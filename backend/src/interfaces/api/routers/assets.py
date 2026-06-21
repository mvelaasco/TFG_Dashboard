from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.db_session import get_session
from infrastructure.db.repositories.pg_asset_repository import PgAssetRepository
from infrastructure.db.repositories.pg_price_repository import PgPriceRepository
from interfaces.schemas.asset_schema import AssetResponse
from interfaces.schemas.price_schema import PriceResponse

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[AssetResponse])
async def list_assets(
    session: AsyncSession = Depends(get_session),
) -> list[AssetResponse]:
#inyecciones de dependencias manuales, podrían ser reemplazadas por un contenedor de dependencias
    """Lista todos los activos disponibles en la base de datos."""
    repo = PgAssetRepository(session)
    assets = await repo.find_all()
    return [AssetResponse(**a.model_dump()) for a in assets]


@router.get("/{symbol}/prices", response_model=list[PriceResponse])
async def get_prices(
    symbol:     str,
    from_date:  date = Query(default=date(2022, 1, 1), description="Fecha inicio YYYY-MM-DD"),
    to_date:    date = Query(default=date.today(),     description="Fecha fin YYYY-MM-DD"),
    session:    AsyncSession = Depends(get_session),
) -> list[PriceResponse]:
    """
    Devuelve la serie temporal de precios OHLCV de un activo
    en el rango de fechas indicado, ordenada de más antiguo a más reciente.
    """
    from datetime import datetime, timezone

    asset_repo = PgAssetRepository(session)
    price_repo = PgPriceRepository(session)

    asset = await asset_repo.find_by_symbol(symbol)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Activo '{symbol}' no encontrado")

    from_time = datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc)
    to_time   = datetime(to_date.year,   to_date.month,   to_date.day, 23, 59, 59, tzinfo=timezone.utc)

    prices = await price_repo.find_by_asset(asset.id, from_time, to_time)
    return [PriceResponse(**p.model_dump()) for p in prices]


@router.get("/{symbol}/prices/latest", response_model=PriceResponse)
async def get_latest_price(
    symbol:  str,
    session: AsyncSession = Depends(get_session),
) -> PriceResponse:
    """Devuelve el precio de cierre más reciente disponible para un activo."""
    asset_repo = PgAssetRepository(session)
    price_repo = PgPriceRepository(session)

    asset = await asset_repo.find_by_symbol(symbol)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Activo '{symbol}' no encontrado")

    price = await price_repo.find_latest(asset.id)
    if price is None:
        raise HTTPException(status_code=404, detail=f"No hay precios para '{symbol}'")

    return PriceResponse(**price.model_dump())