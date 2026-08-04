from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class NewsOut(BaseModel):
    """Representação pública de uma notícia (sem imagem, por decisão de produto)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    city: str
    reg_code: str
    title: str
    date: datetime
    link: str
    description: str | None = None


class NewsBlock(BaseModel):
    """Bloco usado na home: destaques, laterais e ticker."""

    main: list[NewsOut]
    side: list[NewsOut]
    roller: list[NewsOut]
    more: list[NewsOut]

"""
class SectorBlock(BaseModel):
    south: list[NewsOut]
    center: list[NewsOut]
    north: list[NewsOut]
    west: list[NewsOut]
    montain: list[NewsOut]
    valley: list[NewsOut]
"""

class CityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str


class StarCityOut(BaseModel):
    city_name: str | None
    city_news: list[NewsOut]


class AccessIn(BaseModel):
    news_id: int
    type: str = Field(default="", max_length=30)


class NewsletterIn(BaseModel):
    mail: EmailStr


class MessageOut(BaseModel):
    result: bool
    message: str
