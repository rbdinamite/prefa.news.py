from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class NewsOut(BaseModel):
    """Public presentation of a news item."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    city: str
    reg_code: str
    title: str
    date: datetime
    link: str
    description: str | None = None


class NewsBlock(BaseModel):
    """Block used on the home page."""

    main: list[NewsOut]
    side: list[NewsOut]
    roller: list[NewsOut]
    more: list[NewsOut]


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
