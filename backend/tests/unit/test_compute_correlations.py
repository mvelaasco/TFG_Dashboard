import pytest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from application.ports.asset_repository import AssetRepository
from application.ports.price_repository import PriceRepository
from application.ports.metric_repository import MetricRepository
from application.use_cases.compute_correlations import (
    ComputeCorrelations,
    ComputeCorrelationsRequest,
)
from domain.assets.asset import Asset
from domain.assets.asset_type import AssetType
from domain.metrics.metric import AnalyticalMetric
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


class InMemoryMetricRepository(MetricRepository):
    def __init__(self):
        self._store: list[AnalyticalMetric] = []

    async def save_batch(self, metrics: list[AnalyticalMetric]) -> int:
        self._store.extend(metrics)
        return len(metrics)

    async def find_latest(
        self,
        base_asset_id: int,
        comparison_asset_id: int | None,
        metric_name: str,
        window_days: int,
    ) -> AnalyticalMetric | None:
        candidates = [
            m for m in self._store
            if m.base_asset_id == base_asset_id
            and m.comparison_asset_id == comparison_asset_id
            and m.metric_name == metric_name
            and m.window_days == window_days
        ]
        return max(candidates, key=lambda m: m.time) if candidates else None

    async def find_series(
        self,
        base_asset_id: int,
        comparison_asset_id: int | None,
        metric_name: str,
        window_days: int,
        from_time: datetime,
        to_time: datetime,
    ) -> list[AnalyticalMetric]:
        return sorted(
            [
                m for m in self._store
                if m.base_asset_id == base_asset_id
                and m.comparison_asset_id == comparison_asset_id
                and m.metric_name == metric_name
                and m.window_days == window_days
                and from_time <= m.time <= to_time
            ],
            key=lambda m: m.time,
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
    return (
        InMemoryAssetRepository(),
        InMemoryPriceRepository(),
        InMemoryMetricRepository(),
    )


async def test_basic_correlation(repos):
    """Base vs risk — metrics should be computed for both windows."""
    asset_repo, price_repo, metric_repo = repos
    spy = await asset_repo.save(Asset(symbol="SPY", name="S&P 500", asset_type=AssetType.ETF))
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))

    for i in range(60):
        d = date(2024, 1, 1) + timedelta(days=i)
        await price_repo.save_batch([_price(spy.id, d, str(400 + i))])
        await price_repo.save_batch([_price(aapl.id, d, str(100 + (i if i < 30 else 60 - i)))])

    uc = ComputeCorrelations(asset_repo, price_repo, metric_repo)
    result = await uc.execute(ComputeCorrelationsRequest(
        risk_symbols=["SPY"],
        from_date=date(2024, 1, 1),
        to_date=date(2024, 3, 1),
    ))
    assert result.pairs_processed == 1
    assert result.metrics_inserted > 0
    assert result.missing_risk_symbols == []


async def test_missing_risk_symbol(repos):
    """Risk symbol not in DB should appear in missing_risk_symbols."""
    asset_repo, price_repo, metric_repo = repos
    await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))

    uc = ComputeCorrelations(asset_repo, price_repo, metric_repo)
    result = await uc.execute(ComputeCorrelationsRequest(risk_symbols=["FAKE"]))
    assert result.missing_risk_symbols == ["FAKE"]
    assert result.pairs_processed == 0


async def test_all_risk_symbols_missing(repos):
    """All risk symbols missing → empty result."""
    asset_repo, price_repo, metric_repo = repos
    await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))

    uc = ComputeCorrelations(asset_repo, price_repo, metric_repo)
    result = await uc.execute(ComputeCorrelationsRequest(risk_symbols=["FAKE1", "FAKE2"]))
    assert result.metrics_inserted == 0
    assert result.pairs_processed == 0
    assert len(result.missing_risk_symbols) == 2


async def test_no_overlapping_prices(repos):
    """No common trading dates → no pairs processed."""
    asset_repo, price_repo, metric_repo = repos
    spy = await asset_repo.save(Asset(symbol="SPY", name="S&P 500", asset_type=AssetType.ETF))
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))

    for i in range(10):
        d = date(2024, 1, 1) + timedelta(days=i)
        await price_repo.save_batch([_price(spy.id, d, "400")])
    for i in range(10):
        d = date(2024, 2, 1) + timedelta(days=i)
        await price_repo.save_batch([_price(aapl.id, d, "100")])

    uc = ComputeCorrelations(asset_repo, price_repo, metric_repo)
    result = await uc.execute(ComputeCorrelationsRequest(
        risk_symbols=["SPY"],
        from_date=date(2024, 1, 1),
        to_date=date(2024, 3, 1),
    ))
    assert result.pairs_processed == 0
    assert result.metrics_inserted == 0


async def test_from_date_forces_recomputation(repos):
    """When from_date is provided, all metrics are recomputed (last_time cleared)."""
    asset_repo, price_repo, metric_repo = repos
    spy = await asset_repo.save(Asset(symbol="SPY", name="S&P 500", asset_type=AssetType.ETF))
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))

    for i in range(60):
        d = date(2024, 1, 1) + timedelta(days=i)
        await price_repo.save_batch([_price(spy.id, d, str(400 + i))])
        await price_repo.save_batch([_price(aapl.id, d, str(100 + (i if i < 30 else 60 - i)))])

    uc = ComputeCorrelations(asset_repo, price_repo, metric_repo)
    result_with_from = await uc.execute(ComputeCorrelationsRequest(
        risk_symbols=["SPY"],
        from_date=date(2024, 1, 1),
        to_date=date(2024, 3, 1),
    ))
    assert result_with_from.metrics_inserted > 0


async def test_multiple_windows_produce_metrics(repos):
    """Both 30d and 90d windows should produce metrics with enough data."""
    asset_repo, price_repo, metric_repo = repos
    spy = await asset_repo.save(Asset(symbol="SPY", name="S&P 500", asset_type=AssetType.ETF))
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))

    for i in range(120):
        d = date(2024, 1, 1) + timedelta(days=i)
        await price_repo.save_batch([_price(spy.id, d, str(400 + i))])
        await price_repo.save_batch([_price(aapl.id, d, str(100 + (i if i < 60 else 120 - i)))])

    uc = ComputeCorrelations(asset_repo, price_repo, metric_repo)
    result = await uc.execute(ComputeCorrelationsRequest(
        risk_symbols=["SPY"],
        from_date=date(2024, 1, 1),
        window_days=[30, 90],
        to_date=date(2024, 4, 30),
    ))
    assert result.metrics_inserted > 0
    metric_names = {m.metric_name for m in metric_repo._store}
    assert "correlation_30d" in metric_names
    assert "correlation_90d" in metric_names


async def test_correlation_with_series_generated_correctly(repos):
    """Correlation of identical moves = 1.0 (within precision)."""
    asset_repo, price_repo, metric_repo = repos
    spy = await asset_repo.save(Asset(symbol="SPY", name="S&P 500", asset_type=AssetType.ETF))
    aapl = await asset_repo.save(Asset(symbol="AAPL", name="Apple", asset_type=AssetType.STOCK))

    for i in range(60):
        d = date(2024, 1, 1) + timedelta(days=i)
        await price_repo.save_batch([_price(spy.id, d, str(400 + i))])
        await price_repo.save_batch([_price(aapl.id, d, str(400 + i))])

    uc = ComputeCorrelations(asset_repo, price_repo, metric_repo)
    result = await uc.execute(ComputeCorrelationsRequest(
        risk_symbols=["SPY"],
        from_date=date(2024, 1, 1),
        window_days=[30],
        to_date=date(2024, 3, 1),
    ))
    assert result.metrics_inserted > 0
    metrics = await metric_repo.find_series(
        base_asset_id=aapl.id,
        comparison_asset_id=spy.id,
        metric_name="correlation_30d",
        window_days=30,
        from_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        to_time=datetime(2024, 12, 31, tzinfo=timezone.utc),
    )
    assert len(metrics) > 0
    for m in metrics:
        assert float(m.metric_value) == pytest.approx(1.0, abs=1e-6)
