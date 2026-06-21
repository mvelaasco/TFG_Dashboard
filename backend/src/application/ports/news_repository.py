from abc import ABC, abstractmethod
from datetime import date

from domain.news.news_item import NewsItem


class NewsRepository(ABC):

    @abstractmethod
    async def find_by_symbol_and_date(
        self,
        symbol: str,
        date: date,
    ) -> list[NewsItem]:
        """
        Busca noticias en la BD para un símbolo y fecha.
        Devuelve lista vacía si no hay resultados (cache miss).
        """
        ...

    @abstractmethod
    async def save_batch(self, items: list[NewsItem]) -> int:
        """
        Persiste una lista de noticias. Devuelve el número
        de filas insertadas.
        """
        ...
