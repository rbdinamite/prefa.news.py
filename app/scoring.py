"""
Reimplementação em Python das regras de pontuação de notícias que, na
versão PHP, estavam espalhadas entre sys/classes/class.TextValuation.php
(algoritmo estilo RAKE) e o corpo de sys/commands/get_news.php (as oito
"validações" de peso).

Não usamos bibliotecas pesadas de NLP (nem a extensão SQLite específica
do PHP text-analysis) — o algoritmo de RAKE simplificado é implementado
aqui mesmo em ~40 linhas, o que facilita testar e não exige dependências
binárias em produção.
"""
from __future__ import annotations

import re
import string
from collections import Counter
from functools import lru_cache
from pathlib import Path

STOP_WORDS_PATH = Path(__file__).parent / "ingestion" / "stop_words_pt.txt"

# Palavras que reduzem a relevância de uma notícia (ex.: editais, boletins administrativos)
POOR_WORDS = [
    "EDITAL", "PROCESSO SELETIVO", "BOLETIM", "COMUNICADO", "/", "COVID",
    "COVID-19", "DECRETO", "PESAR", "FALECIMENTO", "AUDIÊNCIA", "LICITA",
    "PROCESSO", "DEPUTADO",
]

# Palavras que aumentam a relevância (conquistas, prêmios, abrangência maior)
GOOD_WORDS = [
    "NACIONAL", "ESTADUAL", "APRESENTAÇÃO", "APRESENTA", "PREMIAÇÃO",
    "PREMIA", "PRÊMIO", "GRATUITO", "GRATUITA", "GRÁTIS", "VENCE",
    "VENCEDOR", "DESTAQUE", "INTERNACIONAL",
]

MISSING_DESCRIPTION_PENALTY = -100
MISSING_TITLE_PENALTY = -500
UPPERCASE_TITLE_PENALTY = -20
POOR_WORD_PENALTY = -75
DUPLICATE_WORD_PENALTY = -5
GOOD_WORD_BONUS = 5
GOOD_WORD_BONUS_UPPERCASE = 1
ACCESS_WEIGHT = 0.9
HOURLY_DECAY = 0.95
SHORT_TITLE_PENALTY_PER_WORD = 0.99
LONG_TITLE_PENALTY_PER_WORD = 0.75
CONTENT_BONUS_GENERIC = 20  # usado quando não há conteúdo completo (feeds RSS simples)


@lru_cache
def _load_stop_words() -> set[str]:
    if not STOP_WORDS_PATH.exists():
        return set()
    with STOP_WORDS_PATH.open(encoding="utf-8") as fh:
        return {line.strip().lower() for line in fh if line.strip()}


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    return [t for t in text.split() if t]


def check_rake_score(text: str, keyword_score_threshold: float = 100.0) -> float:
    """
    Versão simplificada de RAKE (Rapid Automatic Keyword Extraction):
    agrupa palavras contíguas que não são stop-words em "frases-candidatas",
    pontua cada palavra pelo grau de co-ocorrência dividido pela frequência,
    e soma o score das frases cujo total ultrapassa o limiar.

    Retorna um valor pequeno normalizado (equivalente ao antigo
    checkRake() de class.TextValuation.php, porém sem as dependências
    externas da lib yooper/php-text-analysis).
    """
    stop_words = _load_stop_words()
    words = _tokenize(text)
    if not words:
        return 0.0

    # Divide o texto em frases-candidatas, quebrando em stop-words
    phrases: list[list[str]] = []
    current: list[str] = []
    for w in words:
        if w in stop_words:
            if current:
                phrases.append(current)
                current = []
        else:
            current.append(w)
    if current:
        phrases.append(current)

    if not phrases:
        return 0.0

    freq: Counter[str] = Counter()
    degree: Counter[str] = Counter()
    for phrase in phrases:
        span = len(phrase) - 1
        for word in phrase:
            freq[word] += 1
            degree[word] += span

    word_score = {w: (degree[w] + freq[w]) / freq[w] for w in freq}

    phrase_scores = [sum(word_score[w] for w in phrase) for phrase in phrases]
    relevant = [s for s in phrase_scores if s * 10 >= keyword_score_threshold]

    total_tokens = len(words)
    if total_tokens < 100:
        token_penalty = (100 - total_tokens) * 0.3
    elif total_tokens > 500:
        token_penalty = (total_tokens - 500) * 0.3
    else:
        token_penalty = 0.0

    score = (sum(relevant) * 0.05) + (len(relevant) * 0.5) - token_penalty
    return round(score, 4)


def is_uppercase_title(title: str) -> bool:
    words = title.split(" ")
    return all(not w.islower() for w in words if w)


def contains_any(words: list[str], text_upper: str) -> bool:
    return any(w in text_upper for w in words)


def count_duplicated_words(title_upper: str) -> int:
    cleaned = re.sub(r"[^\w\s]", "", title_upper)
    counts = Counter(w for w in cleaned.split() if len(w) > 4)
    return sum(1 for _, c in counts.items() if c >= 2)


def compute_news_value(
    *,
    title: str,
    description: str | None,
    published_at,
    now,
    has_full_content: bool,
    access_count: int = 0,
) -> float:
    """
    Recalcula o "peso" (relevância) de uma notícia, replicando as oito
    validações originais de get_news.php (checagem de título vazio,
    idade da notícia, caixa alta, palavras boas/ruins, duplicidade de
    palavras, acessos e conteúdo).
    """
    value = 0.0
    title = (title or "").strip()
    description = (description or "").strip()

    if not title:
        return MISSING_TITLE_PENALTY

    title_upper = title.upper()

    # Idade da notícia (desconto por hora decorrida desde a publicação)
    hours_elapsed = (now - published_at).total_seconds() / 3600
    value -= hours_elapsed * HOURLY_DECAY

    is_upper = is_uppercase_title(title)
    if is_upper:
        value += UPPERCASE_TITLE_PENALTY

    if contains_any(POOR_WORDS, title_upper):
        value += POOR_WORD_PENALTY

    duplicated = count_duplicated_words(title_upper)
    if duplicated:
        value += duplicated * DUPLICATE_WORD_PENALTY

    if access_count > 0:
        value += access_count * ACCESS_WEIGHT

    if contains_any(GOOD_WORDS, title_upper):
        value += GOOD_WORD_BONUS_UPPERCASE if is_upper else GOOD_WORD_BONUS

    words_number = len(title_upper.split())
    if words_number < 5:
        value -= (5 - words_number) * SHORT_TITLE_PENALTY_PER_WORD
    elif words_number > 20:
        value -= (words_number - 20) * LONG_TITLE_PENALTY_PER_WORD

    if len(description) > 30:
        if has_full_content:
            value += check_rake_score(description)
        else:
            value += CONTENT_BONUS_GENERIC

    if not description:
        value += MISSING_DESCRIPTION_PENALTY

    return round(value, 4)
