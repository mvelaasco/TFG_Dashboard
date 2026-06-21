import pytest
from datetime import date, datetime, timezone

from application.ports.news_client import NewsClient
from application.ports.news_repository import NewsRepository
from application.use_cases.get_news import GetNews, GetNewsRequest
from domain.news.news_item import NewsItem


def _make_item(symbol: str = "AAPL", d: date = date(2024, 3, 15)) -> NewsItem:
    return NewsItem(
        symbol=symbol,
        date=d,
        datetime=datetime(2024, 3, 15, 14, 0, 0, tzinfo=timezone.utc),
        headline="Apple lanza nuevo producto",
        source="Reuters",
        url="https://reuters.com/article/123",
    )


class InMemoryNewsRepository(NewsRepository):
    def __init__(self):
        self._store: list[NewsItem] = []

    async def find_by_symbol_and_date(self, symbol, date):
        return [
            i for i in self._store
            if i.symbol == symbol and i.date == date
        ]

    async def save_batch(self, items):
        self._store.extend(items)
        return len(items)


class StubNewsClient(NewsClient):
    def __init__(self, items: list[NewsItem]):
        self._items = items
        self.call_count = 0

    async def fetch_news(self, symbol, date):
        self.call_count += 1
        return self._items


@pytest.fixture
def target_date():
    return date(2024, 3, 15)


async def test_cache_miss_calls_client_and_persists(target_date):
    repo = InMemoryNewsRepository()
    client = StubNewsClient([_make_item()])
    uc = GetNews(news_repo=repo, news_client=client)

    result = await uc.execute(GetNewsRequest(symbol="AAPL", date=target_date))

    assert len(result) == 1
    assert client.call_count == 1
    assert len(repo._store) == 1


async def test_cache_hit_does_not_call_client(target_date):
    repo = InMemoryNewsRepository()
    repo._store.append(_make_item())
    client = StubNewsClient([_make_item()])
    uc = GetNews(news_repo=repo, news_client=client)

    result = await uc.execute(GetNewsRequest(symbol="AAPL", date=target_date))

    assert len(result) == 1
    assert client.call_count == 0


async def test_second_request_uses_cache(target_date):
    repo = InMemoryNewsRepository()
    client = StubNewsClient([_make_item()])
    uc = GetNews(news_repo=repo, news_client=client)

    await uc.execute(GetNewsRequest(symbol="AAPL", date=target_date))
    await uc.execute(GetNewsRequest(symbol="AAPL", date=target_date))

    assert client.call_count == 1


async def test_empty_response_from_client_returns_empty_list(target_date):
    repo = InMemoryNewsRepository()
    client = StubNewsClient([])
    uc = GetNews(news_repo=repo, news_client=client)

    result = await uc.execute(GetNewsRequest(symbol="AAPL", date=target_date))

    assert result == []
    assert len(repo._store) == 0


async def test_symbol_is_normalized(target_date):
    repo = InMemoryNewsRepository()
    client = StubNewsClient([_make_item(symbol="aapl")])
    uc = GetNews(news_repo=repo, news_client=client)

    result = await uc.execute(GetNewsRequest(symbol="aapl", date=target_date))

    assert result[0].symbol == "AAPL"


def test_news_item_requires_timezone():
    with pytest.raises(ValueError):
        NewsItem(
            symbol="AAPL",
            date=date(2024, 3, 15),
            datetime=datetime(2024, 3, 15, 14, 0, 0),
            headline="Test",
            url="https://example.com",
        )


def test_news_client_is_abstract():
    with pytest.raises(TypeError):
        NewsClient()


def test_news_repository_is_abstract():
    with pytest.raises(TypeError):
        NewsRepository()
