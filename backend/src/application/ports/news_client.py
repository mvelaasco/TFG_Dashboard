from abc import ABC, abstractmethod
from datetime import date

from domain.news.news_item import NewsItem


class NewsClient(ABC):

    @abstractmethod
    async def fetch_news(self, symbol: str, date: date) -> list[NewsItem]:
        """
        Obtiene noticias de una fuente externa para un símbolo
        y fecha concretos. Devuelve lista vacía si no hay noticias.
        Nunca lanza excepciones de red hacia el caso de uso.
        """
        ...
