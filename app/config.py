"""
Configurações centrais da aplicação.
Todos os valores sensíveis vêm de variáveis de ambiente (.env),
nunca ficam hard-coded no código como na versão PHP original
(sys/classes/class.Config.php).
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Aplicação
    APP_NAME: str = "Prefa.News"
    APP_ENV: str = "development"  # development | production
    SECRET_KEY: str = "change-me-in-production"
    DEBUG: bool = True

    # Banco de dados (SQLite por padrão; troque por Postgres/MySQL em produção
    # bastando ajustar DATABASE_URL, pois usamos SQLAlchemy)
    DATABASE_URL: str = "sqlite:///./data/prefa_news.db"

    # Newsletter / e-mail (equivalente a MAIL_HOST, MAIL_USERNAME, ... do PHP)
    MAIL_HOST: str = ""
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""

    # Integração Instagram (equivalente a INSTAGRAM_USER_ID / INSTAGRAM_ACCESS_TOKEN)
    INSTAGRAM_ENABLED: bool = False
    INSTAGRAM_USER_ID: str = ""
    INSTAGRAM_ACCESS_TOKEN: str = ""
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # Ingestão de notícias
    NEWS_FETCH_TIMEOUT: int = 15  # segundos
    NEWS_ITEMS_PER_FEED: int = 5
    NEWS_MAX_AGE_DAYS_TO_IGNORE_CITY: int = 15
    NEWS_MIN_SCORE_TO_REMOVE: int = -1000

    # CORS (se o front for consumido separadamente)
    CORS_ORIGINS: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
