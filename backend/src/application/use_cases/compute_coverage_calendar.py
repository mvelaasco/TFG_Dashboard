from dataclasses import dataclass
from datetime import date, timedelta

from application.ports.asset_repository import AssetRepository
from application.ports.price_repository import PriceRepository


@dataclass
class CalendarDay:
    date: date
    actual_count: int
    expected_count: int
    is_weekend: bool


@dataclass
class CoverageCalendarResult:
    from_date: date
    to_date: date
    total_assets: int
    days: list[CalendarDay]


@dataclass
class CoverageCalendarRequest:
    from_date: date
    to_date: date


class ComputeCoverageCalendar:

    def __init__(
        self,
        asset_repo: AssetRepository,
        price_repo: PriceRepository,
    ) -> None:
        self._assets = asset_repo
        self._prices = price_repo

    async def execute(self, request: CoverageCalendarRequest) -> CoverageCalendarResult:
        assets = await self._assets.find_all()
        total_assets = len(assets)

        counts_by_date: dict[date, int] = {}
        for asset in assets:
            dates = await self._prices.find_distinct_dates(
                asset.id, request.from_date, request.to_date,
            )
            for d in dates:
                counts_by_date[d] = counts_by_date.get(d, 0) + 1

        days: list[CalendarDay] = []
        current = request.from_date
        while current <= request.to_date:
            actual = counts_by_date.get(current, 0)
            is_weekend = current.weekday() >= 5
            days.append(CalendarDay(
                date=current,
                actual_count=actual,
                expected_count=total_assets,
                is_weekend=is_weekend,
            ))
            current += timedelta(days=1)

        return CoverageCalendarResult(
            from_date=request.from_date,
            to_date=request.to_date,
            total_assets=total_assets,
            days=days,
        )
