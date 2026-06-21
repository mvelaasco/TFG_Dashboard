import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from infrastructure.external_apis.tiingo_client import TiingoClient
from domain.assets.asset import Asset
from domain.assets.asset_type import AssetType
from domain.prices.price import Price


def _mock_response(status_code: int, json_data: object = None):
    m = MagicMock()
    m.status_code = status_code
    if json_data is not None:
        m.json.return_value = json_data
    else:
        m.json.side_effect = ValueError("No JSON set")
    return m


@pytest.fixture(autouse=True)
def mock_async_client():
    with patch("httpx.AsyncClient") as cls:
        yield cls


# --- fetch_asset_metadata ---

async def test_fetch_asset_metadata_returns_asset(mock_async_client):
    client_instance = AsyncMock()
    mock_async_client.return_value = client_instance
    client_instance.__aenter__.return_value = client_instance

    client_instance.get.return_value = _mock_response(200, {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "exchangeCode": "NASDAQ",
    })

    tiingo = TiingoClient()
    result = await tiingo.fetch_asset_metadata("AAPL")
    assert isinstance(result, Asset)
    assert result.symbol == "AAPL"
    assert result.name == "Apple Inc."
    assert result.exchange == "NASDAQ"


async def test_fetch_asset_metadata_404_returns_none(mock_async_client):
    client_instance = AsyncMock()
    mock_async_client.return_value = client_instance
    client_instance.__aenter__.return_value = client_instance
    client_instance.get.return_value = _mock_response(404)

    tiingo = TiingoClient()
    result = await tiingo.fetch_asset_metadata("UNKNOWN")
    assert result is None


async def test_fetch_asset_metadata_403_raises(mock_async_client):
    client_instance = AsyncMock()
    mock_async_client.return_value = client_instance
    client_instance.__aenter__.return_value = client_instance
    client_instance.get.return_value = _mock_response(403)

    tiingo = TiingoClient()
    with pytest.raises(PermissionError):
        await tiingo.fetch_asset_metadata("AAPL")


async def test_fetch_asset_metadata_network_error_returns_none(mock_async_client):
    from httpx import RequestError

    client_instance = AsyncMock()
    mock_async_client.return_value = client_instance
    client_instance.__aenter__.return_value = client_instance
    client_instance.get.side_effect = RequestError("Network error")

    tiingo = TiingoClient()
    result = await tiingo.fetch_asset_metadata("AAPL")
    assert result is None


# --- fetch_daily_prices ---

def _sample_price_row(date_str: str, close: float) -> dict:
    return {
        "date": date_str,
        "close": close,
        "adjOpen": close,
        "adjHigh": close + 1,
        "adjLow": close - 1,
        "adjClose": close,
        "adjVolume": 1_000_000,
    }


async def test_fetch_daily_prices_returns_prices(mock_async_client):
    client_instance = AsyncMock()
    mock_async_client.return_value = client_instance
    client_instance.__aenter__.return_value = client_instance

    client_instance.get.return_value = _mock_response(200, [
        _sample_price_row("2024-01-02T00:00:00+00:00", 185.0),
        _sample_price_row("2024-01-03T00:00:00+00:00", 186.0),
    ])

    tiingo = TiingoClient()
    prices = await tiingo.fetch_daily_prices("AAPL", date(2024, 1, 2), date(2024, 1, 3))
    assert len(prices) == 2
    assert all(isinstance(p, Price) for p in prices)
    assert float(prices[0].close) == 185.0


async def test_fetch_daily_prices_filters_null_close(mock_async_client):
    client_instance = AsyncMock()
    mock_async_client.return_value = client_instance
    client_instance.__aenter__.return_value = client_instance

    client_instance.get.return_value = _mock_response(200, [
        {"date": "2024-01-02T00:00:00+00:00", "close": None},
        _sample_price_row("2024-01-03T00:00:00+00:00", 186.0),
    ])

    tiingo = TiingoClient()
    prices = await tiingo.fetch_daily_prices("AAPL", date(2024, 1, 2), date(2024, 1, 3))
    assert len(prices) == 1


async def test_fetch_daily_prices_404_returns_empty(mock_async_client):
    client_instance = AsyncMock()
    mock_async_client.return_value = client_instance
    client_instance.__aenter__.return_value = client_instance
    client_instance.get.return_value = _mock_response(404)

    tiingo = TiingoClient()
    prices = await tiingo.fetch_daily_prices("UNKNOWN", date(2024, 1, 2), date(2024, 1, 3))
    assert prices == []


async def test_fetch_daily_prices_network_error_raises(mock_async_client):
    from httpx import RequestError

    client_instance = AsyncMock()
    mock_async_client.return_value = client_instance
    client_instance.__aenter__.return_value = client_instance
    client_instance.get.side_effect = RequestError("Network error")

    tiingo = TiingoClient()
    with pytest.raises(ConnectionError):
        await tiingo.fetch_daily_prices("AAPL", date(2024, 1, 2), date(2024, 1, 3))


# --- _infer_asset_type ---

def test_infer_etf_by_name():
    result = TiingoClient._infer_asset_type({"name": "Vanguard Total Stock Market ETF"})
    assert result == AssetType.ETF


def test_infer_index_by_description():
    result = TiingoClient._infer_asset_type({"description": "S&P 500 index"})
    assert result == AssetType.INDEX


def test_infer_stock_default():
    result = TiingoClient._infer_asset_type({"name": "Apple Inc."})
    assert result == AssetType.STOCK


# --- _parse_price ---

def test_parse_price_timezone_handling():
    row = _sample_price_row("2024-01-02T14:30:00-05:00", 185.0)
    price = TiingoClient._parse_price(row, "AAPL")
    assert price.time.tzinfo is not None
    assert price.time.utcoffset().total_seconds() == 0  # normalized to UTC


def test_parse_price_missing_adjusted_fields():
    """_parse_price handles rows where only adjClose is present."""
    row = {
        "date": "2024-01-02T14:30:00Z",
        "adjClose": 185.0,
    }
    price = TiingoClient._parse_price(row, "AAPL")
    assert float(price.close) == 185.0
    assert price.open is None
