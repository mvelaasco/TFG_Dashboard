# tests/unit/test_ports_contracts.py
"""
Verifica que los puertos son correctamente abstractos:
ninguna subclase incompleta puede instanciarse.
"""
import pytest
from datetime import datetime, timezone, date
from decimal import Decimal

from application.ports.asset_repository import AssetRepository
from application.ports.price_repository import PriceRepository
from application.ports.metric_repository import MetricRepository
from application.ports.market_data_client import MarketDataClient


def test_asset_repository_is_abstract():
    """No se puede instanciar sin implementar todos los métodos."""
    with pytest.raises(TypeError):
        AssetRepository()


def test_price_repository_is_abstract():
    with pytest.raises(TypeError):
        PriceRepository()


def test_metric_repository_is_abstract():
    with pytest.raises(TypeError):
        MetricRepository()


def test_market_data_client_is_abstract():
    with pytest.raises(TypeError):
        MarketDataClient()


def test_concrete_asset_repository_must_implement_all_methods():
    """Una implementación parcial también falla."""
    class IncompleteRepo(AssetRepository):
        def save(self, asset):
            return asset
        # find_by_symbol y find_all sin implementar

    with pytest.raises(TypeError):
        IncompleteRepo()


def test_concrete_asset_repository_full_implementation():
    """Una implementación completa sí puede instanciarse."""
    from domain.assets.asset import Asset
    from domain.assets.asset_type import AssetType

    class InMemoryAssetRepository(AssetRepository):
        def __init__(self):
            self._store: dict[str, Asset] = {}

        def save(self, asset: Asset) -> Asset:
            saved = asset.model_copy(update={"id": len(self._store) + 1})
            self._store[saved.symbol] = saved
            return saved

        def find_by_symbol(self, symbol: str) -> Asset | None:
            return self._store.get(symbol.upper())

        def find_all(self) -> list[Asset]:
            return list(self._store.values())

        def delete_by_symbol(self, symbol: str) -> bool:
            return self._store.pop(symbol.upper(), None) is not None

        def find_all_with_price_stats(self) -> list[tuple[Asset, date | None, int]]:
            return [(a, None, 0) for a in self._store.values()]

    repo = InMemoryAssetRepository()

    asset = Asset(
        symbol="MSFT",
        name="Microsoft Corp.",
        asset_type=AssetType.STOCK,
    )
    saved = repo.save(asset)

    assert saved.id == 1
    assert repo.find_by_symbol("MSFT") is not None
    assert len(repo.find_all()) == 1
    assert repo.find_by_symbol("AAPL") is None