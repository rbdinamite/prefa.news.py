from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

# Ensures that the ./data folder exists when using local SQLite.
if settings.DATABASE_URL.startswith("sqlite"):
    db_path = settings.DATABASE_URL.split("///")[-1]
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

readonly_engine = engine
if settings.READONLY_DATABASE_URL:
    readonly_connect_args = (
        {"check_same_thread": False}
        if settings.READONLY_DATABASE_URL.startswith("sqlite")
        else {}
    )
    readonly_engine = create_engine(
        settings.READONLY_DATABASE_URL,
        connect_args=readonly_connect_args,
        future=True,
    )
ReadOnlySessionLocal = sessionmaker(
    bind=readonly_engine, autoflush=False, autocommit=False, future=True
)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency for FastAPI: opens and closes the session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_readonly_db():
    """Dependency for read-only consumers such as the AI assistant."""
    db = ReadOnlySessionLocal()
    try:
        yield db
    finally:
        db.close()
