import pytest
from datetime import date, datetime, timezone
from decimal import Decimal

from application.ports.asset_repository import AssetRepository
from application.ports.price_repository import PriceRepository
from application.use_cases.compute_correlation_matrix import (
    ComputeCorrelationMatrix,
    CorrelationMatrixRequest,
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


_FROM = date(2024, 1, 1)
_TO = date(2024, 1, 15)


async def test_two_assets_correlation(repos):
    """Two assets with overlapping prices should produce a 2x2 matrix."""
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    msft = await asset_repo.save(Asset(symbol="MSFT", name="Microsoft", asset_type=AssetType.STOCK))

    for i in range(10):
        d = date(2024, 1, i + 1)
        await price_repo.save_batch([_price(aapl.id, d, str(100 + i))])
        await price_repo.save_batch([_price(msft.id, d, str(105 + i))])

    uc = ComputeCorrelationMatrix(asset_repo, price_repo)
    result = await uc.execute(CorrelationMatrixRequest(top_n=5, to_date=_TO, from_date=_FROM))
    assert result.symbols == ["AAPL", "MSFT"]
    assert len(result.matrix) == 2
    assert result.matrix[0][0] == 1.0
    assert result.matrix[1][1] == 1.0


async def test_no_assets(repos):
    """With no assets, result should be empty."""
    asset_repo, price_repo = repos
    uc = ComputeCorrelationMatrix(asset_repo, price_repo)
    result = await uc.execute(CorrelationMatrixRequest())
    assert result.symbols == []
    assert result.matrix == []


async def test_single_asset_returns_empty(repos):
    """With only one asset with data, result should be empty."""
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    for i in range(5):
        await price_repo.save_batch([_price(aapl.id, date(2024, 1, i + 1), str(100 + i))])

    uc = ComputeCorrelationMatrix(asset_repo, price_repo)
    result = await uc.execute(CorrelationMatrixRequest(top_n=5, to_date=_TO, from_date=_FROM))
    assert result.symbols == []
    assert result.matrix == []


async def test_top_n_limits_symbols(repos):
    """top_n should limit how many symbols appear in the matrix."""
    asset_repo, price_repo = repos
    for sym in ["A", "B", "C", "D"]:
        a = await asset_repo.save(Asset(symbol=sym, name=sym, asset_type=AssetType.STOCK))
        for i in range(5):
            await price_repo.save_batch([_price(a.id, date(2024, 1, i + 1), str(100 + i))])

    uc = ComputeCorrelationMatrix(asset_repo, price_repo)
    result = await uc.execute(CorrelationMatrixRequest(top_n=2, to_date=_TO, from_date=_FROM))
    assert len(result.symbols) == 2


async def test_perfect_correlation(repos):
    """Identical return series (same moves) → off-diagonal = 1.0."""
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    msft = await asset_repo.save(Asset(symbol="MSFT", name="Microsoft", asset_type=AssetType.STOCK))

    for i in range(10):
        d = date(2024, 1, i + 1)
        await price_repo.save_batch([_price(aapl.id, d, str(100 + i))])
        await price_repo.save_batch([_price(msft.id, d, str(100 + i))])

    uc = ComputeCorrelationMatrix(asset_repo, price_repo)
    result = await uc.execute(CorrelationMatrixRequest(top_n=5, to_date=_TO, from_date=_FROM))
    assert result.matrix[0][1] == pytest.approx(1.0, abs=1e-9)
    assert result.matrix[1][0] == pytest.approx(1.0, abs=1e-9)


async def test_non_overlapping_periods(repos):
    """Assets with no overlapping dates should return empty."""
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    msft = await asset_repo.save(Asset(symbol="MSFT", name="Microsoft", asset_type=AssetType.STOCK))

    for i in range(5):
        await price_repo.save_batch([_price(aapl.id, date(2024, 1, i + 1), "100")])
    for i in range(5):
        await price_repo.save_batch([_price(msft.id, date(2024, 2, i + 1), "100")])

    uc = ComputeCorrelationMatrix(asset_repo, price_repo)
    result = await uc.execute(CorrelationMatrixRequest(top_n=5, to_date=_TO, from_date=_FROM))
    assert result.symbols == []
    assert result.matrix == []


async def test_three_asset_matrix_symmetric(repos):
    """Matrix should be symmetric for 3+ assets."""
    asset_repo, price_repo = repos
    assets = []
    for sym in ["AAPL", "MSFT", "GOOG"]:
        a = await asset_repo.save(Asset(symbol=sym, name=sym, asset_type=AssetType.STOCK))
        assets.append(a)

    for i in range(10):
        d = date(2024, 1, i + 1)
        for a in assets:
            await price_repo.save_batch([_price(a.id, d, str(100 + i))])

    uc = ComputeCorrelationMatrix(asset_repo, price_repo)
    result = await uc.execute(CorrelationMatrixRequest(top_n=5, to_date=_TO, from_date=_FROM))
    assert len(result.matrix) == 3
    for i in range(3):
        for j in range(3):
            assert result.matrix[i][j] == pytest.approx(result.matrix[j][i])
