"""
Entry point for the news ingestion routine
Usage:

    python -m app.ingestion.fetch_news

Designed to be called periodically by a cron/systemd timer (see DEPLOY.md).

Steps:
  1. Fetches new news from active city feeds. 
  2. Recalculates the "weight" (relevance) of all recent news items. 
  3. Removes news items with very low weight (spam, official notices, etc.). 
  4. Activates new news items for public display. 
  5. Removes duplicates (same title + description + city). 
  6. Records the featured news of the day (highlight_news).
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone, timedelta

from sqlalchemy import func, select

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.ingestion.parsers import parse_feed
from app.ingestion.translate import translate_title_to_english
from app.models import Access, City, FeedType, HighlightNews, News
from app.scoring import compute_news_value

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("prefa_news.ingestion")

settings = get_settings()


def fetch_new_news(db) -> int:
    logger.info("## CHECKING NEWS ##")
    cities = db.execute(
        select(City).where(City.active.is_(True)).order_by(City.name)
    ).scalars().all()

    inserted_count = 0
    for city in cities:
        if city.url_type == FeedType.PROPRIO or not city.url_path:
            logger.info("City [%s] use specific layout (without feed). Ignoring.", city.name)
            continue

        logger.info("Checking news from [%s] - layout [%s]", city.name, city.url_type)
        try:
            items = parse_feed(
                city.url_path,
                city.url_type,
                limit=settings.NEWS_ITEMS_PER_FEED,
                timeout=settings.NEWS_FETCH_TIMEOUT,
            )
        except Exception as exc:
            logger.warning("Failed to check feed from [%s]: %s", city.name, exc)
            continue

        if not items:
            continue
        
        newest = items[0]
        age_days = (datetime.now() - newest.published_at).days
        logger.info("Last news from [%s]: %s (%s days ago)", city.name, newest.published_at.date(), age_days)
        if age_days > settings.NEWS_MAX_AGE_DAYS_TO_IGNORE_CITY:
            logger.info("Feed from [%s] is old (>%s days). Ignoring city.",
                        city.name, settings.NEWS_MAX_AGE_DAYS_TO_IGNORE_CITY)
            continue

        city.lastcheck_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        city.lastnews_date = newest.published_at.strftime("%Y-%m-%d")
        
        for item in items:
            # Executing translate function
            title_en = translate_title_to_english(item.title)

            exists = db.execute(
                select(func.count(News.id)).where(
                    News.city_id == city.id,
                    News.date == item.published_at,
                    News.title == title_en,
                )
            ).scalar()
            if exists:
                continue
            news = News(
                city_id=city.id,
                title=title_en,
                title_pt=item.title,
                date=item.published_at,
                news_url=item.link,
                description=item.description,
                active=False,
                value=0.0,
                pub_instagram=False,
            )
            db.add(news)
            inserted_count += 1
            logger.info(
                "News inserted: [%s] [%s] (original: [%s])",
                item.published_at,
                title_en,
                item.title,
            )

    db.commit()
    logger.info("Check completed. %s new news items inserted.", inserted_count)
    return inserted_count


def rescore_news(db) -> None:
    logger.info("## SCORING NEWS ##")
    now = datetime.now()
    rows = db.execute(
        select(News, City.url_type)
        .join(City, News.city_id == City.id)
        .where(News.value >= -99, City.active.is_(True))
    ).all()

    for news, url_type in rows:
        access_count = db.execute(
            select(func.count(Access.id)).where(Access.news_id == news.id)
        ).scalar()

        new_value = compute_news_value(
            title=news.title,
            description=news.description,
            published_at=news.date,
            now=now,
            has_full_content=(url_type == FeedType.FECAM),
            access_count=access_count or 0,
        )
        if new_value != news.value:
            logger.info("Score [%s] updated from [%s] to [%s]", news.id, news.value, new_value)
            news.value = new_value

    db.commit()

    # Remove notícias com peso muito baixo, exceto as que já foram destaque
    to_remove = db.execute(
        select(News.id)
        .outerjoin(HighlightNews, HighlightNews.news_id == News.id)
        .where(News.value <= settings.NEWS_MIN_SCORE_TO_REMOVE, HighlightNews.id.is_(None))
    ).scalars().all()
    if to_remove:
        db.execute(News.__table__.delete().where(News.id.in_(to_remove)))
        db.commit()
        logger.info("Removed %s news items with low scores", len(to_remove))

    # Ativa notícias novas
    activated = db.execute(
        News.__table__.update().where(News.active.is_(False)).values(active=True)
    )
    db.commit()
    logger.info("Activated %s new news items", activated.rowcount)

    # Remove duplicidades (mesmo título + descrição + cidade), mantendo o
    # registro de menor id em cada grupo (o mais antigo/original)
    groups = db.execute(
        select(News.city_id, News.title_pt, News.description, func.min(News.id).label("keep_id"))
        .group_by(News.city_id, News.title_pt, News.description)
        .having(func.count(News.id) > 1)
    ).all()

    removed_dupes = 0
    for city_id, title_pt, description, keep_id in groups:
        result = db.execute(
            News.__table__.delete().where(
                News.city_id == city_id,
                News.title_pt == title_pt,
                #News.description == description,
                News.id != keep_id,
            )
        )
        removed_dupes += result.rowcount
    if removed_dupes:
        db.commit()
        logger.info("Removed %s duplicate news items", removed_dupes)

    # Removing news with the translate failure (title = title_pt)
    to_remove = db.execute(
        select(News.id)
        .where(News.title == News.title_pt)
        .where(News.active.is_(True))
    ).scalars().all()
    if to_remove:
        db.execute(News.__table__.delete().where(News.id.in_(to_remove)))
        db.commit()
        logger.info("Removed %s news items with translation failures", len(to_remove))

def register_daily_highlight(db) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    already = db.execute(
        select(func.count(HighlightNews.id)).where(
            HighlightNews.date == today, HighlightNews.type == "portal"
        )
    ).scalar()
    if already:
        logger.info("Daily highlights already registered for [%s]", today)
        return

    top_news = db.execute(
        select(News.id)
        .outerjoin(HighlightNews, HighlightNews.news_id == News.id)
        .where(HighlightNews.id.is_(None), News.active.is_(True))
        .order_by(News.value.desc())
        .limit(3)
    ).scalars().all()

    for news_id in top_news:
        db.add(HighlightNews(news_id=news_id, date=today, type="portal"))
    db.commit()
    if top_news:
        logger.info("Registered %s daily highlights", len(top_news))


def run() -> None:
    Base.metadata.create_all(bind=engine)
    started_at = datetime.now(timezone.utc)
    logger.info("#" * 30)
    logger.info("Starting news ingestion execution")
    logger.info("#" * 30)

    db = SessionLocal()
    try:
        fetch_new_news(db)
        rescore_news(db)
        #register_daily_highlight(db)
    finally:
        db.close()

    elapsed = datetime.now(timezone.utc) - started_at
    logger.info("Finalized in %s", timedelta(seconds=int(elapsed.total_seconds())))


if __name__ == "__main__":
    run()
