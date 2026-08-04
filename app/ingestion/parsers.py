"""
Substitui a dependência da lib SimplePie (assets/lib/SimplePie) usada na
versão PHP para ler os feeds RSS das prefeituras.

Usamos `feedparser`, que já normaliza RSS 1.0/2.0 e Atom, cobrindo os
três formatos que a versão antiga tratava manualmente (IPM, FECAM2, P1).

Decisão de produto: a nova versão do front-end não exibe mais imagens de
notícia, então não é mais necessário abrir cada página da notícia só para
extrair a tag <meta property="og:image"> (como o layout IPM fazia) nem
processar enclosures/tags de imagem — isso também deixa a ingestão bem
mais rápida e resiliente.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from time import mktime

import feedparser

from app.models import FeedType

_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(raw: str | None) -> str:
    if not raw:
        return ""
    text = _TAG_RE.sub("", raw)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_malformed_entities(text: str) -> str:
    """Equivalente a limparCaracteresHtmlMalFormados() do PHP."""
    text = re.sub(r"&#\d+;", "", text)
    text = re.sub(r"&#x[0-9a-fA-F]+;", "", text)
    text = re.sub(r"&[a-zA-Z]+;", "", text)
    return text


@dataclass
class RawNewsItem:
    title: str
    link: str
    published_at: datetime
    description: str
    has_full_content: bool  # True quando o feed já traz o corpo completo da notícia (ex.: FECAM2)


def _entry_datetime(entry) -> datetime:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc).replace(tzinfo=None)
    return datetime.utcnow()


def _entry_description(entry, feed_type: str) -> tuple[str, bool]:
    if feed_type == FeedType.FECAM2:
        content = entry.get("content")
        if content:
            return strip_html(content[0].get("value", "")), True
    summary = entry.get("summary") or entry.get("description") or ""
    return strip_html(summary), False


def parse_feed(url: str, feed_type: str, limit: int = 5, timeout: int = 15) -> list[RawNewsItem]:
    """
    Faz o parse de um feed RSS/Atom e devolve uma lista normalizada de
    itens, independente do "layout" original (IPM, FECAM2, P1).
    """
    parsed = feedparser.parse(url, request_headers={"User-Agent": "PrefaNewsBot/2.0"})
    items: list[RawNewsItem] = []
    for entry in parsed.entries[:limit]:
        title = clean_malformed_entities(strip_html(entry.get("title", "")))
        if not title:
            continue
        description, has_full_content = _entry_description(entry, feed_type)
        items.append(
            RawNewsItem(
                title=title,
                link=entry.get("link", ""),
                published_at=_entry_datetime(entry),
                description=description,
                has_full_content=has_full_content,
            )
        )
    return items
