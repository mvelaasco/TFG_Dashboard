from dataclasses import dataclass
from datetime import date

from application.ports.news_client import NewsClient
from application.ports.news_repository import NewsRepository
from domain.news.news_item import NewsItem


@dataclass
class GetNewsRequest:
    symbol: str
    date: date


class GetNews:
    """
    Caso de uso: devuelve noticias para un símbolo y fecha.
    Implementa el patrón Cache-Aside.
    """

    def __init__(
        self,
        news_repo: NewsRepository,
        news_client: NewsClient,
    ) -> None:
        self._repo = news_repo
        self._client = news_client

    async def execute(self, request: GetNewsRequest) -> list[NewsItem]:
        symbol = request.symbol.upper().strip()

        # 1. Busca en la caché (PostgreSQL)
        cached = await self._repo.find_by_symbol_and_date(symbol, request.date)
        if cached:
            return cached

        # 2. Llama a la API (Si hay error de red o rate limit, aborta aquí automáticamente)
        items = await self._client.fetch_news(symbol, request.date)
        
        if not items:
            return []

        # 3. Persiste directamente (El cliente de infraestructura ya construyó las entidades bien)
        await self._repo.save_batch(items)
        
        return items