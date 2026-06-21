from dataclasses import dataclass
from datetime import date, timedelta

from application.ports.asset_repository import AssetRepository
from application.ports.market_data_client import MarketDataClient
from application.ports.price_repository import PriceRepository
from infrastructure.cache.redis_service import AsyncRedisCacheService


@dataclass
class SyncResult:
    calls_consumed: int
    rows_inserted:  int
    action:         str


class SyncAssetData:

    HISTORICAL_DAYS = 2740

    def __init__(
        self,
        asset_repo:    AssetRepository,
        price_repo:    PriceRepository,
        market_client: MarketDataClient,
        cache_service: AsyncRedisCacheService,
    ) -> None:
        self._assets  = asset_repo
        self._prices  = price_repo
        self._client  = market_client
        self._cache   = cache_service

    async def execute_new_symbol(self, symbol: str) -> SyncResult:
        if await self._rate_limited():
            return SyncResult(0, 0, "rate_limited")

        existing = await self._assets.find_by_symbol(symbol)
        if existing is not None:
            asset = existing
            calls_metadata = 0
        else:
            asset = await self._client.fetch_asset_metadata(symbol)
            if asset is None:
                return SyncResult(0, 0, "skipped")
            await self._tick_rate_limit()
            asset = await self._assets.save(asset)
            calls_metadata = 1

            if await self._rate_limited():
                return SyncResult(1, 0, "new_asset")

        today = date.today()
        from_date = date(2004, 1, 1)
        prices = await self._client.fetch_daily_prices(symbol, from_date, today)

        await self._tick_rate_limit()

        if not prices:
            return SyncResult(1 + calls_metadata, 0, "new_asset")

        prices_with_id = [p.model_copy(update={"asset_id": asset.id}) for p in prices]
        rows = await self._prices.save_batch(prices_with_id)
        return SyncResult(1 + calls_metadata, rows, "new_asset")

    async def execute_existing_asset(self, asset_id: int, symbol: str) -> SyncResult:
        lock_key = f"lock:asset:{asset_id}"
        if not await self._cache.acquire_lock(lock_key, expire_seconds=60):
            return SyncResult(0, 0, "skipped")

        try:
            if await self._rate_limited():
                return SyncResult(0, 0, "rate_limited")

            today = date.today()
            last_date = await self._prices.find_last_price_date(asset_id)

            if last_date is None:
                from_date = today - timedelta(days=self.HISTORICAL_DAYS)
            elif last_date >= today:
                return SyncResult(0, 0, "skipped")
            else:
                from_date = last_date + timedelta(days=1)

            prices = await self._client.fetch_daily_prices(symbol, from_date, today)
            await self._tick_rate_limit()

            if not prices:
                return SyncResult(1, 0, "updated")

            prices_with_id = [p.model_copy(update={"asset_id": asset_id}) for p in prices]
            rows = await self._prices.save_batch(prices_with_id)
            return SyncResult(1, rows, "updated")
        finally:
            await self._cache.release_lock(lock_key)

    async def _rate_limited(self) -> bool:
        hour_used = await self._cache.get_counter("rate_limit:hour_counter")
        day_used  = await self._cache.get_counter("rate_limit:day_counter")
        return hour_used >= 50 or day_used >= 1000

    async def _tick_rate_limit(self) -> None:
        await self._cache.increment_counter("rate_limit:hour_counter", expire_seconds=3600)
        await self._cache.increment_counter("rate_limit:day_counter", expire_seconds=86400)
