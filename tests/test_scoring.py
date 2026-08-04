from datetime import datetime, timedelta

from app.scoring import (
    check_rake_score,
    compute_news_value,
    contains_any,
    count_duplicated_words,
    is_uppercase_title,
)


def test_is_uppercase_title_detects_all_caps():
    assert is_uppercase_title("PREFEITURA INAUGURA NOVA ESCOLA") is True
    assert is_uppercase_title("Prefeitura inaugura nova escola") is False


def test_contains_any_matches_keyword_list():
    assert contains_any(["EDITAL", "DECRETO"], "PUBLICADO NOVO EDITAL DE LICITAÇÃO")
    assert not contains_any(["EDITAL"], "PREFEITURA ENTREGA NOVA CRECHE")


def test_count_duplicated_words_ignores_short_words():
    # "para" e "de" tem <=4 chars e devem ser ignoradas mesmo repetidas
    title = "PREFEITURA PREFEITURA ENTREGA PARA PARA CIDADE CIDADE"
    assert count_duplicated_words(title) == 2  # PREFEITURA e CIDADE


def test_check_rake_score_is_zero_for_empty_text():
    assert check_rake_score("") == 0.0


def test_check_rake_score_rewards_richer_content():
    short_text = "Prefeitura realiza reunião."
    long_text = (
        "A prefeitura realizou uma extensa reunião pública com a comunidade "
        "para debater investimentos em educação, saúde e infraestrutura urbana, "
        "apresentando resultados do programa de modernização administrativa "
        "e captação de recursos estaduais para obras prioritárias no município."
    )
    assert check_rake_score(long_text) >= check_rake_score(short_text)


def test_compute_news_value_penalizes_missing_title():
    value = compute_news_value(
        title="",
        description="qualquer coisa",
        published_at=datetime.utcnow(),
        now=datetime.utcnow(),
        has_full_content=False,
    )
    assert value == -500


def test_compute_news_value_penalizes_missing_description():
    value = compute_news_value(
        title="Prefeitura inaugura novo parque municipal para a comunidade",
        description="",
        published_at=datetime.utcnow(),
        now=datetime.utcnow(),
        has_full_content=False,
    )
    assert value <= -100


def test_compute_news_value_rewards_recent_news_over_old_news():
    now = datetime.utcnow()
    recent = compute_news_value(
        title="Prefeitura entrega novas moradias populares para famílias carentes",
        description="Texto descritivo com mais de trinta caracteres sobre o assunto.",
        published_at=now - timedelta(hours=1),
        now=now,
        has_full_content=False,
    )
    old = compute_news_value(
        title="Prefeitura entrega novas moradias populares para famílias carentes",
        description="Texto descritivo com mais de trinta caracteres sobre o assunto.",
        published_at=now - timedelta(days=10),
        now=now,
        has_full_content=False,
    )
    assert recent > old


def test_compute_news_value_rewards_access_count():
    now = datetime.utcnow()
    base_kwargs = dict(
        title="Prefeitura entrega novas moradias populares para famílias carentes",
        description="Texto descritivo com mais de trinta caracteres sobre o assunto.",
        published_at=now,
        now=now,
        has_full_content=False,
    )
    without_access = compute_news_value(**base_kwargs, access_count=0)
    with_access = compute_news_value(**base_kwargs, access_count=50)
    assert with_access > without_access
