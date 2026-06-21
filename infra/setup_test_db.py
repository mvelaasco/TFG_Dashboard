"""
Crea la base de datos tfg_finance_test y aplica el schema.

Uso:
    PYTHONPATH=src python3 infra/setup_test_db.py

Es idempotente: se puede ejecutar varias veces sin romper nada.
"""
import asyncio
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DB_NAME = "tfg_finance_test"

# DB_USER / DB_PASSWORD / DB_HOST vienen del .env via core.config
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))
from core.config import settings


def _split_sql(sql: str) -> list[str]:
    return [s.strip() + ";" for s in sql.split(";") if s.strip()]


async def main() -> None:
    admin_url = (
        f"postgresql+asyncpg://{settings.db_user}:{settings.db_password}"
        f"@{settings.db_host}:{settings.db_port}/postgres"
    )
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            await conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
        print(f"Base de datos '{TEST_DB_NAME}' creada.")
    except Exception:
        print(f"Base de datos '{TEST_DB_NAME}' ya existe.")
    await admin_engine.dispose()

    test_url = (
        f"postgresql+asyncpg://{settings.db_user}:{settings.db_password}"
        f"@{settings.db_host}:{settings.db_port}/{TEST_DB_NAME}"
    )
    schema_engine = create_async_engine(test_url)

    infra_dir = Path(__file__).resolve().parent
    init_sql = (infra_dir / "init.sql").read_text()
    migration_sql = (infra_dir / "migrations" / "002_pending_assets.sql").read_text()
    migration_003_sql = (infra_dir / "migrations" / "003_drop_unused_rule_columns.sql").read_text()

    async with schema_engine.begin() as conn:
        for stmt in _split_sql(init_sql):
            await conn.execute(text(stmt))
        for stmt in _split_sql(migration_sql):
            await conn.execute(text(stmt))
        for stmt in _split_sql(migration_003_sql):
            await conn.execute(text(stmt))

    await schema_engine.dispose()
    print("Schema aplicado correctamente.")


if __name__ == "__main__":
    asyncio.run(main())
