from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from application.ports.metric_repository import MetricRepository
from domain.metrics.metric import AnalyticalMetric
from infrastructure.db.models.metric_model import MetricModel


class PgMetricRepository(MetricRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: MetricModel) -> AnalyticalMetric:
        return AnalyticalMetric(
            time=model.time,
            base_asset_id=model.base_asset_id,
            comparison_asset_id=model.comparison_asset_id,
            metric_name=str(model.metric_name),
            window_days=model.window_days,
            metric_value=Decimal(str(model.metric_value)),
            calculated_at=model.calculated_at,
        )

    async def save_batch(self, metrics: list[AnalyticalMetric]) -> int:
        if not metrics:
            return 0

        BATCH_SIZE = 500
        total_inserted = 0

        for i in range(0, len(metrics), BATCH_SIZE):
            chunk = metrics[i : i + BATCH_SIZE]

            keys = [
                (
                    m.time,
                    m.base_asset_id,
                    m.comparison_asset_id,
                    m.metric_name,
                    m.window_days,
                )
                for m in chunk
            ]

            result = await self._session.execute(
                select(
                    MetricModel.time,
                    MetricModel.base_asset_id,
                    MetricModel.comparison_asset_id,
                    MetricModel.metric_name,
                    MetricModel.window_days,
                ).where(
                    tuple_(
                        MetricModel.time,
                        MetricModel.base_asset_id,
                        MetricModel.comparison_asset_id,
                        MetricModel.metric_name,
                        MetricModel.window_days,
                    ).in_(keys)
                )
            )

            existing = {
                (
                    row.time,
                    row.base_asset_id,
                    row.comparison_asset_id,
                    row.metric_name,
                    row.window_days,
                )
                for row in result
            }

            new_metrics = [
                m
                for m in chunk
                if (
                    m.time,
                    m.base_asset_id,
                    m.comparison_asset_id,
                    m.metric_name,
                    m.window_days,
                )
                not in existing
            ]

            if not new_metrics:
                continue

            rows = [
                {
                    "time": m.time,
                    "base_asset_id": m.base_asset_id,
                    "comparison_asset_id": m.comparison_asset_id,
                    "metric_name": m.metric_name,
                    "window_days": m.window_days,
                    "metric_value": m.metric_value,
                    "calculated_at": m.calculated_at,
                }
                for m in new_metrics
            ]

            await self._session.execute(
                insert(MetricModel).values(rows)
            )
            total_inserted += len(new_metrics)

        await self._session.flush()
        return total_inserted

    async def find_latest(
        self,
        base_asset_id: int,
        comparison_asset_id: int | None,
        metric_name: str,
        window_days: int,
    ) -> AnalyticalMetric | None:
        result = await self._session.execute(
            select(MetricModel)
            .where(MetricModel.base_asset_id == base_asset_id)
            .where(MetricModel.comparison_asset_id == comparison_asset_id)
            .where(MetricModel.metric_name == metric_name)
            .where(MetricModel.window_days == window_days)
            .order_by(MetricModel.time.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def find_series(
        self,
        base_asset_id: int,
        comparison_asset_id: int | None,
        metric_name: str,
        window_days: int,
        from_time: datetime,
        to_time: datetime,
    ) -> list[AnalyticalMetric]:
        result = await self._session.execute(
            select(MetricModel)
            .where(MetricModel.base_asset_id == base_asset_id)
            .where(MetricModel.comparison_asset_id == comparison_asset_id)
            .where(MetricModel.metric_name == metric_name)
            .where(MetricModel.window_days == window_days)
            .where(MetricModel.time >= from_time)
            .where(MetricModel.time <= to_time)
            .order_by(MetricModel.time.asc())
        )
        return [self._to_domain(m) for m in result.scalars().all()]
