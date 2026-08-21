"""
ORM models equivalent to the tables used in the original PHP version.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FeedType:
    """Equivalent to the city.url_type column."""

    IPM = "IPM"
    FECAM = "FECAM"
    PROPRIO = "PROPRIO"  # site with proprietary layout, no standard RSS feed (not automatically ingested)


class City(Base):
    __tablename__ = "city"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
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
    title_pt: Mapped[str] = mapped_column(String(500), nullable=True)    
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
    """Registers clicks on news."""

    __tablename__ = "access"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    news_id: Mapped[int] = mapped_column(ForeignKey("news.id"), nullable=False, index=True)
    type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    server: Mapped[str | None] = mapped_column(Text, nullable=True)  # request metadata (JSON)


class Newsletter(Base):
    __tablename__ = "newsletter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mail: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    create_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class HighlightNews(Base):
    """Highlights (of the day / week)."""

    __tablename__ = "highlight_news"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    news_id: Mapped[int] = mapped_column(ForeignKey("news.id"), nullable=False, index=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    type: Mapped[str] = mapped_column(String(20), default="portal", nullable=False)  # portal | feed | reels


class Insight(Base):
    """AI-generated patterns shared by news from multiple cities."""

    __tablename__ = "insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    cities: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    news_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
