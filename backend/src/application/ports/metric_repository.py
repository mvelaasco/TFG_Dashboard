from abc import ABC, abstractmethod
from datetime import datetime
from domain.metrics.metric import AnalyticalMetric


class MetricRepository(ABC):

    @abstractmethod
    def save_batch(self, metrics: list[AnalyticalMetric]) -> int:
        ...

    @abstractmethod
    def find_latest(
        self,
        base_asset_id: int,
        comparison_asset_id: int | None,
        metric_name: str,
        window_days: int,
    ) -> AnalyticalMetric | None:
        ...

    @abstractmethod
    def find_series(
        self,
        base_asset_id: int,
        comparison_asset_id: int | None,
        metric_name: str,
        window_days: int,
        from_time: datetime,
        to_time: datetime,
    ) -> list[AnalyticalMetric]:
        """Serie temporal de una métrica para renderizar en el frontend."""
        ...
