"""
Modelos ORM equivalentes às tabelas usadas na versão PHP original:
city, news, access, newsletter, highlight_news.

Mantivemos os nomes de campo próximos aos originais para facilitar a
migração de dados de bd.db (SQLite antigo) para o novo banco, mas os
tipos agora são fortemente tipados e as constraints (FK, unique, index)
que faltavam no schema original foram adicionadas.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

"""
class Region:    

    SUL = "SUL"
    GRANDE_FLORIPA = "GRANDE FLORIPA"
    NORTE = "NORTE"
    OESTE = "OESTE"
    SERRANA = "SERRANA"
    VALE = "VALE"

    ALL = [SUL, GRANDE_FLORIPA, NORTE, OESTE, SERRANA, VALE]
"""

class FeedType:
    """Equivalente à coluna city.url_type."""

    IPM = "IPM"
    FECAM2 = "FECAM2"
    P1 = "P1"
    PROPRIO = "PROPRIO"  # site com layout próprio, sem RSS padrão (não é ingerido automaticamente)


class City(Base):
    __tablename__ = "city"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    #regiao: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    url_type: Mapped[str] = mapped_column(String(20), nullable=False, default=FeedType.PROPRIO)
    url_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    instagram: Mapped[str | None] = mapped_column(String(120), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    lastcheck_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    lastnews_date: Mapped[str | None] = mapped_column(String(10), nullable=True)

    news: Mapped[list["News"]] = relationship(back_populates="city")

    def __repr__(self) -> str:
        return f"<City {self.id} {self.name}>"


class News(Base):
    __tablename__ = "news"
    __table_args__ = (
        UniqueConstraint("city_id", "date", "title", name="uq_news_city_date_title"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("city.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    news_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    img_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    pub_instagram: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    city: Mapped["City"] = relationship(back_populates="news")

    def __repr__(self) -> str:
        return f"<News {self.id} {self.title[:30]!r}>"


class Access(Base):
    """Registra cliques em notícias (equivalente à tabela access)."""

    __tablename__ = "access"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    news_id: Mapped[int] = mapped_column(ForeignKey("news.id"), nullable=False, index=True)
    type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    server: Mapped[str | None] = mapped_column(Text, nullable=True)  # metadados da requisição (JSON)


class Newsletter(Base):
    __tablename__ = "newsletter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mail: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    create_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class HighlightNews(Base):
    """Destaques (do dia / semana), equivalente à tabela highlight_news."""

    __tablename__ = "highlight_news"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    news_id: Mapped[int] = mapped_column(ForeignKey("news.id"), nullable=False, index=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    type: Mapped[str] = mapped_column(String(20), default="portal", nullable=False)  # portal | feed | reels
