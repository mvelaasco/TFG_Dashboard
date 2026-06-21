from pydantic import BaseModel
from domain.assets.asset_type import AssetType


class AssetResponse(BaseModel):
    id:         int
    symbol:     str
    name:       str
    asset_type: AssetType
    currency:   str
    exchange:   str | None
    timezone:   str

    model_config = {"from_attributes": True}