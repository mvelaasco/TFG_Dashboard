from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from application.ports.news_repository import NewsRepository
from domain.news.news_item import NewsItem
from infrastructure.db.models.news_model import NewsModel


class PgNewsRepository(NewsRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: NewsModel) -> NewsItem:
        return NewsItem(
            id=model.id,
            symbol=model.symbol,
            date=model.date,
            datetime=model.datetime,
            headline=model.headline,
            source=model.source,
            url=model.url,
            summary=model.summary,
        )

    async def find_by_symbol_and_date(
        self,
        symbol: str,
        date: date,
    ) -> list[NewsItem]:
        result = await self._session.execute(
            select(NewsModel)
            .where(NewsModel.symbol == symbol.upper())
            .where(NewsModel.date == date)
            .order_by(NewsModel.datetime.desc())
        )
        return [self._to_domain(m) for m in result.scalars().all()]

    async def save_batch(self, items: list[NewsItem]) -> int:
        if not items:
            return 0

        rows = [
            {
                "symbol": item.symbol,
                "date": item.date,
                "datetime": item.datetime,
                "headline": item.headline,
                "source": item.source,
                "url": item.url,
                "summary": item.summary,
            }
            for item in items
        ]

        stmt = insert(NewsModel).values(rows)
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_historical_news_symbol_datetime_url"
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount or 0
