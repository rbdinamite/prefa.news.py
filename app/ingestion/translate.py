"""Tradução de títulos de notícias para inglês na ingestão."""
from __future__ import annotations

import logging
import re
from functools import lru_cache

from deep_translator import GoogleTranslator, MyMemoryTranslator

logger = logging.getLogger("prefa_news.ingestion")

MAX_TITLE_LENGTH = 500
_ERROR_MARKERS = ("error 500", "server error", "please try again later", "<html")


@lru_cache(maxsize=1)
def _google_translator() -> GoogleTranslator:
    return GoogleTranslator(source="pt", target="en")


@lru_cache(maxsize=1)
def _mymemory_translator() -> MyMemoryTranslator:
    return MyMemoryTranslator(source="portuguese brazil", target="english")


def _looks_like_error(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _ERROR_MARKERS)


def _normalize_translation(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _translate_with_google(title: str) -> str | None:
    translated = _google_translator().translate(title)
    if not translated:
        return None
    result = _normalize_translation(translated)
    if _looks_like_error(result):
        return None
    return result


def _translate_with_mymemory(title: str) -> str | None:
    translated = _mymemory_translator().translate(title)
    if not translated:
        return None
    result = _normalize_translation(translated)
    if _looks_like_error(result):
        return None
    return result


def translate_title_to_english(title: str) -> str:
    """Traduz o título para inglês; em falha, devolve o texto original."""
    title = (title or "").strip()
    if not title:
        return title

    for attempt, translate in enumerate((_translate_with_google, _translate_with_mymemory), start=1):
        try:
            translated = translate(title)
            if translated:
                return translated[:MAX_TITLE_LENGTH]
        except Exception as exc:
            provider = "Google" if attempt == 1 else "MyMemory"
            logger.warning("Falha ao traduzir título com %s [%s]: %s", provider, title[:80], exc)

    logger.warning("Não foi possível traduzir o título; mantendo original [%s]", title[:80])
    return title[:MAX_TITLE_LENGTH]
