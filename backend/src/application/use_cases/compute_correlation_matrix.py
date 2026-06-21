from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import math

from application.ports.asset_repository import AssetRepository
from application.ports.price_repository import PriceRepository


@dataclass
class CorrelationMatrixRequest:
    top_n: int = 15
    from_date: date | None = None
    to_date: date | None = None


@dataclass
class CorrelationMatrixResult:
    symbols: list[str]
    matrix: list[list[float]]


class ComputeCorrelationMatrix:

    def __init__(
        self,
        asset_repo: AssetRepository,
        price_repo: PriceRepository,
    ) -> None:
        self._assets = asset_repo
        self._prices = price_repo

    async def execute(
        self,
        request: CorrelationMatrixRequest,
    ) -> CorrelationMatrixResult:
        to_date = request.to_date or date.today()
        to_time = datetime(
            to_date.year, to_date.month, to_date.day,
            23, 59, 59, tzinfo=timezone.utc,
        )

        from_date = request.from_date or (to_date - timedelta(days=60))
        from_time = datetime(
            from_date.year, from_date.month, from_date.day,
            tzinfo=timezone.utc,
        )

        assets = await self._assets.find_all()
        if not assets:
            return CorrelationMatrixResult(symbols=[], matrix=[])

        counts: list[tuple[int, str, int]] = []
        for asset in assets:
            n = await self._prices.count_by_asset(asset.id)
            counts.append((asset.id, asset.symbol, n))

        counts.sort(key=lambda x: x[2], reverse=True)
        top = counts[: request.top_n]

        symbols: list[str] = []
        all_series: list[list[tuple[datetime, float]]] = []

        for asset_id, symbol, _ in top:
            prices = await self._prices.find_by_asset(asset_id, from_time, to_time)
            series = [(p.time, float(p.close)) for p in prices]
            if len(series) >= 2:
                symbols.append(symbol)
                all_series.append(series)

        if len(symbols) < 2:
            return CorrelationMatrixResult(symbols=[], matrix=[])

        common_map: dict[datetime, list[float | None]] = {}
        for i, series in enumerate(all_series):
            for t, close in series:
                if t not in common_map:
                    common_map[t] = [None] * len(symbols)
                common_map[t][i] = close

        common_times = sorted(
            t for t, vals in common_map.items()
            if all(v is not None for v in vals)
        )

        if len(common_times) < 2:
            return CorrelationMatrixResult(symbols=[], matrix=[])

        returns: list[list[float]] = [[] for _ in range(len(symbols))]
        for k in range(1, len(common_times)):
            for i in range(len(symbols)):
                prev = common_map[common_times[k - 1]][i]
                curr = common_map[common_times[k]][i]
                if prev and curr and prev > 0 and curr > 0:
                    returns[i].append(math.log(curr / prev))

        n = len(symbols)
        matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            matrix[i][i] = 1.0
            for j in range(i + 1, n):
                corr = _pearson(returns[i], returns[j])
                matrix[i][j] = corr
                matrix[j][i] = corr

        return CorrelationMatrixResult(symbols=symbols, matrix=matrix)


def _pearson(x: list[float], y: list[float]) -> float:
    n = min(len(x), len(y))
    if n < 3:
        return 0.0
    mx = sum(x[:n]) / n
    my = sum(y[:n]) / n
    cov = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    var_x = sum((x[i] - mx) ** 2 for i in range(n))
    var_y = sum((y[i] - my) ** 2 for i in range(n))
    if var_x <= 0 or var_y <= 0:
        return 0.0
    return cov / math.sqrt(var_x * var_y)
