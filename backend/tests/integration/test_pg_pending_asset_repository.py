import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.repositories.pg_pending_asset_repository import (
    PgPendingAssetRepository,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def clean_pending(engine):
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE pending_assets CASCADE;"))
    yield


async def test_enqueue_adds_pending_row(db_session: AsyncSession):
    repo = PgPendingAssetRepository(db_session)
    await repo.enqueue("AAPL", "Apple Inc.", "stock")
    assert await repo.count_pending() == 1


async def test_enqueue_duplicate_is_ignored(db_session: AsyncSession):
    repo = PgPendingAssetRepository(db_session)
    await repo.enqueue("AAPL", "Apple Inc.", "stock")
    await repo.enqueue("AAPL", "Apple Inc.", "stock")
    assert await repo.count_pending() == 1


async def test_dequeue_returns_oldest_pending(db_session: AsyncSession):
    repo = PgPendingAssetRepository(db_session)
    await repo.enqueue("B", "B Inc.", "stock")
    await repo.enqueue("A", "A Inc.", "stock")
    item = await repo.dequeue()
    assert item is not None
    symbol, name, asset_type = item
    assert symbol == "B"  # first enqueued


async def test_dequeue_changes_status_to_processing(db_session: AsyncSession):
    repo = PgPendingAssetRepository(db_session)
    await repo.enqueue("AAPL", "Apple Inc.", "stock")
    item = await repo.dequeue()
    assert item is not None
    # Dequeue should have set status to "processing"
    assert await repo.count_pending() == 0
    # A second dequeue should return None
    assert await repo.dequeue() is None


async def test_mark_updates_status(db_session: AsyncSession):
    repo = PgPendingAssetRepository(db_session)
    await repo.enqueue("AAPL", "Apple Inc.", "stock")
    await repo.dequeue()
    await repo.mark("AAPL", "done")
    assert await repo.count_pending() == 0


async def test_dequeue_empty_returns_none(db_session: AsyncSession):
    repo = PgPendingAssetRepository(db_session)
    assert await repo.dequeue() is None


async def test_count_pending_only_counts_pending(db_session: AsyncSession):
    repo = PgPendingAssetRepository(db_session)
    await repo.enqueue("A", "A Inc.", "stock")
    await repo.enqueue("B", "B Inc.", "stock")
    await repo.dequeue()  # moves "A" to processing
    assert await repo.count_pending() == 1


async def test_enqueue_without_name(db_session: AsyncSession):
    repo = PgPendingAssetRepository(db_session)
    await repo.enqueue("AAPL", None, "stock")
    assert await repo.count_pending() == 1
    item = await repo.dequeue()
    assert item is not None
    assert item[1] is None
