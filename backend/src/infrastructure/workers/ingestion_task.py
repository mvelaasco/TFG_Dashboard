import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.celery_app import celery_app
from core.config import settings
from application.use_cases.sync_asset_data import SyncAssetData
from infrastructure.cache.redis_service import AsyncRedisCacheService
from infrastructure.db.repositories.pg_asset_repository import PgAssetRepository
from infrastructure.db.repositories.pg_pending_asset_repository import PgPendingAssetRepository
from infrastructure.db.repositories.pg_price_repository import PgPriceRepository
from infrastructure.external_apis.tiingo_client import TiingoClient

logger = logging.getLogger(__name__)


@celery_app.task
def hourly_ingestion() -> dict:
    return asyncio.run(_run_hourly_ingestion())


async def _run_hourly_ingestion() -> dict:
    engine = create_async_engine(settings.db_url, pool_size=2, max_overflow=2)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    summary = {"new_symbols": 0, "updated": 0, "skipped": 0, "rate_limited": 0, "calls_used": 0}

    async with session_factory() as session:
        asset_repo   = PgAssetRepository(session)
        price_repo   = PgPriceRepository(session)
        pending_repo = PgPendingAssetRepository(session)
        cache        = AsyncRedisCacheService()

        sync = SyncAssetData(asset_repo, price_repo, TiingoClient(), cache)

        remaining = 50 - await cache.get_counter("rate_limit:hour_counter")
        remaining = max(remaining, 0)

        if remaining >= 2:
            pending = await pending_repo.dequeue()
            if pending is not None:
                symbol = pending[0]
                try:
                    result = await sync.execute_new_symbol(symbol)
                    summary["calls_used"] += result.calls_consumed
                    remaining -= result.calls_consumed
                    if result.action in ("new_asset",):
                        await pending_repo.mark(symbol, "done")
                    else:
                        await pending_repo.mark(symbol, "failed")
                    summary["new_symbols"] += 1
                    await session.commit()
                except Exception:
                    logger.exception("Error procesando nuevo símbolo %s", symbol)
                    await session.rollback()
                    try:
                        await pending_repo.mark(symbol, "failed")
                        await session.commit()
                    except Exception:
                        await session.rollback()

        if remaining > 0:
            assets = await asset_repo.find_all_with_price_stats()
            for asset, _last_date, _count in assets:
                if remaining <= 0:
                    break
                try:
                    result = await sync.execute_existing_asset(asset.id, asset.symbol)
                    summary["calls_used"] += result.calls_consumed
                    remaining -= result.calls_consumed
                    if result.action == "updated":
                        summary["updated"] += 1
                    elif result.action == "rate_limited":
                        summary["rate_limited"] += 1
                    else:
                        summary["skipped"] += 1
                    await session.commit()
                except Exception:
                    logger.exception("Error actualizando %s", asset.symbol)
                    await session.rollback()
                    summary["skipped"] += 1

    await engine.dispose()
    logger.info("Ingesta completada: %s", summary)
    return summary
