from pydantic import BaseModel


class RuleResponse(BaseModel):
    id: int
    antecedent: str
    consequent: str
    support: float | None = None
    confidence: float | None = None
    lift: float | None = None
    coverage: float | None = None
    amplitude: float | None = None
    netconf: float | None = None

    model_config = {"from_attributes": True}


class WeeklyPriceResponse(BaseModel):
    week_start: str
    symbol: str
    pct_change: float | None = None
