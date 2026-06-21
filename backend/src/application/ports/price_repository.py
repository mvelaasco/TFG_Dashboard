from abc import ABC, abstractmethod
from datetime import date, datetime
from domain.prices.price import Price


class PriceRepository(ABC):

    @abstractmethod
    async def save_batch(self, prices: list[Price]) -> int:
        """Inserta en bulk. Devuelve el número de filas insertadas."""
        ...

    @abstractmethod
    async def find_by_asset(
        self,
        asset_id: int,
        from_time: datetime,
        to_time: datetime,
    ) -> list[Price]:
        ...

    @abstractmethod
    async def find_latest(self, asset_id: int) -> Price | None:
        """Último precio disponible para un activo."""
        ...

    @abstractmethod
    async def find_date_range(self, asset_id: int) -> tuple[date | None, date | None]:
        """Rango de fechas con datos (date) para un activo."""
        ...

    @abstractmethod
    async def find_distinct_dates(
        self,
        asset_id: int,
        from_date: date,
        to_date: date,
    ) -> list[date]:
        """Fechas distintas (date) con datos para un activo en rango."""
        ...

    @abstractmethod
    async def find_last_price_date(self, asset_id: int) -> date | None:
        """Última fecha (date) con datos de precio para un activo."""
        ...

    @abstractmethod
    async def count_by_asset(self, asset_id: int) -> int:
        """Número total de registros de precios para un activo."""
        ...
