from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from application.ports.asset_repository import AssetRepository
from application.ports.price_repository import PriceRepository


@dataclass
class CoverageGap:
    start: date
    end: date
    days: int


@dataclass
class CoverageItem:
    symbol: str
    expected_days: int
    available_days: int
    coverage_pct: float
    missing_days: int
    first_date: date
    last_date: date
    freshness_lag_days: int
    record_count: int
    gaps: list[CoverageGap]


@dataclass
class CoverageSummary:
    symbols_count: int
    coverage_pct_avg: float
    symbols_below_threshold: int
    threshold_pct: float


@dataclass
class CoverageResult:
    items: list[CoverageItem]
    summary: CoverageSummary


@dataclass
class ComputeCoverageRequest:
    symbols: list[str] | None
    min_gap_days: int = 2
    threshold_pct: float = 95.0


class ComputeCoverage:

    def __init__(
        self,
        asset_repo: AssetRepository,
        price_repo: PriceRepository,
    ) -> None:
        self._assets = asset_repo
        self._prices = price_repo

    async def execute(self, request: ComputeCoverageRequest) -> CoverageResult:
        if request.min_gap_days < 1:
            raise ValueError("min_gap_days debe ser >= 1")

        if request.symbols is None:
            assets = await self._assets.find_all()
        else:
            symbols = [s.strip().upper() for s in request.symbols if s.strip()]
            assets = [a for a in await self._assets.find_all() if a.symbol in symbols]

        items: list[CoverageItem] = []

        for asset in assets:
            first_date, last_date = await self._prices.find_date_range(asset.id)
            if first_date is None or last_date is None:
                continue

            expected_dates = _generate_weekdays(first_date, last_date)
            expected_days = len(expected_dates)
            if expected_days == 0:
                continue

            available_dates = await self._prices.find_distinct_dates(
                asset.id,
                first_date,
                last_date,
            )
            available_days = len(available_dates)
            missing_days = expected_days - available_days
            coverage_pct = (available_days / expected_days) * 100

            gaps = _compute_gaps(
                expected_dates,
                set(available_dates),
                request.min_gap_days,
            )

            today = date.today()
            record_count = await self._prices.count_by_asset(asset.id)

            items.append(
                CoverageItem(
                    symbol=asset.symbol,
                    expected_days=expected_days,
                    available_days=available_days,
                    coverage_pct=round(coverage_pct, 4),
                    missing_days=missing_days,
                    first_date=first_date,
                    last_date=last_date,
                    freshness_lag_days=(today - last_date).days,
                    record_count=record_count,
                    gaps=gaps,
                )
            )

        summary = _build_summary(items, request.threshold_pct)
        return CoverageResult(items=items, summary=summary)


def _generate_weekdays(from_date: date, to_date: date) -> list[date]:
    days: list[date] = []
    current = from_date
    while current <= to_date:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def _compute_gaps(
    expected_dates: list[date],
    available_dates: set[date],
    min_gap_days: int,
) -> list[CoverageGap]:
    gaps: list[CoverageGap] = []
    gap_start: date | None = None
    gap_length = 0
    last_gap_day: date | None = None

    for day in expected_dates:
        if day in available_dates:
            if gap_start is not None and gap_length >= min_gap_days:
                gaps.append(
                    CoverageGap(
                        start=gap_start,
                        end=last_gap_day or gap_start,
                        days=gap_length,
                    )
                )
            gap_start = None
            gap_length = 0
            last_gap_day = None
            continue

        if gap_start is None:
            gap_start = day
            gap_length = 1
        else:
            gap_length += 1
        last_gap_day = day

    if gap_start is not None and gap_length >= min_gap_days:
        gaps.append(
            CoverageGap(
                start=gap_start,
                end=last_gap_day or gap_start,
                days=gap_length,
            )
        )

    return gaps


def _build_summary(items: list[CoverageItem], threshold_pct: float) -> CoverageSummary:
    if not items:
        return CoverageSummary(
            symbols_count=0,
            coverage_pct_avg=0.0,
            symbols_below_threshold=0,
            threshold_pct=threshold_pct,
        )

    total = sum(i.coverage_pct for i in items)
    avg = round(total / len(items), 4)
    below = sum(1 for i in items if i.coverage_pct < threshold_pct)

    return CoverageSummary(
        symbols_count=len(items),
        coverage_pct_avg=avg,
        symbols_below_threshold=below,
        threshold_pct=threshold_pct,
    )
