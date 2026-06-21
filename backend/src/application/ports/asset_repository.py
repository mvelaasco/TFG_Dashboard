from abc import ABC, abstractmethod
from datetime import date

from domain.assets.asset import Asset


class AssetRepository(ABC):

    @abstractmethod
    async def save(self, asset: Asset) -> Asset:
        """Persiste un activo y devuelve la entidad con id asignado."""
        ...

    @abstractmethod
    async def find_by_symbol(self, symbol: str) -> Asset | None:
        """Devuelve None si no existe."""
        ...

    @abstractmethod
    async def find_all(self) -> list[Asset]:
        ...

    @abstractmethod
    async def delete_by_symbol(self, symbol: str) -> bool:
        """Elimina un activo por su símbolo. Devuelve True si existía."""
        ...

    @abstractmethod
    async def find_all_with_price_stats(self) -> list[tuple[Asset, date | None, int]]:
        """Retorna activos ordenados por menos datos: precio_count ASC,
        última fecha ASC nulls first. Útil para priorizar ingesta."""
        ...