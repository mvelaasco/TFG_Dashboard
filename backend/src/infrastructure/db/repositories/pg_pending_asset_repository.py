from sqlalchemy import select, func, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from application.ports.pending_asset_repository import PendingAssetRepository
from infrastructure.db.models.pending_asset_model import PendingAssetModel


class PgPendingAssetRepository(PendingAssetRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(self, symbol: str, name: str | None, asset_type: str) -> None:
        stmt = insert(PendingAssetModel).values(
            symbol=symbol,
            name=name,
            asset_type=asset_type,
            status="pending",
        ).on_conflict_do_nothing(index_elements=["symbol"])
        await self._session.execute(stmt)

    async def dequeue(self) -> tuple[str, str | None, str] | None:
        result = await self._session.execute(
            select(PendingAssetModel)
            .where(PendingAssetModel.status == "pending")
            .order_by(PendingAssetModel.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.status = "processing"
        await self._session.flush()
        return (row.symbol, row.name, row.asset_type)

    async def mark(self, symbol: str, status: str) -> None:
        await self._session.execute(
            update(PendingAssetModel)
            .where(PendingAssetModel.symbol == symbol)
            .values(status=status)
        )

    async def count_pending(self) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(PendingAssetModel)
            .where(PendingAssetModel.status == "pending")
        )
        return result.scalar() or 0
