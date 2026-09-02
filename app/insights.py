"""Generate and persist cross-city insights using the Groq chat API."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta

from openai import OpenAI
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import City, Insight, News

logger = logging.getLogger("prefa_news.insights")


def _news_context(db: Session) -> list[dict]:
    rows = db.execute(
        select(News.id, City.name, News.title_pt, News.title, News.description, News.date)
        .join(City, News.city_id == City.id)
        .where(News.active.is_(True))
        .order_by(News.value.desc())
        .limit(50)
    ).all()
    return [
        {
            "id": row.id,
            "city": row.name,
            "title": row.title_pt or row.title,
            #"description": (row.description or "")[:500],
            "date": row.date.isoformat(),
        }
        for row in rows
    ]


def _extract_json(content: str) -> list[dict]:
    content = content.strip()
    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.IGNORECASE | re.DOTALL)
    if fenced_match:
        content = fenced_match.group(1).strip()

    parsed = json.loads(content)
    if isinstance(parsed, dict):
        parsed = parsed.get("insights", [])
    if not isinstance(parsed, list):
        raise ValueError("Groq response is not a list of insights")
    return parsed


def _build_insights(generated: list[dict], context: list[dict]) -> list[Insight]:
    """
    Example of generated insights from Groq:
    [
        {
            'topic': 'Multi‑Vaccination Day Initiatives', 
            'title': 'Multi‑Vaccination Day Events Across Municipalities', 
            'summary': 'Both Morro da Fumaça and Gravatal are hosting Multi‑Vaccination Day campaigns this weekend, offering a broad range of immunizations to children and adolescents aged under 15. These coordinated efforts aim to increase coverage and streamline access to healthcare services.',
            'cities': ['Morro da Fumaça', 'Gravatal'], 
            'news_ids': [52, 37]
        }, 
        {
            'topic': 'Municipal Road Paving Projects', 
            'title': 'Municipal Road Paving Projects Advancing Urban Mobility', 
            'summary': 'Imbituba and Praia Grande are completing significant paving works—Imbituba’s Avenida Central da Praia do Rosa and Praia Grande’s Rua Arnaldo Inácio Silveira—to improve infrastructure, reduce traffic congestion, and enhance safety for residents.', 
            'cities': ['Imbituba', 'Praia Grande'], 
            'news_ids': [41, 58]
        }
    ]
    """
    news_by_id = {item["id"]: item for item in context}
    insights: list[Insight] = []
    for item in generated[:5]:
        if not isinstance(item, dict):
            continue
        try:
            news_ids = list(dict.fromkeys(
                int(news_id) for news_id in item.get("news_ids", []) if int(news_id) in news_by_id
            ))
        except (TypeError, ValueError):
            continue

        cities = list(dict.fromkeys(news_by_id[news_id]["city"] for news_id in news_ids))
        if len(cities) < 2:
            continue

        topic = str(item.get("topic", "Regional pattern")).strip()
        title = str(item.get("title", "")).strip()
        summary = str(item.get("summary", "")).strip()
        if not title or not summary:
            continue

        insights.append(Insight(
            topic=topic[:160] or "Regional pattern",
            title=title[:300],
            summary=summary[:4000],
            cities=cities,
            news_ids=news_ids,
        ))
    return insights


def generate_insights(db: Session) -> int:
    """Generate today's insights when Groq is enabled and news is available."""
    settings = get_settings()
    if not settings.GROQ_ENABLED or not settings.GROQ_API_KEY:
        return 0

    today = datetime.utcnow().date()
    already_generated = db.scalar(
        select(Insight.id).where(Insight.generated_at >= datetime.combine(today, datetime.min.time()))
    )
    if already_generated:
        logger.info("Insights already generated today")
        return 0

    context = _news_context(db)
    if not context:
        logger.info("No news available for insight generation")
        return 0

    prompt = (
        "Analise as notícias públicas abaixo e encontre padrões sobre o mesmo assunto "
        "que apareçam em pelo menos duas cidades diferentes. Gere de 1 a 5 insights. "
        "Ignore coincidências fracas. Responda SOMENTE JSON válido no formato: "
        '{"insights":[{"topic":"...","title":"...","summary":"...",'
        '"cities":["..."],"news_ids":[1,2]}]}. '
        "O conteúdo das notícias está em português do Brasil, mas o resultado deve ser gerado em inglês. "
        "Cada insight deve citar pelo menos duas cidades "
        "e usar somente news_ids presentes no conjunto fornecido.\n\n"
        f"Notícias:\n{json.dumps(context, ensure_ascii=False)}"
    )

    logger.info("Prompt Size: %s characters", len(prompt))
    try:
        client = OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url=settings.GROQ_API_BASE_URL,
        )

        response = client.responses.create(
            input=prompt,
            model=settings.GROQ_MODEL,
        )
        generated = _extract_json(response.output_text)        
        insights = _build_insights(generated, context)
        if not insights:
            logger.info("Groq returned no cross-city insights")
            return 0

        db.execute(delete(Insight).where(Insight.generated_at < datetime.utcnow() - timedelta(days=30)))
        db.add_all(insights)
        db.commit()
        return len(insights)
    except Exception as exc:
        logger.warning("Insight generation failed: %s", exc)
        db.rollback()
        return 0