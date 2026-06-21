from pydantic import BaseModel, field_validator


class CreateAssetRequest(BaseModel):
    symbol: str
    name: str
    asset_type: str = "stock"
    currency: str = "USD"
    exchange: str | None = None

    @field_validator("symbol")
    @classmethod
    def symbol_must_be_uppercase(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("asset_type")
    @classmethod
    def validate_asset_type(cls, v: str) -> str:
        valid = {"stock", "etf", "crypto", "index", "fx"}
        if v.lower() not in valid:
            raise ValueError(f"asset_type debe ser uno de: {', '.join(sorted(valid))}")
        return v.lower()


class EnqueueSymbolRequest(BaseModel):
    symbol: str
    asset_type: str = "stock"

    @field_validator("symbol")
    @classmethod
    def symbol_must_be_uppercase(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("asset_type")
    @classmethod
    def validate_asset_type(cls, v: str) -> str:
        valid = {"stock", "etf", "crypto", "index", "fx"}
        if v.lower() not in valid:
            raise ValueError(f"asset_type debe ser uno de: {', '.join(sorted(valid))}")
        return v.lower()


class IngestResult(BaseModel):
    symbol: str
    rows_inserted: int
    status: str  # "ok" | "error"
    detail: str = ""
