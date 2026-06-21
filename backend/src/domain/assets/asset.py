from pydantic import BaseModel, field_validator
from .asset_type import AssetType


class Asset(BaseModel):
    id:            int | None = None   # None hasta que la BD asigne el id
    symbol:        str
    name:          str
    asset_type:    AssetType
    currency:      str = "USD"
    exchange:      str | None = None
    timezone:      str = "America/New_York"

    model_config = {"frozen": True}   # entidades inmutables: el dominio no muta estado

    @field_validator("symbol")
    @classmethod
    def symbol_must_be_uppercase(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("symbol no puede estar vacío")
        return v

    @field_validator("currency")
    @classmethod
    def currency_must_be_uppercase(cls, v: str) -> str:
        return v.strip().upper()