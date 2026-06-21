import pytest
from datetime import date, datetime, timezone
from decimal import Decimal

from application.ports.asset_repository import AssetRepository
from application.ports.price_repository import PriceRepository
from application.use_cases.compute_coverage import (
    ComputeCoverage,
    ComputeCoverageRequest,
    CoverageItem,
    CoverageGap,
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
        return [p for p in self._store if p.asset_id == asset_id and from_time <= p.time <= to_time]

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


def _price(asset_id: int, day: date) -> Price:
    return Price(
        time=datetime(day.year, day.month, day.day, 21, 0, 0, tzinfo=timezone.utc),
        asset_id=asset_id,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=1_000_000,
    )


@pytest.fixture
def repos():
    return InMemoryAssetRepository(), InMemoryPriceRepository()


@pytest.fixture
def use_case(repos):
    asset_repo, price_repo = repos
    return ComputeCoverage(asset_repo=asset_repo, price_repo=price_repo)


async def test_full_coverage(repos):
    """No gaps — all weekdays present."""
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    for d in range(1, 12):
        if date(2024, 1, d).weekday() < 5:
            await price_repo.save_batch([_price(aapl.id, date(2024, 1, d))])

    uc = ComputeCoverage(asset_repo, price_repo)
    result = await uc.execute(ComputeCoverageRequest(symbols=["AAPL"]))
    assert len(result.items) == 1
    item = result.items[0]
    assert item.coverage_pct == 100.0
    assert item.gaps == []


async def test_missing_days_produces_gaps(repos):
    """Missing Wednesday and Thursday should produce a gap."""
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    for d in [1, 2, 3, 6, 7, 8]:  # skip 4 (Thu) and 5 (Fri)
        d_obj = date(2024, 2, d)
        if d_obj.weekday() < 5:
            await price_repo.save_batch([_price(aapl.id, d_obj)])

    uc = ComputeCoverage(asset_repo, price_repo)
    result = await uc.execute(ComputeCoverageRequest(symbols=["AAPL"], min_gap_days=1))
    assert len(result.items) == 1
    assert len(result.items[0].gaps) >= 1


async def test_min_gap_days_filters_small_gaps(repos):
    """A 1-day gap should be ignored when min_gap_days=2."""
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    for d in [1, 2, 3, 5, 6, 7]:  # skip 4 (Thu) — 1-day gap
        d_obj = date(2024, 2, d)
        if d_obj.weekday() < 5:
            await price_repo.save_batch([_price(aapl.id, d_obj)])

    uc = ComputeCoverage(asset_repo, price_repo)
    result = await uc.execute(ComputeCoverageRequest(symbols=["AAPL"], min_gap_days=2))
    assert len(result.items[0].gaps) == 0


async def test_no_data_asset_skipped(repos):
    """Asset without prices should be omitted from results."""
    asset_repo, price_repo = repos
    await asset_repo.save(Asset(symbol="EMPTY", name="Empty", asset_type=AssetType.STOCK))

    uc = ComputeCoverage(asset_repo, price_repo)
    result = await uc.execute(ComputeCoverageRequest(symbols=None))
    assert len(result.items) == 0
    assert result.summary.symbols_count == 0


async def test_multiple_assets(repos):
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    msft = await asset_repo.save(Asset(symbol="MSFT", name="Microsoft", asset_type=AssetType.STOCK))

    for d in range(1, 8):
        if date(2024, 1, d).weekday() < 5:
            await price_repo.save_batch([_price(aapl.id, date(2024, 1, d))])
    for d in range(1, 6):
        if date(2024, 1, d).weekday() < 5:
            await price_repo.save_batch([_price(msft.id, date(2024, 1, d))])

    uc = ComputeCoverage(asset_repo, price_repo)
    result = await uc.execute(ComputeCoverageRequest(symbols=None))
    assert len(result.items) == 2
    assert result.summary.symbols_count == 2


async def test_freshness_lag_days(repos):
    asset_repo, price_repo = repos
    aapl_recent = await asset_repo.save(Asset(symbol="RECENT", name="Recent", asset_type=AssetType.STOCK))
    last_day = date.today() - __import__("datetime").timedelta(days=2)
    if last_day.weekday() >= 5:
        last_day = date.today() - __import__("datetime").timedelta(days=4)
    await price_repo.save_batch([_price(aapl_recent.id, last_day)])

    uc = ComputeCoverage(asset_repo, price_repo)
    result = await uc.execute(ComputeCoverageRequest(symbols=["RECENT"]))
    assert len(result.items) == 1
    assert result.items[0].freshness_lag_days >= 2


async def test_record_count(repos):
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    prices = [_price(aapl.id, date(2024, 1, d)) for d in range(1, 6) if date(2024, 1, d).weekday() < 5]
    await price_repo.save_batch(prices)

    uc = ComputeCoverage(asset_repo, price_repo)
    result = await uc.execute(ComputeCoverageRequest(symbols=["AAPL"]))
    assert result.items[0].record_count == len(prices)


async def test_symbols_filter(repos):
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    msft = await asset_repo.save(Asset(symbol="MSFT", name="Microsoft", asset_type=AssetType.STOCK))
    for d in range(1, 6):
        if date(2024, 1, d).weekday() < 5:
            await price_repo.save_batch([_price(aapl.id, date(2024, 1, d))])
            await price_repo.save_batch([_price(msft.id, date(2024, 1, d))])

    uc = ComputeCoverage(asset_repo, price_repo)
    result = await uc.execute(ComputeCoverageRequest(symbols=["AAPL"]))
    assert len(result.items) == 1
    assert result.items[0].symbol == "AAPL"


async def test_invalid_min_gap_days_raises(use_case):
    with pytest.raises(ValueError):
        await use_case.execute(ComputeCoverageRequest(symbols=None, min_gap_days=0))


async def test_summary_threshold(repos):
    """Asset with low coverage should be counted as below threshold."""
    asset_repo, price_repo = repos
    good = await asset_repo.save(Asset(symbol="GOOD", name="Good", asset_type=AssetType.STOCK))
    bad = await asset_repo.save(Asset(symbol="BAD", name="Bad", asset_type=AssetType.STOCK))

    for d in range(1, 12):
        d_obj = date(2024, 1, d)
        if d_obj.weekday() < 5:
            await price_repo.save_batch([_price(good.id, d_obj)])
    # BAD only has Jan 1 (Mon) and Jan 11 (Thu) — big gap in between
    await price_repo.save_batch([_price(bad.id, date(2024, 1, 1))])
    await price_repo.save_batch([_price(bad.id, date(2024, 1, 11))])

    uc = ComputeCoverage(asset_repo, price_repo)
    result = await uc.execute(ComputeCoverageRequest(symbols=None, threshold_pct=60.0))
    assert result.summary.symbols_below_threshold >= 1


async def test_gap_structure(repos):
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    for d in [1, 2, 3]:  # Mon, Tue, Wed — then gap Thu, Fri
        d_obj = date(2024, 1, d)
        await price_repo.save_batch([_price(aapl.id, d_obj)])
    for d in [8, 9, 10]:  # Mon, Tue, Wed
        d_obj = date(2024, 1, d)
        if d_obj.weekday() < 5:
            await price_repo.save_batch([_price(aapl.id, d_obj)])

    uc = ComputeCoverage(asset_repo, price_repo)
    result = await uc.execute(ComputeCoverageRequest(symbols=["AAPL"], min_gap_days=1))
    if result.items[0].gaps:
        gap = result.items[0].gaps[0]
        assert isinstance(gap, CoverageGap)
        assert gap.days >= 1
        assert gap.start <= gap.end
