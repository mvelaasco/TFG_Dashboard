from datetime import date, datetime, timezone

from pydantic import BaseModel, field_validator


class NewsItem(BaseModel):
    id: int | None = None
    symbol: str
    date: date
    datetime: datetime
    headline: str
    source: str | None = None
    url: str | None = None
    summary: str | None = None

    model_config = {"frozen": True}

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("datetime")
    @classmethod
    def datetime_must_be_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("datetime debe incluir zona horaria")
        return v.astimezone(timezone.utc)
