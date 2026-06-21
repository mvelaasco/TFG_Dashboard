from abc import ABC, abstractmethod


class PendingAssetRepository(ABC):

    @abstractmethod
    async def enqueue(self, symbol: str, name: str | None, asset_type: str) -> None:
        ...

    @abstractmethod
    async def dequeue(self) -> tuple[str, str | None, str] | None:
        ...

    @abstractmethod
    async def mark(self, symbol: str, status: str) -> None:
        ...

    @abstractmethod
    async def count_pending(self) -> int:
        ...
