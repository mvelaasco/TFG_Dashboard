import pytest
from datetime import date, datetime, timezone
from decimal import Decimal

from application.ports.asset_repository import AssetRepository
from application.ports.price_repository import PriceRepository
from application.ports.market_data_client import MarketDataClient
from application.use_cases.ingest_prices import IngestPrices, IngestPricesRequest
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
        return [
            p for p in self._store
            if p.asset_id == asset_id
            and from_time <= p.time <= to_time
        ]

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


def _make_price(asset_id: int, day: date, close: str) -> Price:
    return Price(
        time=datetime(day.year, day.month, day.day, 21, 0, 0, tzinfo=timezone.utc),
        asset_id=asset_id,
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=1_000_000,
    )


class StubMarketClient(MarketDataClient):

    async def fetch_asset_metadata(self, symbol: str) -> Asset | None:
        if symbol == "FAKE":
            return None
        return Asset(
            symbol=symbol,
            name=f"{symbol} Inc.",
            asset_type=AssetType.STOCK,
            currency="USD",
            exchange="NASDAQ",
        )

    async def fetch_daily_prices(self, symbol: str, from_date: date, to_date: date) -> list[Price]:
        if symbol == "EMPTY":
            return []
        return [
            _make_price(0, date(2024, 1, 15), "185.50"),
            _make_price(0, date(2024, 1, 16), "186.20"),
            _make_price(0, date(2024, 1, 17), "184.90"),
        ]


@pytest.fixture
def use_case():
    return IngestPrices(
        asset_repo=InMemoryAssetRepository(),
        price_repo=InMemoryPriceRepository(),
        market_client=StubMarketClient(),
    )


async def test_ingest_creates_asset_when_not_exists(use_case):
    request = IngestPricesRequest(
        symbol="AAPL",
        from_date=date(2024, 1, 15),
        to_date=date(2024, 1, 17),
    )
    result = await use_case.execute(request)
    assert result.symbol == "AAPL"
    assert result.already_existed is False
    assert result.rows_inserted == 3


async def test_ingest_reuses_existing_asset(use_case):
    request = IngestPricesRequest(
        symbol="AAPL",
        from_date=date(2024, 1, 15),
        to_date=date(2024, 1, 17),
    )
    await use_case.execute(request)
    result = await use_case.execute(request)
    assert result.already_existed is True


async def test_ingest_normalizes_symbol_to_uppercase(use_case):
    request = IngestPricesRequest(
        symbol="aapl",
        from_date=date(2024, 1, 15),
        to_date=date(2024, 1, 17),
    )
    result = await use_case.execute(request)
    assert result.symbol == "AAPL"


async def test_ingest_raises_when_symbol_not_found(use_case):
    request = IngestPricesRequest(
        symbol="FAKE",
        from_date=date(2024, 1, 15),
        to_date=date(2024, 1, 17),
    )
    with pytest.raises(ValueError, match="no existe en la fuente de datos"):
        await use_case.execute(request)


async def test_ingest_returns_zero_rows_when_no_prices(use_case):
    request = IngestPricesRequest(
        symbol="EMPTY",
        from_date=date(2024, 1, 15),
        to_date=date(2024, 1, 17),
    )
    result = await use_case.execute(request)
    assert result.rows_inserted == 0


async def test_prices_have_correct_asset_id_after_ingest():
    price_repo = InMemoryPriceRepository()
    asset_repo = InMemoryAssetRepository()

    uc = IngestPrices(
        asset_repo=asset_repo,
        price_repo=price_repo,
        market_client=StubMarketClient(),
    )

    await uc.execute(IngestPricesRequest(
        symbol="MSFT",
        from_date=date(2024, 1, 15),
        to_date=date(2024, 1, 17),
    ))

    asset = await asset_repo.find_by_symbol("MSFT")
    assert asset.id is not None

    for price in price_repo._store:
        assert price.asset_id == asset.id