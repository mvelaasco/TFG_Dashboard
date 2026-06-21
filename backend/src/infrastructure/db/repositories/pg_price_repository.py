from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from application.ports.price_repository import PriceRepository
from domain.prices.price import Price
from infrastructure.db.models.price_model import PriceModel


class PgPriceRepository(PriceRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: PriceModel) -> Price:
        return Price(
            time=model.time,
            asset_id=model.asset_id,
            open=Decimal(str(model.open))  if model.open  is not None else None,
            high=Decimal(str(model.high))  if model.high  is not None else None,
            low=Decimal(str(model.low))    if model.low   is not None else None,
            close=Decimal(str(model.close)),
            volume=model.volume,
        )

    async def save_batch(self, prices: list[Price]) -> int:
        if not prices:
            return 0

        # 1. Busca qué (time, asset_id) ya existen en la BD (en lotes de 500)
        CHUNK = 500
        existing: set[tuple[datetime, int]] = set()
        for i in range(0, len(prices), CHUNK):
            chunk = prices[i:i + CHUNK]
            pairs = [(p.time, p.asset_id) for p in chunk]
            result = await self._session.execute(
                select(PriceModel.time, PriceModel.asset_id).where(
                    tuple_(PriceModel.time, PriceModel.asset_id).in_(pairs)
                )
            )
            existing.update((row.time, row.asset_id) for row in result)

        # 2. Filtra solo los precios que no existen todavía
        new_prices = [
            p for p in prices
            if (p.time, p.asset_id) not in existing
        ]

        if not new_prices:
            return 0

        # 3. Inserta solo los nuevos
        rows = [
            {
                "time":     p.time,
                "asset_id": p.asset_id,
                "open":     p.open,
                "high":     p.high,
                "low":      p.low,
                "close":    p.close,
                "volume":   p.volume,
            }
            for p in new_prices
        ]

        for i in range(0, len(rows), CHUNK):
            await self._session.execute(
                insert(PriceModel).values(rows[i:i + CHUNK])
            )
        await self._session.flush()
        return len(new_prices)

    async def find_by_asset(
        self,
        asset_id:  int,
        from_time: datetime,
        to_time:   datetime,
    ) -> list[Price]:
        result = await self._session.execute(
            select(PriceModel)
            .where(PriceModel.asset_id == asset_id)
            .where(PriceModel.time >= from_time)
            .where(PriceModel.time <= to_time)
            .order_by(PriceModel.time.asc())
        )
        return [self._to_domain(m) for m in result.scalars().all()]

    async def find_latest(self, asset_id: int) -> Price | None:
        result = await self._session.execute(
            select(PriceModel)
            .where(PriceModel.asset_id == asset_id)
            .order_by(PriceModel.time.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def find_date_range(self, asset_id: int) -> tuple[date | None, date | None]:
        result = await self._session.execute(
            select(
                func.min(func.date(PriceModel.time)),
                func.max(func.date(PriceModel.time)),
            )
            .where(PriceModel.asset_id == asset_id)
        )
        row = result.one()
        return row[0], row[1]

    async def find_distinct_dates(
        self,
        asset_id: int,
        from_date: date,
        to_date: date,
    ) -> list[date]:
        result = await self._session.execute(
            select(func.date(PriceModel.time))
            .where(PriceModel.asset_id == asset_id)
            .where(PriceModel.time >= from_date)
            .where(PriceModel.time < to_date + timedelta(days=1))
            .distinct()
            .order_by(func.date(PriceModel.time).asc())
        )
        return [row[0] for row in result.all()]

    async def find_last_price_date(self, asset_id: int) -> date | None:
        result = await self._session.execute(
            select(func.max(func.date(PriceModel.time)))
            .where(PriceModel.asset_id == asset_id)
        )
        return result.scalar()

    async def count_by_asset(self, asset_id: int) -> int:
        result = await self._session.execute(
            select(func.count(PriceModel.asset_id))
            .where(PriceModel.asset_id == asset_id)
        )
        return result.scalar() or 0
