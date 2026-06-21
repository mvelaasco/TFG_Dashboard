from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import math

from application.ports.asset_repository import AssetRepository
from application.ports.metric_repository import MetricRepository
from application.ports.price_repository import PriceRepository
from domain.metrics.metric import AnalyticalMetric


@dataclass
class ComputeCorrelationsRequest:
    risk_symbols: list[str]
    from_date: date | None = None
    to_date: date | None = None
    window_days: list[int] = field(default_factory=lambda: [30, 90])
    base_symbols: list[str] | None = None


@dataclass
class ComputeCorrelationsResult:
    metrics_inserted: int
    pairs_processed: int
    missing_risk_symbols: list[str]


class ComputeCorrelations:

    def __init__(
        self,
        asset_repo: AssetRepository,
        price_repo: PriceRepository,
        metric_repo: MetricRepository,
    ) -> None:
        self._assets = asset_repo
        self._prices = price_repo
        self._metrics = metric_repo

    async def execute(
        self,
        request: ComputeCorrelationsRequest,
    ) -> ComputeCorrelationsResult:
        risk_symbols = [s.strip().upper() for s in request.risk_symbols if s.strip()]

        assets = await self._assets.find_all()
        asset_by_symbol = {a.symbol: a for a in assets}

        missing = [s for s in risk_symbols if s not in asset_by_symbol]
        risk_assets = [asset_by_symbol[s] for s in risk_symbols if s in asset_by_symbol]

        if not risk_assets:
            return ComputeCorrelationsResult(
                metrics_inserted=0,
                pairs_processed=0,
                missing_risk_symbols=missing,
            )

        base_assets = [a for a in assets if a.symbol not in risk_symbols]

        if request.base_symbols is not None:
            base_symbols_set = {s.upper().strip() for s in request.base_symbols}
            base_assets = [a for a in base_assets if a.symbol in base_symbols_set]

        to_date = request.to_date or date.today()
        to_time = datetime(
            to_date.year,
            to_date.month,
            to_date.day,
            23,
            59,
            59,
            tzinfo=timezone.utc,
        )

        if request.from_date is None:
            missing_from_date = True
        else:
            missing_from_date = False
            from_time_request = datetime(
                request.from_date.year,
                request.from_date.month,
                request.from_date.day,
                tzinfo=timezone.utc,
            )

        metrics_inserted = 0
        pairs_processed = 0

        for base in base_assets:
            for risk in risk_assets:
                last_time_by_window: dict[int, datetime | None] = {}
                start_times: list[datetime] = []

                for window in request.window_days:
                    metric_name = f"correlation_{window}d"
                    latest = await self._metrics.find_latest(
                        base_asset_id=base.id,
                        comparison_asset_id=risk.id,
                        metric_name=metric_name,
                        window_days=window,
                    )
                    if not missing_from_date:
                        last_time_by_window[window] = None
                        start_times.append(from_time_request)
                    elif latest is not None:
                        last_time_by_window[window] = latest.time
                        start_times.append(latest.time - timedelta(days=window))
                    else:
                        continue

                if not start_times:
                    continue

                from_time = min(start_times)
                if from_time > to_time:
                    continue

                base_prices = await self._prices.find_by_asset(
                    base.id,
                    from_time,
                    to_time,
                )
                risk_prices = await self._prices.find_by_asset(
                    risk.id,
                    from_time,
                    to_time,
                )

                aligned = _align_prices(base_prices, risk_prices)
                if len(aligned) < 2:
                    continue

                return_times, base_returns, risk_returns = _log_returns(aligned)

                metrics: list[AnalyticalMetric] = []
                for window in request.window_days:
                    metric_name = f"correlation_{window}d"
                    last_time = last_time_by_window.get(window)
                    window_metrics = _rolling_correlations(
                        return_times,
                        base_returns,
                        risk_returns,
                        window,
                        metric_name,
                        base.id,
                        risk.id,
                        last_time,
                    )
                    metrics.extend(window_metrics)

                if metrics:
                    metrics_inserted += await self._metrics.save_batch(metrics)
                pairs_processed += 1

        return ComputeCorrelationsResult(
            metrics_inserted=metrics_inserted,
            pairs_processed=pairs_processed,
            missing_risk_symbols=missing,
        )


def _align_prices(base_prices, risk_prices):
    base_map = {p.time: p.close for p in base_prices}
    risk_map = {p.time: p.close for p in risk_prices}

    common_times = sorted(set(base_map).intersection(risk_map))
    return [(t, base_map[t], risk_map[t]) for t in common_times]


def _log_returns(aligned_prices):
    return_times: list[datetime] = []
    base_returns: list[float] = []
    risk_returns: list[float] = []

    for i in range(1, len(aligned_prices)):
        time, base_close, risk_close = aligned_prices[i]
        _, base_prev, risk_prev = aligned_prices[i - 1]

        if base_prev <= 0 or risk_prev <= 0:
            continue

        base_returns.append(math.log(float(base_close / base_prev)))
        risk_returns.append(math.log(float(risk_close / risk_prev)))
        return_times.append(time)

    return return_times, base_returns, risk_returns


def _rolling_correlations(
    return_times: list[datetime],
    base_returns: list[float],
    risk_returns: list[float],
    window: int,
    metric_name: str,
    base_asset_id: int,
    comparison_asset_id: int,
    last_time: datetime | None,
) -> list[AnalyticalMetric]:
    metrics: list[AnalyticalMetric] = []

    if len(base_returns) < window or len(risk_returns) < window:
        return metrics

    for i in range(window - 1, len(base_returns)):
        metric_time = return_times[i]
        if last_time is not None and metric_time <= last_time:
            continue

        window_base = base_returns[i - window + 1 : i + 1]
        window_risk = risk_returns[i - window + 1 : i + 1]
        correlation = _pearson(window_base, window_risk)

        if correlation is None:
            continue

        metrics.append(
            AnalyticalMetric(
                time=metric_time,
                base_asset_id=base_asset_id,
                comparison_asset_id=comparison_asset_id,
                metric_name=metric_name,
                window_days=window,
                metric_value=Decimal(str(correlation)),
            )
        )

    return metrics


def _pearson(x: list[float], y: list[float]) -> float | None:
    n = len(x)
    if n == 0:
        return None

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    var_x = sum((xi - mean_x) ** 2 for xi in x)
    var_y = sum((yi - mean_y) ** 2 for yi in y)

    if var_x <= 0 or var_y <= 0:
        return None

    return cov / math.sqrt(var_x * var_y)
