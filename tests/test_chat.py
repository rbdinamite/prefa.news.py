from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.chat import answer_question, retrieve_context
from app.database import Base
from app.models import City, Insight, News


def make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def seed_chat_data(db):
    city = City(name="Cidade Educação", url_type="PROPRIO", active=True)
    db.add(city)
    db.flush()
    db.add(News(
        city_id=city.id,
        title="Prefeitura inaugura escola municipal",
        title_pt="Prefeitura inaugura escola municipal",
        date=datetime.utcnow(),
        news_url="https://example.com/escola",
        description="Nova escola amplia as vagas de educação infantil.",
        active=True,
        value=10,
    ))
    db.add(Insight(
        topic="Educação municipal",
        title="Investimentos em educação",
        summary="Cidades ampliam a rede municipal de ensino.",
        cities=[city.name],
        news_ids=[],
    ))
    db.commit()


def test_retrieve_context_prioritizes_matching_news():
    db = make_session()
    seed_chat_data(db)

    context = retrieve_context(db, "Quais notícias falam sobre escola?")

    assert '"title": "Prefeitura inaugura escola municipal"' in context.text
    assert '"description": "Nova escola amplia as vagas de educação infantil."' in context.text
    assert context.sources[0]["url"] == "https://example.com/escola"
    assert context.sources[0]["city"] == "Cidade Educação"
    assert context.has_relevant_match is True
    db.close()


def test_answer_question_uses_groq_and_keeps_database_read_only():
    db = make_session()
    seed_chat_data(db)
    groq_response = SimpleNamespace(output_text="A Cidade Educação inaugurou uma escola municipal.")
    mock_client = Mock()
    mock_client.responses.create.return_value = groq_response

    with patch("app.chat.get_settings", return_value=SimpleNamespace(
        GROQ_ENABLED=True,
        GROQ_API_KEY="test-key",
        GROQ_MODEL="test-model",
        GROQ_API_BASE_URL="https://api.groq.com/openai/v1",
        GROQ_CHAT_MAX_QUESTION_CHARS=1000,
        GROQ_CHAT_MAX_OUTPUT_TOKENS=600,
    )), patch("app.chat.OpenAI", return_value=mock_client):
        result = answer_question(db, "O que aconteceu sobre educação?")

    assert result["answer"].startswith("A Cidade Educação")
    prompt = mock_client.responses.create.call_args.kwargs["input"]
    assert "Nova escola amplia as vagas de educação infantil." in prompt
    assert "DATABASE_MATCH: true" in prompt
    assert db.query(News).count() == 1
    mock_client.responses.create.assert_called_once()
    db.close()
