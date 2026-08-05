"""
Central application settings.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    APP_NAME: str = "Prefa.News"
    APP_ENV: str = "development"  # development | production
    SECRET_KEY: str = "change-me-in-production"
    DEBUG: bool = True

    # Database (SQLite by default; change to Postgres/MySQL in production
    # by adjusting DATABASE_URL, as we use SQLAlchemy)
    DATABASE_URL: str = "sqlite:///./data/prefa_news.db"

    # Newsletter / e-mail
    MAIL_HOST: str = ""
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""

    # Instagram integration
    INSTAGRAM_ENABLED: bool = False
    INSTAGRAM_USER_ID: str = ""
    INSTAGRAM_ACCESS_TOKEN: str = ""
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # News ingestion
    NEWS_FETCH_TIMEOUT: int = 15  # segundos
    NEWS_ITEMS_PER_FEED: int = 5
    NEWS_MAX_AGE_DAYS_TO_IGNORE_CITY: int = 15
    NEWS_MIN_SCORE_TO_REMOVE: int = -1000

    # CORS (if the front-end is consumed separately)
    CORS_ORIGINS: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
