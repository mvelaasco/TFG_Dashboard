import pytest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from application.ports.asset_repository import AssetRepository
from application.ports.market_data_client import MarketDataClient
from application.ports.price_repository import PriceRepository
from application.use_cases.sync_asset_data import SyncAssetData
from domain.assets.asset import Asset
from domain.assets.asset_type import AssetType
from domain.prices.price import Price


class FakeCacheService:
    """In-memory implementation of AsyncRedisCacheService interface."""

    def __init__(self):
        self._counters: dict[str, int] = {}
        self._locks: set[str] = set()

    async def acquire_lock(self, key: str, expire_seconds: int = 60) -> bool:
        if key in self._locks:
            return False
        self._locks.add(key)
        return True

    async def release_lock(self, key: str) -> None:
        self._locks.discard(key)

    async def increment_counter(self, key: str, expire_seconds: int = 3600) -> int:
        val = self._counters.get(key, 0) + 1
        self._counters[key] = val
        return val

    async def get_counter(self, key: str) -> int:
        return self._counters.get(key, 0)

    async def close(self) -> None:
        pass


class InMemoryAssetRepository(AssetRepository):
    def __init__(self):
        self._store: dict[str, Asset] = {}
        self._next_id = 1

    async def save(self, asset: Asset) -> Asset:
        saved = asset.model_copy(update={"id": self._next_id})
        self._next_id += 1
        self._store[saved.symbol] = saved
        return saved

    async def find_by_symbol(self, symbol: str) -> Asset | None:
        return self._store.get(symbol.upper())

    async def find_all(self) -> list[Asset]:
        return list(self._store.values())

    async def delete_by_symbol(self, symbol: str) -> bool:
        return self._store.pop(symbol.upper(), None) is not None

    async def find_all_with_price_stats(self) -> list[tuple[Asset, date | None, int]]:
        return [(a, None, 0) for a in self._store.values()]


class InMemoryPriceRepository(PriceRepository):
    def __init__(self):
        self._store: list[Price] = []

    async def save_batch(self, prices: list[Price]) -> int:
        self._store.extend(prices)
        return len(prices)

    async def find_by_asset(self, asset_id, from_time, to_time) -> list[Price]:
        return sorted(
            [p for p in self._store if p.asset_id == asset_id and from_time <= p.time <= to_time],
            key=lambda p: p.time,
        )

    async def find_latest(self, asset_id: int) -> Price | None:
        candidates = [p for p in self._store if p.asset_id == asset_id]
        return max(candidates, key=lambda p: p.time) if candidates else None

    async def find_date_range(self, asset_id: int) -> tuple[date | None, date | None]:
        candidates = [p for p in self._store if p.asset_id == asset_id]
        if not candidates:
            return None, None
        dates = [p.time.date() for p in candidates]
        return min(dates), max(dates)

    async def find_distinct_dates(self, asset_id, from_date, to_date) -> list[date]:
        return sorted({
            p.time.date()
            for p in self._store
            if p.asset_id == asset_id and from_date <= p.time.date() <= to_date
        })

    async def find_last_price_date(self, asset_id: int) -> date | None:
        candidates = [p for p in self._store if p.asset_id == asset_id]
        if not candidates:
            return None
        return max(p.time.date() for p in candidates)

    async def count_by_asset(self, asset_id: int) -> int:
        return sum(1 for p in self._store if p.asset_id == asset_id)


class StubMarketClient(MarketDataClient):
    def __init__(self):
        self.metadata: dict[str, Asset | None] = {}
        self.prices: dict[str, list[Price]] = {}

    async def fetch_asset_metadata(self, symbol: str) -> Asset | None:
        return self.metadata.get(symbol.upper())

    async def fetch_daily_prices(self, symbol: str, from_date: date, to_date: date) -> list[Price]:
        return self.prices.get(symbol.upper(), [])

    def add_asset(self, symbol: str):
        self.metadata[symbol.upper()] = Asset(
            symbol=symbol.upper(),
            name=f"{symbol.upper()} Inc.",
            asset_type=AssetType.STOCK,
            currency="USD",
            exchange="NASDAQ",
        )


def _price(asset_id: int, day: date, close: str) -> Price:
    return Price(
        time=datetime(day.year, day.month, day.day, 21, 0, 0, tzinfo=timezone.utc),
        asset_id=asset_id,
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=1_000_000,
    )


@pytest.fixture
def repos():
    return InMemoryAssetRepository(), InMemoryPriceRepository(), FakeCacheService(), StubMarketClient()


# --- execute_new_symbol ---

async def test_new_symbol_creates_asset_and_saves_prices(repos):
    """New symbol should fetch metadata + prices and persist both."""
    asset_repo, price_repo, cache, client = repos
    client.add_asset("AAPL")
    client.prices["AAPL"] = [_price(0, date.today() - timedelta(days=i), "185") for i in range(5)]

    uc = SyncAssetData(asset_repo, price_repo, client, cache)
    result = await uc.execute_new_symbol("AAPL")
    assert result.action == "new_asset"
    assert result.calls_consumed == 2  # metadata + prices
    assert result.rows_inserted == 5

    saved = await asset_repo.find_by_symbol("AAPL")
    assert saved is not None


async def test_new_symbol_metadata_not_found(repos):
    """Symbol not in external source → skipped."""
    asset_repo, price_repo, cache, client = repos
    uc = SyncAssetData(asset_repo, price_repo, client, cache)
    result = await uc.execute_new_symbol("FAKE")
    assert result.action == "skipped"
    assert result.calls_consumed == 0


async def test_new_symbol_rate_limited(repos):
    """Rate limit hit → rate_limited result."""
    asset_repo, price_repo, cache, client = repos
    for _ in range(50):
        await cache.increment_counter("rate_limit:hour_counter")

    uc = SyncAssetData(asset_repo, price_repo, client, cache)
    result = await uc.execute_new_symbol("AAPL")
    assert result.action == "rate_limited"
    assert result.calls_consumed == 0


async def test_new_symbol_existing_asset_skips_metadata_fetch(repos):
    """If asset already in DB, skip metadata call and go straight to prices."""
    asset_repo, price_repo, cache, client = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    client.prices["AAPL"] = [_price(0, date.today() - timedelta(days=i), "185") for i in range(3)]

    uc = SyncAssetData(asset_repo, price_repo, client, cache)
    result = await uc.execute_new_symbol("AAPL")
    assert result.action == "new_asset"
    assert result.calls_consumed == 1
    assert result.rows_inserted == 3


async def test_new_symbol_no_prices(repos):
    """Symbol found but no prices returned → rows_inserted=0."""
    asset_repo, price_repo, cache, client = repos
    client.add_asset("EMPTY")

    uc = SyncAssetData(asset_repo, price_repo, client, cache)
    result = await uc.execute_new_symbol("EMPTY")
    assert result.action == "new_asset"
    assert result.rows_inserted == 0


async def test_new_symbol_hour_limit_exceeded_after_metadata(repos):
    """After metadata fetch, hour limit hit → stop with new_asset action."""
    asset_repo, price_repo, cache, client = repos
    client.add_asset("AAPL")

    uc = SyncAssetData(asset_repo, price_repo, client, cache)
    # Set hour counter to 49 before call, so metadata fetch pushes it to 50
    for _ in range(49):
        await cache.increment_counter("rate_limit:hour_counter")

    result = await uc.execute_new_symbol("AAPL")
    assert result.action == "new_asset"
    assert result.calls_consumed == 1
    assert result.rows_inserted == 0


# --- execute_existing_asset ---

async def test_existing_asset_incremental_update(repos):
    """Existing asset with no previous prices → fetches from historical."""
    asset_repo, price_repo, cache, client = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    client.prices["AAPL"] = [_price(0, date.today() - timedelta(days=i), "185") for i in range(5)]

    uc = SyncAssetData(asset_repo, price_repo, client, cache)
    result = await uc.execute_existing_asset(aapl.id, "AAPL")
    assert result.action == "updated"
    assert result.calls_consumed == 1
    assert result.rows_inserted == 5


async def test_existing_asset_lock_skipped(repos):
    """If lock can't be acquired → skipped."""
    asset_repo, price_repo, cache, client = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    await cache.acquire_lock(f"lock:asset:{aapl.id}")

    uc = SyncAssetData(asset_repo, price_repo, client, cache)
    result = await uc.execute_existing_asset(aapl.id, "AAPL")
    assert result.action == "skipped"
    assert result.rows_inserted == 0


async def test_existing_asset_rate_limited(repos):
    """Rate limit hit before fetching → rate_limited."""
    asset_repo, price_repo, cache, client = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    for _ in range(50):
        await cache.increment_counter("rate_limit:hour_counter")

    uc = SyncAssetData(asset_repo, price_repo, client, cache)
    result = await uc.execute_existing_asset(aapl.id, "AAPL")
    assert result.action == "rate_limited"
    assert result.rows_inserted == 0


async def test_existing_asset_up_to_date_skipped(repos):
    """If last_date >= today, skip."""
    asset_repo, price_repo, cache, client = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    today = date.today()
    await price_repo.save_batch([_price(aapl.id, today, "185")])

    uc = SyncAssetData(asset_repo, price_repo, client, cache)
    result = await uc.execute_existing_asset(aapl.id, "AAPL")
    assert result.action == "skipped"
    assert result.rows_inserted == 0


async def test_existing_asset_no_new_prices(repos):
    """No prices from client → rows_inserted=0."""
    asset_repo, price_repo, cache, client = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    old_date = date.today() - timedelta(days=10)
    await price_repo.save_batch([_price(aapl.id, old_date, "185")])

    uc = SyncAssetData(asset_repo, price_repo, client, cache)
    result = await uc.execute_existing_asset(aapl.id, "AAPL")
    assert result.action == "updated"
    assert result.rows_inserted == 0


async def test_existing_asset_lock_released(repos):
    """Lock should be released after sync even on failure."""
    asset_repo, price_repo, cache, client = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))

    uc = SyncAssetData(asset_repo, price_repo, client, cache)
    await uc.execute_existing_asset(aapl.id, "AAPL")

    # Lock should be released — acquiring again should work
    assert await cache.acquire_lock(f"lock:asset:{aapl.id}")
