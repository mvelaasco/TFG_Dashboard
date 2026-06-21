from datetime import date, datetime, timezone
import httpx

from application.ports.exceptions import ExternalServiceError, RateLimitExceeded
from application.ports.news_client import NewsClient
from core.config import settings
from domain.news.news_item import NewsItem


class FinnhubClient(NewsClient):
    """
    Cliente HTTP para la API de Finnhub inyectado con un AsyncClient global.
    """
    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, http_client: httpx.AsyncClient):
        # El cliente HTTP se inyecta. NO se instancia aquí.
        self._client = http_client

    async def fetch_news(self, symbol: str, target_date: date) -> list[NewsItem]:
        url = f"{self.BASE_URL}/company-news"
        params = {
            "symbol": symbol.upper(),
            "from": target_date.isoformat(),
            "to": target_date.isoformat(),
            "token": settings.finnhub_api_key,
        }

        try:
            response = await self._client.get(url, params=params, timeout=15.0)
        except httpx.RequestError as e:
            # Propaga el error, no devuelvas vacío. El sistema debe saber que la red falló.
            raise ExternalServiceError(f"Fallo de red al contactar Finnhub: {str(e)}")

        if response.status_code in (401, 403):
            raise PermissionError("API key de Finnhub inválida o sin acceso")
            
        if response.status_code == 429:
            raise RateLimitExceeded("Cuota de Finnhub excedida. Abortando caché.")
            
        if response.status_code != 200:
            raise ExternalServiceError(f"Finnhub devolvió error HTTP {response.status_code}")

        payload = response.json()
        
        # Validación defensiva. Si Finnhub cambia la API y 'datetime' no viene, no explotará aquí,
        # pero es recomendable usar Pydantic para validar este payload si crece en complejidad.
        return [
            self._parse_item(row, symbol, target_date)
            for row in payload
            if isinstance(row, dict) and row.get("headline") and row.get("datetime")
        ]

    @staticmethod
    def _parse_item(row: dict, symbol: str, target_date: date) -> NewsItem:
        dt = datetime.fromtimestamp(row["datetime"], tz=timezone.utc)

        return NewsItem(
            symbol=symbol.upper(),
            date=target_date,
            datetime=dt,
            headline=row.get("headline", ""),
            source=row.get("source"),
            url=row.get("url"),
            summary=row.get("summary")
        )