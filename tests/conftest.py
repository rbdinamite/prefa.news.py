from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import City, News, Region, FeedType


@pytest.fixture()
def db_session():
    """Banco SQLite em memória, isolado por teste."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_data(db_session):
    """Cria duas cidades (regiões diferentes) e algumas notícias para os testes de API."""
    city_a = City(name="Cidade Sul", regiao=Region.SUL, url_type=FeedType.PROPRIO, active=True)
    city_b = City(name="Cidade Norte", regiao=Region.NORTE, url_type=FeedType.PROPRIO, active=True)
    db_session.add_all([city_a, city_b])
    db_session.flush()

    now = datetime.utcnow()
    news_items = []
    for i in range(10):
        news_items.append(
            News(
                city_id=city_a.id,
                title=f"Notícia sul número {i}",
                date=now - timedelta(hours=i),
                news_url=f"https://exemplo.gov.br/sul/{i}",
                description="Descrição de exemplo " * 5,
                active=True,
                value=100 - i,
            )
        )
    news_items.append(
        News(
            city_id=city_b.id,
            title="Notícia especial do norte sobre prêmio nacional",
            date=now,
            news_url="https://exemplo.gov.br/norte/1",
            description="Uma notícia de destaque na região norte.",
            active=True,
            value=200,
        )
    )
    # Notícia inativa não deve aparecer em nenhuma consulta pública
    news_items.append(
        News(
            city_id=city_a.id,
            title="Notícia ainda não ativada",
            date=now,
            news_url="https://exemplo.gov.br/sul/inativa",
            description="",
            active=False,
            value=0,
        )
    )
    db_session.add_all(news_items)
    db_session.commit()
    return {"city_a": city_a, "city_b": city_b}
