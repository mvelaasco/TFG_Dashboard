from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class PriceResponse(BaseModel):
    time:     datetime
    asset_id: int
    open:     Decimal | None
    high:     Decimal | None
    low:      Decimal | None
    close:    Decimal
    volume:   int | None

    model_config = {"from_attributes": True}