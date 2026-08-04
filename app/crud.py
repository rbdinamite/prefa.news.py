"""
Camada de consultas que substitui o sys/controller.php original.

Diferença importante em relação ao PHP: lá o parâmetro `search` e `sector`
eram concatenados diretamente na query SQL (`'AND N.title LIKE "%' . $_GET['search'] . '%"'`),
o que é uma falha clássica de SQL Injection. Aqui todas as condições usam
bind parameters via SQLAlchemy, então a mesma classe de vulnerabilidade
não existe mais.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Access, City, HighlightNews, News, Newsletter


def _base_news_query():
    return (
        select(
            News.id,
            City.name.label("city"),
            #func.substr(City.regiao, 1, 2).label("reg_code"),
            News.title,
            News.date,
            News.news_url.label("link"),
            News.description,
        )
        .join(City, News.city_id == City.id)
        .where(News.active.is_(True))
    )


def _apply_filters(query, sector: str | None, search: str | None):
    #if sector:
        #query = query.where(City.regiao == sector)
    if search:
        query = query.where(News.title.ilike(f"%{search}%"))
    return query


def _rows_to_dicts(rows) -> list[dict]:
    return [dict(row._mapping) for row in rows]


def load_main_news(db: Session, sector: str | None, search: str | None) -> dict:
    base = _apply_filters(_base_news_query(), sector, search).order_by(
        News.value.desc(), News.date.desc()
    )
    main = db.execute(base.limit(7)).all()
    side = db.execute(base.offset(7).limit(4)).all()
    roller = db.execute(base.offset(11).limit(9)).all()
    more = db.execute(base.offset(20).limit(8)).all()
    return {
        "main": _rows_to_dicts(main),
        "side": _rows_to_dicts(side),
        "roller": _rows_to_dicts(roller),
        "more": _rows_to_dicts(more),
    }

"""
def load_sector_news(db: Session, search: str | None) -> dict:
    result = {}
    mapping = {
        "south": "SUL",
        "center": "GRANDE FLORIPA",
        "north": "NORTE",
        "west": "OESTE",
        "montain": "SERRANA",
        "valley": "VALE",
    }
    for key, regiao in mapping.items():
        query = _apply_filters(_base_news_query(), regiao, search).order_by(
            News.value.desc(), News.date.desc()
        ).limit(6)
        result[key] = _rows_to_dicts(db.execute(query).all())
    return result
"""

def load_more_fixed_news(db: Session, sector: str | None, search: str | None) -> list[dict]:
    query = _apply_filters(_base_news_query(), sector, search).order_by(
        News.value.desc(), News.date.desc()
    ).offset(21).limit(8)
    return _rows_to_dicts(db.execute(query).all())


def load_more_by_pointer(
    db: Session, pointer: int, sector: str | None, search: str | None
) -> list[dict]:
    pointer = max(pointer, 0)
    query = _apply_filters(_base_news_query(), sector, search).order_by(
        News.value.desc(), News.date.desc()
    ).offset(pointer).limit(4)
    return _rows_to_dicts(db.execute(query).all())


def load_active_cities(db: Session) -> list[str]:
    rows = db.execute(select(City.name).where(City.active.is_(True)).order_by(City.name)).all()
    return [r[0] for r in rows]


def save_click(db: Session, news_id: int, click_type: str, server_meta: str) -> None:
    access = Access(news_id=news_id, type=click_type, server=server_meta)
    db.add(access)
    db.commit()


def get_star_news(db: Session, limit: int = 15) -> list[dict]:
    access_count = (
        select(func.count(Access.id))
        .where(Access.news_id == News.id)
        .correlate(News)
        .scalar_subquery()
    )
    query = (
        select(
            News.id,
            City.name.label("city"),
            #func.substr(City.regiao, 1, 2).label("reg_code"),
            News.title,
            News.date,
            News.news_url.label("link"),
            News.description,
            access_count.label("qt_access"),
        )
        .join(HighlightNews, HighlightNews.news_id == News.id)
        .join(City, News.city_id == City.id)
        .group_by(HighlightNews.news_id)
        .order_by(HighlightNews.date.desc(), access_count.desc(), News.date.desc())
        .limit(limit)
    )
    rows = db.execute(query).all()
    return [
        {k: v for k, v in dict(row._mapping).items() if k != "qt_access"} for row in rows
    ]


def get_star_city(db: Session) -> dict:
    limit_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    access_count = (
        select(func.count(Access.id))
        .where(Access.news_id == News.id)
        .correlate(News)
        .scalar_subquery()
    )
    query = (
        select(
            City.name.label("city_name"),
            func.count(HighlightNews.news_id).label("qt_news"),
            func.sum(access_count).label("qt_access"),
        )
        .join(News, HighlightNews.news_id == News.id)
        .join(City, News.city_id == City.id)
        .where(HighlightNews.date >= limit_date)
        .group_by(City.id)
        .order_by(func.count(HighlightNews.news_id).desc())
        .limit(1)
    )
    row = db.execute(query).first()
    city_name = row.city_name if row else None

    city_news: list[dict] = []
    if city_name:
        news_query = (
            _base_news_query()
            .where(City.name == city_name)
            .order_by(News.value.desc(), News.date.desc())
            .limit(6)
        )
        city_news = _rows_to_dicts(db.execute(news_query).all())

    return {"city_name": city_name, "city_news": city_news}


def newsletter_email_exists(db: Session, mail: str) -> bool:
    count = db.execute(select(func.count(Newsletter.id)).where(Newsletter.mail == mail)).scalar()
    return bool(count)


def save_newsletter(db: Session, mail: str) -> None:
    db.add(Newsletter(mail=mail))
    db.commit()
