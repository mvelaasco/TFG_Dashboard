# tests/integration/test_pg_price_repository.py
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from domain.assets.asset import Asset
from domain.assets.asset_type import AssetType
from domain.prices.price import Price
from infrastructure.db.repositories.pg_asset_repository import PgAssetRepository
from infrastructure.db.repositories.pg_price_repository import PgPriceRepository


def _make_price(asset_id: int, year: int, month: int, day: int, close: str) -> Price:
    return Price(
        time=datetime(year, month, day, 21, 0, 0, tzinfo=timezone.utc),
        asset_id=asset_id,
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=1_000_000,
    )


@pytest.fixture
async def saved_asset(db_session: AsyncSession) -> Asset:
    """Crea un activo real en BD y lo devuelve con id asignado."""
    repo = PgAssetRepository(db_session)
    return await repo.save(Asset(
        symbol="AAPL",
        name="Apple Inc.",
        asset_type=AssetType.STOCK,
        currency="USD",
        exchange="NASDAQ",
    ))


async def test_save_batch_returns_row_count(db_session, saved_asset):
    repo = PgPriceRepository(db_session)
    prices = [
        _make_price(saved_asset.id, 2024, 1, 15, "185.50"),
        _make_price(saved_asset.id, 2024, 1, 16, "186.20"),
        _make_price(saved_asset.id, 2024, 1, 17, "184.90"),
    ]
    count = await repo.save_batch(prices)
    assert count == 3


async def test_save_batch_is_idempotent(db_session, saved_asset):
    """Insertar los mismos precios dos veces no duplica filas."""
    repo = PgPriceRepository(db_session)
    prices = [
        _make_price(saved_asset.id, 2024, 1, 15, "185.50"),
        _make_price(saved_asset.id, 2024, 1, 16, "186.20"),
    ]
    await repo.save_batch(prices)
    count = await repo.save_batch(prices)
    assert count == 0


async def test_find_by_asset_returns_prices_in_range(db_session, saved_asset):
    repo = PgPriceRepository(db_session)
    prices = [
        _make_price(saved_asset.id, 2024, 1, 15, "185.50"),
        _make_price(saved_asset.id, 2024, 1, 16, "186.20"),
        _make_price(saved_asset.id, 2024, 1, 17, "184.90"),
    ]
    await repo.save_batch(prices)

    from_time = datetime(2024, 1, 15, tzinfo=timezone.utc)
    to_time   = datetime(2024, 1, 16, 23, 59, 59, tzinfo=timezone.utc)

    found = await repo.find_by_asset(saved_asset.id, from_time, to_time)
    assert len(found) == 2
    assert all(isinstance(p.close, Decimal) for p in found)


async def test_find_by_asset_returns_prices_ordered_ascending(db_session, saved_asset):
    repo = PgPriceRepository(db_session)
    prices = [
        _make_price(saved_asset.id, 2024, 1, 17, "184.90"),
        _make_price(saved_asset.id, 2024, 1, 15, "185.50"),
        _make_price(saved_asset.id, 2024, 1, 16, "186.20"),
    ]
    await repo.save_batch(prices)

    from_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    to_time   = datetime(2024, 1, 31, tzinfo=timezone.utc)

    found = await repo.find_by_asset(saved_asset.id, from_time, to_time)
    times = [p.time for p in found]
    assert times == sorted(times)


async def test_find_latest_returns_most_recent_price(db_session, saved_asset):
    repo = PgPriceRepository(db_session)
    prices = [
        _make_price(saved_asset.id, 2024, 1, 15, "185.50"),
        _make_price(saved_asset.id, 2024, 1, 17, "184.90"),
        _make_price(saved_asset.id, 2024, 1, 16, "186.20"),
    ]
    await repo.save_batch(prices)

    latest = await repo.find_latest(saved_asset.id)
    assert latest is not None
    assert latest.time == datetime(2024, 1, 17, 21, 0, 0, tzinfo=timezone.utc)
    assert latest.close == Decimal("184.90")


async def test_find_latest_returns_none_when_no_prices(db_session, saved_asset):
    repo = PgPriceRepository(db_session)
    result = await repo.find_latest(saved_asset.id)
    assert result is None


async def test_save_batch_empty_list_returns_zero(db_session, saved_asset):
    repo = PgPriceRepository(db_session)
    count = await repo.save_batch([])
    assert count == 0