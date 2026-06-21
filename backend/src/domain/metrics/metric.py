from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator


VALID_METRICS = {
    "correlation_30d",
    "correlation_90d",
    "beta",
    "volatility_annualized",
    "var_95_1d",
}


class AnalyticalMetric(BaseModel):
    time:                 datetime
    base_asset_id:        int
    comparison_asset_id:  int | None = None
    metric_name:          str
    window_days:          int
    metric_value:         Decimal
    calculated_at:        datetime | None = None

    model_config = {"frozen": True}

    @field_validator("metric_name")
    @classmethod
    def metric_name_must_be_known(cls, v: str) -> str:
        if v not in VALID_METRICS:
            raise ValueError(
                f"metric_name '{v}' desconocida. Válidas: {VALID_METRICS}"
            )
        return v

    @field_validator("window_days")
    @classmethod
    def window_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("window_days debe ser mayor que cero")
        return v