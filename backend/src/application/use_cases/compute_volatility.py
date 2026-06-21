from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
import math

from application.ports.asset_repository import AssetRepository
from application.ports.price_repository import PriceRepository


@dataclass
class VolatilityPoint:
    time: datetime
    value: Decimal


@dataclass
class VolatilityRequest:
    symbol: str
    window_days: int = 30
    from_date: date | None = None
    to_date: date | None = None


@dataclass
class VolatilityResult:
    symbol: str
    window_days: int
    series: list[VolatilityPoint]


class ComputeVolatility:

    def __init__(
        self,
        asset_repo: AssetRepository,
        price_repo: PriceRepository,
    ) -> None:
        self._assets = asset_repo
        self._prices = price_repo

    async def execute(self, request: VolatilityRequest) -> VolatilityResult:
        symbol = request.symbol.upper().strip()
        asset = await self._assets.find_by_symbol(symbol)
        if asset is None:
            raise ValueError(f"Activo '{symbol}' no encontrado")

        to_date = request.to_date or date.today()
        to_time = datetime(
            to_date.year, to_date.month, to_date.day,
            23, 59, 59, tzinfo=timezone.utc,
        )

        if request.from_date is None:
            from_time = datetime(2022, 1, 1, tzinfo=timezone.utc)
        else:
            from_time = datetime(
                request.from_date.year,
                request.from_date.month,
                request.from_date.day,
                tzinfo=timezone.utc,
            )

        prices = await self._prices.find_by_asset(asset.id, from_time, to_time)
        if len(prices) < request.window_days + 1:
            return VolatilityResult(
                symbol=symbol,
                window_days=request.window_days,
                series=[],
            )

        closes = [float(p.close) for p in prices]
        times = [p.time for p in prices]

        returns: list[float] = []
        return_times: list[datetime] = []
        for i in range(1, len(closes)):
            if closes[i - 1] <= 0:
                continue
            returns.append(math.log(closes[i] / closes[i - 1]))
            return_times.append(times[i])

        window = request.window_days
        series: list[VolatilityPoint] = []
        for i in range(window - 1, len(returns)):
            window_returns = returns[i - window + 1 : i + 1]
            mean = sum(window_returns) / window
            variance = sum((r - mean) ** 2 for r in window_returns) / (window - 1)
            std_dev = math.sqrt(variance)
            annualized = std_dev * math.sqrt(252)
            series.append(VolatilityPoint(
                time=return_times[i],
                value=Decimal(str(round(annualized, 6))),
            ))

        return VolatilityResult(
            symbol=symbol,
            window_days=window,
            series=series,
        )
