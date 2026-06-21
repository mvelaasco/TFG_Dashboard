import pytest
from datetime import date, datetime, timezone
from decimal import Decimal

from application.ports.asset_repository import AssetRepository
from application.ports.price_repository import PriceRepository
from application.use_cases.compute_volatility import (
    ComputeVolatility,
    VolatilityRequest,
    VolatilityPoint,
)
from domain.assets.asset import Asset
from domain.assets.asset_type import AssetType
from domain.prices.price import Price


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
    return InMemoryAssetRepository(), InMemoryPriceRepository()


async def test_volatility_computed_correctly(repos):
    """With enough prices, volatility should be a positive float."""
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    for i in range(30):
        await price_repo.save_batch([_price(aapl.id, date(2024, 1, i + 1), str(100 + i))])

    uc = ComputeVolatility(asset_repo, price_repo)
    result = await uc.execute(VolatilityRequest(symbol="AAPL", window_days=5))
    assert result.symbol == "AAPL"
    assert result.window_days == 5
    assert len(result.series) > 0
    for pt in result.series:
        assert isinstance(pt, VolatilityPoint)
        assert pt.value > 0


async def test_insufficient_prices_returns_empty_series(repos):
    """Fewer prices than window+1 should return empty series."""
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    for i in range(3):
        await price_repo.save_batch([_price(aapl.id, date(2024, 1, i + 1), "100")])

    uc = ComputeVolatility(asset_repo, price_repo)
    result = await uc.execute(VolatilityRequest(symbol="AAPL", window_days=10))
    assert len(result.series) == 0


async def test_symbol_not_found_raises(repos):
    asset_repo, price_repo = repos
    uc = ComputeVolatility(asset_repo, price_repo)
    with pytest.raises(ValueError, match="no encontrado"):
        await uc.execute(VolatilityRequest(symbol="NONEXIST"))


async def test_constant_prices_zero_volatility(repos):
    """If all prices are identical, volatility is ~0."""
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    for i in range(30):
        await price_repo.save_batch([_price(aapl.id, date(2024, 1, i + 1), "100")])

    uc = ComputeVolatility(asset_repo, price_repo)
    result = await uc.execute(VolatilityRequest(symbol="AAPL", window_days=5))
    assert len(result.series) > 0
    for pt in result.series:
        assert pt.value == Decimal("0")


async def test_symbol_normalized_to_uppercase(repos):
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    for i in range(30):
        await price_repo.save_batch([_price(aapl.id, date(2024, 1, i + 1), str(100 + i))])

    uc = ComputeVolatility(asset_repo, price_repo)
    result = await uc.execute(VolatilityRequest(symbol="aapl", window_days=5))
    assert result.symbol == "AAPL"


async def test_window_size_affects_series_length(repos):
    """Larger window yields fewer volatility points."""
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    for i in range(30):
        await price_repo.save_batch([_price(aapl.id, date(2024, 1, i + 1), str(100 + i))])

    uc = ComputeVolatility(asset_repo, price_repo)
    r5 = await uc.execute(VolatilityRequest(symbol="AAPL", window_days=5))
    r20 = await uc.execute(VolatilityRequest(symbol="AAPL", window_days=20))
    assert len(r5.series) > len(r20.series)


async def test_to_date_truncates_series(repos):
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    for i in range(30):
        await price_repo.save_batch([_price(aapl.id, date(2024, 1, i + 1), str(100 + i))])

    uc = ComputeVolatility(asset_repo, price_repo)
    full = await uc.execute(VolatilityRequest(symbol="AAPL", window_days=5))
    truncated = await uc.execute(VolatilityRequest(
        symbol="AAPL", window_days=5, to_date=date(2024, 1, 10),
    ))
    assert len(full.series) > len(truncated.series)
