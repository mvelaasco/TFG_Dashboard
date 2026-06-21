import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domain.assets.asset import Asset
from domain.assets.asset_type import AssetType
from infrastructure.db.repositories.pg_asset_repository import PgAssetRepository

# Indicamos explícitamente a pytest que este módulo contiene corrutinas asíncronas
pytestmark = pytest.mark.asyncio


def _make_asset(symbol: str, asset_type: AssetType = AssetType.STOCK) -> Asset:
    return Asset(
        symbol=symbol,
        name=f"{symbol} Test Corp.",
        asset_type=asset_type,
        currency="USD",
        exchange="NASDAQ",
    )


async def test_save_asset_assigns_id(db_session: AsyncSession):
    repo = PgAssetRepository(db_session)
    saved = await repo.save(_make_asset("AAPL"))
    
    assert saved.id is not None
    assert int(saved.id) > 0
    assert saved.symbol == "AAPL"


async def test_find_by_symbol_returns_saved_asset(db_session: AsyncSession):
    repo = PgAssetRepository(db_session)
    await repo.save(_make_asset("MSFT"))
    
    # Forzar la consulta física a la BD limpiando el Identity Map local
    db_session.expire_all()
    
    found = await repo.find_by_symbol("MSFT")
    assert found is not None
    assert found.symbol == "MSFT"
    assert found.asset_type == AssetType.STOCK


async def test_find_by_symbol_is_case_insensitive(db_session: AsyncSession):
    repo = PgAssetRepository(db_session)
    await repo.save(_make_asset("GOOG"))
    
    db_session.expire_all()
    
    found = await repo.find_by_symbol("goog")
    assert found is not None
    assert found.symbol == "GOOG"


async def test_find_by_symbol_returns_none_when_not_exists(db_session: AsyncSession):
    repo = PgAssetRepository(db_session)
    found = await repo.find_by_symbol("DOESNOTEXIST")
    assert found is None


async def test_find_all_returns_saved_assets(db_session: AsyncSession):
    repo = PgAssetRepository(db_session)
    await repo.save(_make_asset("SPY", AssetType.ETF))
    await repo.save(_make_asset("QQQ", AssetType.ETF))
    
    db_session.expire_all()
    
    all_assets = await repo.find_all()
    symbols = {a.symbol for a in all_assets}
    assert "SPY" in symbols
    assert "QQQ" in symbols


async def test_saved_asset_preserves_asset_type(db_session: AsyncSession):
    repo = PgAssetRepository(db_session)
    await repo.save(_make_asset("VIX", AssetType.INDEX))
    
    db_session.expire_all()
    
    found = await repo.find_by_symbol("VIX")
    assert found is not None
    assert found.asset_type == AssetType.INDEX


async def test_saved_asset_preserves_timezone(db_session: AsyncSession):
    repo = PgAssetRepository(db_session)
    asset = Asset(
        symbol="IBEX",
        name="IBEX 35",
        asset_type=AssetType.INDEX,
        currency="EUR",
        exchange="BME",
        timezone="Europe/Madrid",
    )
    await repo.save(asset)
    
    db_session.expire_all()
    
    found = await repo.find_by_symbol("IBEX")
    assert found is not None
    assert found.timezone == "Europe/Madrid"
    assert found.currency == "EUR"