from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from application.use_cases.ingest_prices import IngestPrices, IngestPricesRequest
from core.db_session import get_session
from domain.assets.asset import Asset
from domain.assets.asset_type import AssetType
from infrastructure.auth.dependencies import require_admin
from infrastructure.db.repositories.pg_asset_repository import PgAssetRepository
from infrastructure.db.repositories.pg_price_repository import PgPriceRepository
from infrastructure.external_apis.tiingo_client import TiingoClient
from infrastructure.db.repositories.pg_pending_asset_repository import PgPendingAssetRepository
from infrastructure.workers.ingestion_task import hourly_ingestion
from interfaces.schemas.admin_schema import CreateAssetRequest, EnqueueSymbolRequest, IngestResult
from interfaces.schemas.asset_schema import AssetResponse

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/ingest", response_model=list[IngestResult])
async def ingest_all(
    session: AsyncSession = Depends(get_session),
) -> list[IngestResult]:
#inyecciones de dependencias manuales, podrían ser reemplazadas por un contenedor de dependencias
    asset_repo = PgAssetRepository(session)
    price_repo = PgPriceRepository(session)
    client = TiingoClient()
    use_case = IngestPrices(asset_repo, price_repo, client)

    assets = await asset_repo.find_all()
    if not assets:
        raise HTTPException(status_code=400, detail="No hay activos en la base de datos")

    today = date.today()
    from_date = date(2022, 1, 1)
    results: list[IngestResult] = []

    for asset in assets:
        try:
            req = IngestPricesRequest(symbol=asset.symbol, from_date=from_date, to_date=today)
            result = await use_case.execute(req)
            results.append(IngestResult(
                symbol=result.symbol,
                rows_inserted=result.rows_inserted,
                status="ok",
                detail="Nuevo" if not result.already_existed else "Existente",
            ))
        except Exception as e:
            results.append(IngestResult(
                symbol=asset.symbol, rows_inserted=0, status="error", detail=str(e),
            ))

    return results


@router.post("/assets", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    body: CreateAssetRequest,
    session: AsyncSession = Depends(get_session),
    
) -> AssetResponse:
    repo = PgAssetRepository(session)

    existing = await repo.find_by_symbol(body.symbol)
    if existing:
        raise HTTPException(status_code=409, detail=f"El activo '{body.symbol}' ya existe")

    asset = Asset(
        symbol=body.symbol,
        name=body.name,
        asset_type=AssetType(body.asset_type),
        currency=body.currency.upper(),
        exchange=body.exchange,
    )
    created = await repo.save(asset)
    return AssetResponse(**created.model_dump())


@router.post("/enqueue", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_symbol(
    body: EnqueueSymbolRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    repo = PgPendingAssetRepository(session)
    await repo.enqueue(body.symbol, name=None, asset_type=body.asset_type)
    try:
        hourly_ingestion.delay()
    except Exception:
        pass
    return {"status": "queued", "symbol": body.symbol}


@router.delete("/assets/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    symbol: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    repo = PgAssetRepository(session)
    deleted = await repo.delete_by_symbol(symbol)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Activo '{symbol}' no encontrado")
