import pytest
from datetime import date, datetime, timezone
from decimal import Decimal

from application.ports.asset_repository import AssetRepository
from application.ports.price_repository import PriceRepository
from application.use_cases.compute_coverage_calendar import (
    ComputeCoverageCalendar,
    CoverageCalendarRequest,
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


async def test_all_assets_have_data(repos):
    """All assets have prices for all days in range."""
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    msft = await asset_repo.save(Asset(symbol="MSFT", name="Microsoft", asset_type=AssetType.STOCK))

    for d in range(1, 5):
        await price_repo.save_batch([_price(aapl.id, date(2024, 1, d))])
        await price_repo.save_batch([_price(msft.id, date(2024, 1, d))])

    uc = ComputeCoverageCalendar(asset_repo, price_repo)
    result = await uc.execute(CoverageCalendarRequest(
        from_date=date(2024, 1, 1), to_date=date(2024, 1, 4),
    ))

    assert result.total_assets == 2
    assert len(result.days) == 4
    for day in result.days:
        if day.is_weekend:
            assert day.actual_count == 0
        else:
            assert day.actual_count == 2
            assert day.expected_count == 2


async def test_partial_data(repos):
    """Only one asset has data on certain days."""
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    msft = await asset_repo.save(Asset(symbol="MSFT", name="Microsoft", asset_type=AssetType.STOCK))
    goog = await asset_repo.save(Asset(symbol="GOOG", name="Google", asset_type=AssetType.STOCK))

    await price_repo.save_batch([_price(aapl.id, date(2024, 1, 2))])
    await price_repo.save_batch([_price(msft.id, date(2024, 1, 2))])

    uc = ComputeCoverageCalendar(asset_repo, price_repo)
    result = await uc.execute(CoverageCalendarRequest(
        from_date=date(2024, 1, 1), to_date=date(2024, 1, 3),
    ))

    jan2 = next(d for d in result.days if d.date == date(2024, 1, 2))
    assert jan2.actual_count == 2
    assert jan2.expected_count == 3


async def test_weekend_detection(repos):
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    await price_repo.save_batch([_price(aapl.id, date(2024, 1, 5))])  # Friday
    await price_repo.save_batch([_price(aapl.id, date(2024, 1, 6))])  # Saturday
    await price_repo.save_batch([_price(aapl.id, date(2024, 1, 7))])  # Sunday

    uc = ComputeCoverageCalendar(asset_repo, price_repo)
    result = await uc.execute(CoverageCalendarRequest(
        from_date=date(2024, 1, 5), to_date=date(2024, 1, 7),
    ))

    fri = next(d for d in result.days if d.date == date(2024, 1, 5))
    sat = next(d for d in result.days if d.date == date(2024, 1, 6))
    sun = next(d for d in result.days if d.date == date(2024, 1, 7))
    assert fri.is_weekend is False
    assert sat.is_weekend is True
    assert sun.is_weekend is True


async def test_no_assets(repos):
    """No assets in DB → total_assets=0, days still cover range."""
    asset_repo, price_repo = repos
    uc = ComputeCoverageCalendar(asset_repo, price_repo)
    result = await uc.execute(CoverageCalendarRequest(
        from_date=date(2024, 1, 1), to_date=date(2024, 1, 3),
    ))
    assert result.total_assets == 0
    assert len(result.days) == 3
    for day in result.days:
        assert day.actual_count == 0


async def test_range_order(repos):
    """Days should be returned in chronological order."""
    asset_repo, price_repo = repos
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))
    await price_repo.save_batch([_price(aapl.id, date(2024, 1, 1))])

    uc = ComputeCoverageCalendar(asset_repo, price_repo)
    result = await uc.execute(CoverageCalendarRequest(
        from_date=date(2024, 1, 1), to_date=date(2024, 1, 5),
    ))
    dates = [d.date for d in result.days]
    assert dates == sorted(dates)
