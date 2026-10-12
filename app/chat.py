"""Read-only RAG assistant for questions about Prefa.News data."""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import City, Insight, News

settings = get_settings()
logger = logging.getLogger("prefa_news.chat")

# Used in the function _tokens to limit the number of characters in the question.
_STOP_WORDS = {
   "a", "an", "the", "at", "by", "for", "in", "into", "of", "on", "to", "with", "be", "but", "by", "do", "does", "doing", 
   "don", "had", "has", "have", "he", "her", "him", "his", "i", "is", "it", "its", "me", "my", "no", "not", "of", "on", 
   "or", "so", "such", "that", "the", "their", "them", "then", "your",
}


@dataclass(frozen=True)
class RetrievedContext:
    text: str
    sources: list[dict]
    has_relevant_match: bool


def _tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value.lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return {
        token for token in re.findall(r"[a-z0-9]{3,}", normalized)
        if token not in _STOP_WORDS
    }


def _rank(items: list[dict], question: str, limit: int) -> list[dict]:
    query_tokens = _tokens(question)
    scored = []
    for index, item in enumerate(items):
        searchable = " ".join(str(value) for value in item.values())
        score = len(query_tokens.intersection(_tokens(searchable)))
        scored.append((score, -index, item))
    scored.sort(reverse=True, key=lambda row: (row[0], row[1]))
    relevant = [item for score, _, item in scored if score > 0]
    return (relevant or items)[:limit]


def _has_relevant_match(items: list[dict], question: str) -> bool:
    """Detect whether the question shares a meaningful term with database data."""
    question_tokens = _tokens(question)
    return any(question_tokens.intersection(_tokens(" ".join(map(str, item.values())))) for item in items)


def _compact_context(context: dict) -> str:
    """Keep the serialized RAG context below a predictable request size."""
    compact = {
        "cities": context["cities"][:120],
        "news": context["news"][:12],
        "insights": context["insights"][:8],
    }
    for insight in compact["insights"]:
        insight["summary"] = insight["summary"][:500]

    # Remove the least relevant tail while preserving valid JSON and source IDs.
    while True:
        serialized = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        if len(serialized) <= settings.GROQ_CHAT_MAX_CONTEXT_CHARS:
            return serialized
        if compact["insights"]:
            compact["insights"].pop()
        elif compact["news"]:
            compact["news"].pop()
        elif compact["cities"]:
            compact["cities"].pop()
        else:
            return "{}"


def retrieve_context(db: Session, question: str) -> RetrievedContext:
    """Build context using SELECT statements only; this function never mutates the session."""
    city_rows = db.execute(
        select(City.id, City.name, City.url_type, City.active).order_by(City.name)
    ).all()
    news_rows = db.execute(
        select(
            News.id,
            City.name,
            News.title,
            News.title_pt,
            News.description,
            News.date,
            News.news_url,
        )
        .join(City, News.city_id == City.id)
        .where(News.active.is_(True))
        .order_by(News.value.desc())
    ).all()
    insight_rows = db.execute(
        select(Insight.id, Insight.topic, Insight.title, Insight.summary, Insight.cities, Insight.news_ids)
        .order_by(Insight.generated_at.desc())
        .limit(30)
    ).all()

    cities = [
        {"id": row.id, "name": row.name, "active": row.active}
        for row in city_rows
    ]
    news = [
        {
            "id": row.id,
            "city": row.name,
            "title": row.title,            
            "title_pt": row.title_pt,
            "description": row.description or "",
            "date": row.date.isoformat(),
            "url": row.news_url,
        }
        for row in news_rows
    ]
    insights = [
        {
            "id": row.id,
            "topic": row.topic,
            "title": row.title,
            "summary": row.summary[:800],
            "cities": row.cities or [],
            "news_ids": row.news_ids or [],
        }
        for row in insight_rows
    ]

    selected_news = _rank(news, question, 20)
    selected_insights = _rank(insights, question, 10)
    context = {
        "cities": cities,
        "news": selected_news,
        "insights": selected_insights,
    }
    has_relevant_match = _has_relevant_match(cities + news + insights, question)
    sources = [
        {
            "type": "news",
            "id": item["id"],
            "title": item["title"],
            "city": item["city"],
            "url": item["url"],
        }
        for item in selected_news
    ]
    return RetrievedContext(
        text=_compact_context(context),
        sources=sources,
        has_relevant_match=has_relevant_match,
    )


def answer_question(db: Session, question: str) -> dict:
    settings = get_settings()
    if not settings.GROQ_ENABLED or not settings.GROQ_API_KEY or not settings.GROQ_MODEL:
        raise RuntimeError("The AI ​​assistant is temporarily unavailable.")

    question = question.strip()[:settings.GROQ_CHAT_MAX_QUESTION_CHARS]
    retrieved = retrieve_context(db, question)
    prompt = (
        "You are the Prefa.News assistant. Answer in English about cities, news, "
        "and insights found in the database context. Treat every item in the "
        "context as learned factual knowledge and use the most relevant items, "
        "including descriptions and Portuguese titles when useful. "
        "Use only the provided data. "
        "If DATABASE_MATCH is false, treat the question as outside the Prefa.News domain "
        "unless it is clearly about the portal itself, and reply exactly that you can only "
        "answer questions about Prefa.News cities, news, and insights. "
        "If DATABASE_MATCH is true but the answer is not in the context, clearly state that "
        "you did not find sufficient data. "
        "Do not invent facts, dates, cities, or links. "        
        "Use only continuous text, without links, tables, or bullet points. "
        "Do not include any citations of 'title_pt' or 'news_url' in the response. \n\n"
        f"Question: {question}\n"
        f"DATABASE_MATCH: {str(retrieved.has_relevant_match).lower()}\n\n"
        f"Context retrieved from the database:\n{retrieved.text}"
    )
    try:
        logger.warning("Prompt Size: %s characters", len(prompt))  
        logger.warning("Question: %s", question)
        logger.warning("Context Sources: %s", json.dumps(retrieved.sources, ensure_ascii=False))
        logger.warning("Context Size: %s characters", len(retrieved.text))
        logger.warning("Context News Count: %s", len(retrieved.sources))
        logger.warning("Context Insights Count: %s", len(json.loads(retrieved.text).get("insights", [])))  
        logger.warning("Context Cities Count: %s", len(json.loads(retrieved.text).get("cities", [])))    
        client_kwargs = {"api_key": settings.GROQ_API_KEY}
        if settings.GROQ_API_BASE_URL:
            client_kwargs["base_url"] = settings.GROQ_API_BASE_URL
        client = OpenAI(**client_kwargs)
        response = client.responses.create(
            input=prompt,
            model=settings.GROQ_MODEL,
            max_output_tokens=settings.GROQ_CHAT_MAX_OUTPUT_TOKENS,
        )
        answer = response.output_text.strip()
        if not answer:
            raise ValueError("Groq returned an empty response.")
        logger.warning("Answer Size: %s characters", len(answer))
        logger.warning("Response: %s", response)
        return {"answer": answer, "sources": retrieved.has_relevant_match and retrieved.sources or []}
    except Exception as exc:
        logger.warning("Chat answer failed: %s", exc)
        raise RuntimeError("The AI ​​assistant is temporarily unavailable.") from exc
