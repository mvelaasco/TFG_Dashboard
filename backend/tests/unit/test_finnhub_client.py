import pytest
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import httpx

from infrastructure.external_apis.finnhub_client import (
    FinnhubClient,
    ExternalServiceError,
    RateLimitExceeded,
)
from domain.news.news_item import NewsItem


def _mock_response(status_code: int = 200, json_data: object = None):
    m = AsyncMock(spec=httpx.Response)
    m.status_code = status_code
    if json_data is not None:
        m.json.return_value = json_data
    return m


def _make_client(http_get_return: AsyncMock = None):
    http = AsyncMock(spec=httpx.AsyncClient)
    http.get.return_value = http_get_return
    return FinnhubClient(http)


def _sample_news(ts: int = 1700000000) -> dict:
    return {"headline": "Test news", "datetime": ts, "source": "Reuters", "url": "https://example.com"}


async def test_fetch_news_returns_items():
    client = _make_client(_mock_response(200, [_sample_news()]))
    result = await client.fetch_news("AAPL", date(2024, 3, 15))
    assert len(result) == 1
    assert isinstance(result[0], NewsItem)
    assert result[0].symbol == "AAPL"
    assert result[0].headline == "Test news"


async def test_fetch_news_skips_items_without_headline():
    rows = [{"datetime": 1700000000}, _sample_news()]
    client = _make_client(_mock_response(200, rows))
    result = await client.fetch_news("AAPL", date(2024, 3, 15))
    assert len(result) == 1


async def test_fetch_news_skips_items_without_datetime():
    rows = [{"headline": "No datetime"}, _sample_news()]
    client = _make_client(_mock_response(200, rows))
    result = await client.fetch_news("AAPL", date(2024, 3, 15))
    assert len(result) == 1


async def test_fetch_news_empty_response():
    client = _make_client(_mock_response(200, []))
    result = await client.fetch_news("AAPL", date(2024, 3, 15))
    assert result == []


async def test_fetch_news_401_raises_permission_error():
    client = _make_client(_mock_response(401))
    with pytest.raises(PermissionError):
        await client.fetch_news("AAPL", date(2024, 3, 15))


async def test_fetch_news_403_raises_permission_error():
    client = _make_client(_mock_response(403))
    with pytest.raises(PermissionError):
        await client.fetch_news("AAPL", date(2024, 3, 15))


async def test_fetch_news_429_raises_rate_limit():
    client = _make_client(_mock_response(429))
    with pytest.raises(RateLimitExceeded):
        await client.fetch_news("AAPL", date(2024, 3, 15))


async def test_fetch_news_500_raises_external_error():
    client = _make_client(_mock_response(500))
    with pytest.raises(ExternalServiceError):
        await client.fetch_news("AAPL", date(2024, 3, 15))


async def test_fetch_news_network_error_raises_external_error():
    http = AsyncMock(spec=httpx.AsyncClient)
    http.get.side_effect = httpx.RequestError("Connection failed")
    client = FinnhubClient(http)

    with pytest.raises(ExternalServiceError):
        await client.fetch_news("AAPL", date(2024, 3, 15))


def test_parse_item_converts_timestamp():
    ts = 1700000000
    dt_expected = datetime.fromtimestamp(ts, tz=timezone.utc)
    item = FinnhubClient._parse_item(
        {"headline": "H", "datetime": ts},
        "AAPL",
        date(2024, 3, 15),
    )
    assert item.datetime == dt_expected
