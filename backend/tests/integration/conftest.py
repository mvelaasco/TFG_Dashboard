import asyncio
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings

TEST_DB_NAME = "tfg_finance_test"


def _split_sql(sql: str) -> list[str]:
    """Divide un archivo SQL en sentencias individuales."""
    return [s.strip() + ";" for s in sql.split(";") if s.strip()]


@pytest.fixture(scope="session", autouse=True)
async def ensure_test_database():
    """Crea tfg_finance_test con el schema si no existe."""
    admin_url = (
        f"postgresql+asyncpg://{settings.db_user}:{settings.db_password}"
        f"@{settings.db_host}:{settings.db_port}/postgres"
    )
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            await conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    except Exception:
        pass
    await admin_engine.dispose()

    test_url = (
        f"postgresql+asyncpg://{settings.db_user}:{settings.db_password}"
        f"@{settings.db_host}:{settings.db_port}/{TEST_DB_NAME}"
    )
    schema_engine = create_async_engine(test_url)

    infra_dir = Path(__file__).resolve().parents[3] / "infra"

    async with schema_engine.begin() as conn:
        # Comprueba si el schema ya existe para ser idempotente
        try:
            await conn.execute(text("SELECT 1 FROM asset_types LIMIT 1"))
        except Exception:
            init_sql = (infra_dir / "init.sql").read_text()
            migration_sql = (infra_dir / "migrations" / "002_pending_assets.sql").read_text()
            migration_003_sql = (infra_dir / "migrations" / "003_drop_unused_rule_columns.sql").read_text()
            for stmt in _split_sql(init_sql):
                await conn.execute(text(stmt))
            for stmt in _split_sql(migration_sql):
                await conn.execute(text(stmt))
            for stmt in _split_sql(migration_003_sql):
                await conn.execute(text(stmt))

    await schema_engine.dispose()


@pytest.fixture(scope="session")
def event_loop():
    """Fuerza a pytest-asyncio a usar un único bucle de eventos para toda
    la sesión de pruebas. Esto evita que el pool de conexiones de asyncpg
    quede huérfano entre tests."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def engine(event_loop):
    """El motor se amarra explícitamente al único loop de la sesión."""
    test_url = (
        f"postgresql+asyncpg://{settings.db_user}:{settings.db_password}"
        f"@{settings.db_host}:{settings.db_port}/{TEST_DB_NAME}"
    )
    return create_async_engine(
        test_url,
        echo=False,
        pool_size=5,
        max_overflow=0,
    )


@pytest.fixture(scope="session")
def session_factory(engine):
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture(autouse=True)
async def clean_tables(engine):
    """Limpia la base de datos antes de cada test.
    Trabaja sobre tfg_finance_test, nunca toca la BD real."""
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE assets RESTART IDENTITY CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE pending_assets CASCADE;"))
    yield


@pytest.fixture
async def db_session(session_factory) -> AsyncSession:
    """Genera una sesión limpia para cada test individual."""
    async with session_factory() as session:
        yield session
        await session.rollback()
