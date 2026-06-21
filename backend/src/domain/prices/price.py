from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, field_validator, model_validator


class Price(BaseModel):
    time:     datetime
    asset_id: int
    open:     Decimal | None = None
    high:     Decimal | None = None
    low:      Decimal | None = None
    close:    Decimal
    volume:   int | None = None

    model_config = {"frozen": True}

    @field_validator("time")
    @classmethod
    def time_must_be_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("time debe incluir zona horaria")
        return v.astimezone(timezone.utc)

    @model_validator(mode="after")
    def ohlc_coherence(self) -> "Price":
        if self.high is not None and self.low is not None:
            if self.high < self.low:
                raise ValueError(f"high ({self.high}) no puede ser menor que low ({self.low})")
        if self.open is not None and self.high is not None:
            if self.open > self.high:
                raise ValueError(f"open ({self.open}) no puede superar high ({self.high})")
        if self.close is not None and self.close <= 0:
            raise ValueError(f"close ({self.close}) debe ser positivo")
        if self.open is not None and self.open <= 0:
            raise ValueError(f"open ({self.open}) debe ser positivo")
        if self.high is not None and self.high <= 0:
            raise ValueError(f"high ({self.high}) debe ser positivo")
        if self.low is not None and self.low <= 0:
            raise ValueError(f"low ({self.low}) debe ser positivo")
        if self.volume is not None and self.volume < 0:
            raise ValueError(f"volume ({self.volume}) no puede ser negativo")
        return self