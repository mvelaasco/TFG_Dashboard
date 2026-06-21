from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import selectinload


from application.ports.asset_repository import AssetRepository
from domain.assets.asset import Asset
from domain.assets.asset_type import AssetType
from infrastructure.db.models.asset_model import AssetModel, AssetTypeModel
from infrastructure.db.models.price_model import PriceModel


class PgAssetRepository(AssetRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: AssetModel) -> Asset:
        return Asset(
            id=model.id,
            symbol=model.symbol,
            name=model.name,
            asset_type=AssetType(model.asset_type.name),
            currency=model.currency,
            exchange=model.exchange,
            timezone=model.timezone,
        )

    async def save(self, asset: Asset) -> Asset:
        result = await self._session.execute(
            select(AssetTypeModel).where(
                AssetTypeModel.name == asset.asset_type.value
            )
        )
        asset_type_model = result.scalar_one()

        model = AssetModel(
            symbol=asset.symbol,
            name=asset.name,
            asset_type_id=asset_type_model.id,
            currency=asset.currency,
            exchange=asset.exchange,
            timezone=asset.timezone,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model, ["asset_type"])
        return self._to_domain(model)

    async def find_by_symbol(self, symbol: str) -> Asset | None:
        result = await self._session.execute(
            select(AssetModel)
            .where(AssetModel.symbol == symbol.upper())
            .options(joinedload(AssetModel.asset_type))
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def find_all(self) -> list[Asset]:
        result = await self._session.execute(
            select(AssetModel)
            .options(joinedload(AssetModel.asset_type))
            .order_by(AssetModel.symbol.asc())
        )
        return [self._to_domain(m) for m in result.scalars().all()]

    async def find_all_with_price_stats(self) -> list[tuple[Asset, date | None, int]]:
        result = await self._session.execute(
            select(
                AssetModel,
                func.max(func.date(PriceModel.time)),
                func.count(PriceModel.asset_id),
            )
            .options(selectinload(AssetModel.asset_type))
            .outerjoin(PriceModel, PriceModel.asset_id == AssetModel.id)
            .group_by(AssetModel.id)
            .order_by(
                func.count(PriceModel.asset_id).asc(),
                func.max(func.date(PriceModel.time)).asc().nullsfirst(),
            )
        )
        return [
            (self._to_domain(row[0]), row[1], row[2])
            for row in result.all()
        ]

    async def delete_by_symbol(self, symbol: str) -> bool:
        asset = await self.find_by_symbol(symbol)
        if asset is None:
            return False
        await self._session.execute(
            delete(AssetModel).where(AssetModel.id == asset.id)
        )
        await self._session.flush()
        return True