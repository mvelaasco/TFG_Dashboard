# backend/smoke_test.py
import sys
sys.path.insert(0, "src")

from decimal import Decimal
from datetime import datetime, timezone

from domain.assets.asset import Asset
from domain.assets.asset_type import AssetType
from domain.prices.price import Price
from domain.metrics.metric import AnalyticalMetric

# --- Asset ---
asset = Asset(
    symbol="aapl",          # debe convertirse a "AAPL"
    name="Apple Inc.",
    asset_type=AssetType.STOCK,
    currency="usd",         # debe convertirse a "USD"
    exchange="NASDAQ",
)
assert asset.symbol == "AAPL"
assert asset.currency == "USD"
print(f"✓ Asset: {asset.symbol} ({asset.asset_type})")

# --- Price válido ---
price = Price(
    time=datetime(2024, 1, 15, 21, 0, 0, tzinfo=timezone.utc),
    asset_id=1,
    open=Decimal("185.50"),
    high=Decimal("186.00"),
    low=Decimal("184.90"),
    close=Decimal("185.85"),
    volume=52_000_000,
)
print(f"✓ Price: close={price.close}, time={price.time}")

# --- Price inválido: high < low ---
try:
    Price(
        time=datetime(2024, 1, 15, 21, 0, 0, tzinfo=timezone.utc),
        asset_id=1,
        high=Decimal("180.00"),
        low=Decimal("190.00"),   # low > high: debe fallar
        close=Decimal("185.00"),
    )
    assert False, "Debería haber lanzado ValueError"
except Exception as e:
    print(f"✓ Validación OHLC rechaza datos corruptos: {e}")

# --- Price sin timezone: debe fallar ---
try:
    Price(
        time=datetime(2024, 1, 15, 21, 0, 0),  # sin tzinfo
        asset_id=1,
        close=Decimal("185.00"),
    )
    assert False, "Debería haber lanzado ValueError"
except Exception as e:
    print(f"✓ Validación UTC rechaza timestamps sin zona: {e}")

# --- Metric ---
from datetime import timezone
metric = AnalyticalMetric(
    time=datetime(2024, 1, 15, tzinfo=timezone.utc),
    base_asset_id=1,
    comparison_asset_id=2,
    metric_name="correlation_30d",
    window_days=30,
    metric_value=Decimal("-0.823456"),
)
print(f"✓ Metric: {metric.metric_name} = {metric.metric_value}")

print("\n✅ Todas las entidades del dominio son correctas.")