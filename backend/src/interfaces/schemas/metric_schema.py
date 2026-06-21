from datetime import datetime
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class CorrelationPoint(BaseModel):
    time: datetime
    value: Decimal


class CorrelationSeriesResponse(BaseModel):
    base_symbol: str
    risk_symbol: str
    window_days: int
    series: list[CorrelationPoint]


class CoverageGapSchema(BaseModel):
    start: date
    end: date
    days: int


class CoverageItemSchema(BaseModel):
    symbol: str
    expected_days: int
    available_days: int
    coverage_pct: float
    missing_days: int
    first_date: date
    last_date: date
    freshness_lag_days: int
    record_count: int
    gaps: list[CoverageGapSchema]


class CoverageSummarySchema(BaseModel):
    symbols_count: int
    coverage_pct_avg: float
    symbols_below_threshold: int
    threshold_pct: float


class CoverageResponse(BaseModel):
    summary: CoverageSummarySchema
    items: list[CoverageItemSchema]


class CoverageCalendarDaySchema(BaseModel):
    date: date
    actual_count: int
    expected_count: int
    is_weekend: bool


class CoverageCalendarResponse(BaseModel):
    from_date: date
    to_date: date
    total_assets: int
    days: list[CoverageCalendarDaySchema]


class VolatilityPoint(BaseModel):
    time: datetime
    value: Decimal


class VolatilityResponse(BaseModel):
    symbol: str
    window_days: int
    series: list[VolatilityPoint]


class CorrelationMatrixResponse(BaseModel):
    symbols: list[str]
    matrix: list[list[float]]


class CorrelationRequest(BaseModel):
    from_date: date | None = None
    to_date: date | None = None


class CorrelationResponse(BaseModel):
    metrics_inserted: int
    pairs_processed: int
    missing_risk_symbols: list[str]


class CorrelatePairResponse(BaseModel):
    metrics_inserted: int
    pairs_processed: int


class CorrelatePairRequest(BaseModel):
    base_symbol: str
    target_symbol: str
    from_date: date | None = None
    to_date: date | None = None
