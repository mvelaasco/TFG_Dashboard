from datetime import date, datetime

from pydantic import BaseModel


class NewsItemResponse(BaseModel):
    id: int | None
    symbol: str
    date: date
    datetime: datetime
    headline: str
    source: str | None
    url: str | None
    summary: str | None

    model_config = {"from_attributes": True}
