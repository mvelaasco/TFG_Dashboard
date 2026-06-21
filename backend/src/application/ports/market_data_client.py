from abc import ABC, abstractmethod
from datetime import date
from domain.prices.price import Price
from domain.assets.asset import Asset


class MarketDataClient(ABC):

    @abstractmethod
    async def fetch_daily_prices(
        self,
        symbol: str,
        from_date: date,
        to_date: date,
    ) -> list[Price]:
        """
        Llama a la API externa y devuelve precios ya normalizados
        como entidades de dominio. Nunca devuelve JSON crudo.
        """
        ...

    @abstractmethod
    async def fetch_asset_metadata(self, symbol: str) -> Asset | None:
        """
        Devuelve los metadatos del activo o None si no existe
        en la fuente de datos.
        """
        ...