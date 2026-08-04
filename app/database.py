from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

# Garante que a pasta ./data exista quando usarmos SQLite local
if settings.DATABASE_URL.startswith("sqlite"):
    db_path = settings.DATABASE_URL.split("///")[-1]
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency do FastAPI: abre e fecha a sessão por requisição."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
