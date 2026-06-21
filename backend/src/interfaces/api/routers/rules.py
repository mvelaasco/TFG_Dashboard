from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db_session import get_session
from infrastructure.db.models.rule_model import RuleModel
from infrastructure.db.models.weekly_price_model import WeeklyPriceModel
from interfaces.schemas.rule_schema import RuleResponse, WeeklyPriceResponse

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=list[RuleResponse])
async def list_rules(
    session: AsyncSession = Depends(get_session),
) -> list[RuleResponse]:
    """Devuelve todas las reglas de asociación almacenadas."""
    result = await session.execute(
        select(RuleModel).order_by(RuleModel.confidence.desc())
    )
    return [RuleResponse.model_validate(r) for r in result.scalars().all()]


@router.get("/weekly-prices", response_model=list[WeeklyPriceResponse])
async def get_weekly_prices(
    symbols: str = Query(..., description="Símbolos separados por coma (máx 5)"),
    from_date: date | None = Query(default=None, description="Fecha inicio YYYY-MM-DD"),
    to_date: date | None = Query(default=None, description="Fecha fin YYYY-MM-DD"),
    session: AsyncSession = Depends(get_session),
) -> list[WeeklyPriceResponse]:
    """Devuelve pct_change semanal para los símbolos indicados."""
    symbol_list = [s.strip().upper() for s in symbols.split(",")][:5]

    query = select(WeeklyPriceModel).where(
        WeeklyPriceModel.symbol.in_(symbol_list),
        WeeklyPriceModel.pct_change.isnot(None),
    )
    if from_date:
        query = query.where(WeeklyPriceModel.week_start >= from_date)
    if to_date:
        query = query.where(WeeklyPriceModel.week_start <= to_date)
    query = query.order_by(WeeklyPriceModel.symbol, WeeklyPriceModel.week_start)

    result = await session.execute(query)

    return [
        WeeklyPriceResponse(
            week_start=w.week_start.isoformat(),
            symbol=w.symbol,
            pct_change=float(w.pct_change) if w.pct_change is not None else None,
        )
        for w in result.scalars().all()
    ]
