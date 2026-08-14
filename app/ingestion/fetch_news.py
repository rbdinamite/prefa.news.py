"""
Ponto de entrada da rotina de ingestão de notícias, equivalente a
sys/commands/get_news.php. Uso:

    python -m app.ingestion.fetch_news

Pensado para ser chamado periodicamente por um cron/systemd timer (ver
DEPLOY.md), assim como o script PHP original era chamado via cron no
cPanel.

Passos (mesma ordem lógica do script PHP original):
  1. Busca notícias novas nos feeds das cidades ativas.
  2. Recalcula o "peso" (relevância) de todas as notícias recentes.
  3. Remove notícias com peso muito baixo (spam/editais/etc).
  4. Ativa as notícias novas para exibição pública.
  5. Remove duplicidades (mesmo título+descrição+cidade).
  6. Registra o destaque do dia (highlight_news).
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
    logger.info("## CONSULTA DE NOTÍCIAS ##")
    cities = db.execute(
        select(City).where(City.active.is_(True)).order_by(City.name)
    ).scalars().all()

    inserted_count = 0
    for city in cities:
        if city.url_type == FeedType.PROPRIO or not city.url_path:
            logger.info("Cidade [%s] usa layout próprio (sem feed padrão). Ignorando.", city.name)
            continue

        logger.info("Consultando notícias de [%s] - layout [%s]", city.name, city.url_type)
        try:
            items = parse_feed(
                city.url_path,
                city.url_type,
                limit=settings.NEWS_ITEMS_PER_FEED,
                timeout=settings.NEWS_FETCH_TIMEOUT,
            )
        except Exception as exc:
            logger.warning("Falha ao consultar feed de [%s]: %s", city.name, exc)
            continue

        if not items:
            continue
        
        newest = items[0]
        age_days = (datetime.now() - newest.published_at).days
        logger.info("Notícia mais recente de [%s]: %s (%s dias atrás)", city.name, newest.published_at.date(), age_days)
        if age_days > settings.NEWS_MAX_AGE_DAYS_TO_IGNORE_CITY:
            logger.info("Feed de [%s] está desatualizado (>%s dias). Ignorando cidade nesta rodada.",
                        city.name, settings.NEWS_MAX_AGE_DAYS_TO_IGNORE_CITY)
            continue

        city.lastcheck_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        city.lastnews_date = newest.published_at.strftime("%Y-%m-%d")

        for item in items:
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
                "Notícia cadastrada: [%s] [%s] (original: [%s])",
                item.published_at,
                title_en,
                item.title,
            )

    db.commit()
    logger.info("Finalizou consulta de notícias. %s notícias novas inseridas.", inserted_count)
    return inserted_count


def rescore_news(db) -> None:
    logger.info("## AVALIAÇÃO DAS NOTÍCIAS ##")
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
            logger.info("Peso da notícia [%s] atualizado de [%s] para [%s]", news.id, news.value, new_value)
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
        logger.info("Removeu %s notícias com pontuação baixa", len(to_remove))

    # Ativa notícias novas
    activated = db.execute(
        News.__table__.update().where(News.active.is_(False)).values(active=True)
    )
    db.commit()
    logger.info("Ativou %s notícias novas", activated.rowcount)

    # Remove duplicidades (mesmo título + descrição + cidade), mantendo o
    # registro de menor id em cada grupo (o mais antigo/original)
    groups = db.execute(
        select(News.city_id, News.title, News.description, func.min(News.id).label("keep_id"))
        .group_by(News.city_id, News.title, News.description)
        .having(func.count(News.id) > 1)
    ).all()

    removed_dupes = 0
    for city_id, title, description, keep_id in groups:
        result = db.execute(
            News.__table__.delete().where(
                News.city_id == city_id,
                News.title == title,
                News.description == description,
                News.id != keep_id,
            )
        )
        removed_dupes += result.rowcount
    if removed_dupes:
        db.commit()
        logger.info("Removeu %s notícias duplicadas", removed_dupes)


def register_daily_highlight(db) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    already = db.execute(
        select(func.count(HighlightNews.id)).where(
            HighlightNews.date == today, HighlightNews.type == "portal"
        )
    ).scalar()
    if already:
        logger.info("Destaques do dia já registrados para [%s]", today)
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
        logger.info("Registrados %s destaques do dia", len(top_news))


def run() -> None:
    Base.metadata.create_all(bind=engine)
    started_at = datetime.now(timezone.utc)
    logger.info("#" * 30)
    logger.info("Iniciando execução da ingestão de notícias")
    logger.info("#" * 30)

    db = SessionLocal()
    try:
        fetch_new_news(db)
        rescore_news(db)
        #register_daily_highlight(db)
    finally:
        db.close()

    elapsed = datetime.now(timezone.utc) - started_at
    logger.info("Finalizado em %s", timedelta(seconds=int(elapsed.total_seconds())))


if __name__ == "__main__":
    run()
