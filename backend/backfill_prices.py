"""
Backfill: extiende los datos históricos hacia atrás para todos los activos.

Para cada activo, calcula N años antes de su fecha más antigua almacenada
y obtiene esos datos de la API, insertándolos en la BD.

Uso:
    PYTHONPATH=src python3 backend/backfill_prices.py --years 2
"""
import argparse
import asyncio
from datetime import date, timedelta

from core.config import settings
from core.db_session import AsyncSessionFactory
from application.use_cases.ingest_prices import IngestPrices, IngestPricesRequest
from infrastructure.db.repositories.pg_asset_repository import PgAssetRepository
from infrastructure.db.repositories.pg_price_repository import PgPriceRepository
from infrastructure.external_apis.tiingo_client import TiingoClient


def subtract_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:
        return d.replace(year=d.year - years, day=d.day - 1)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill precios históricos hacia atrás para todos los activos."
    )
    parser.add_argument(
        "--years", "-y",
        type=int,
        required=True,
        help="Años hacia atrás desde la fecha más antigua almacenada",
    )
    args = parser.parse_args()
    years = args.years

    if years <= 0:
        print("--years debe ser un número positivo.")
        return

    print(f"Conectando a: {settings.db_url}")

    async with AsyncSessionFactory() as session:
        asset_repo = PgAssetRepository(session)
        price_repo = PgPriceRepository(session)
        use_case = IngestPrices(asset_repo, price_repo, TiingoClient())

        all_assets = await asset_repo.find_all()
        print(f"Activos encontrados: {len(all_assets)}\n")

        exitosos = 0
        fallidos = []
        total_filas = 0

        for asset in all_assets:
            rango = await price_repo.find_date_range(asset.id)
            min_date, max_date = rango

            if min_date is None:
                print(f"  ~ {asset.symbol:<6} sin datos previos — se omite")
                continue

            from_date = subtract_years(min_date, years)

            if from_date >= min_date:
                print(f"  ~ {asset.symbol:<6} fecha mínima {min_date}, "
                      f"no hay margen para {years} año(s) — se omite")
                continue

            to_date = min_date - timedelta(days=1)

            try:
                result = await use_case.execute(IngestPricesRequest(
                    symbol=asset.symbol,
                    from_date=from_date,
                    to_date=to_date,
                ))
                await session.commit()
                print(f"  ✓ {asset.symbol:<6} mín: {min_date} → "
                      f"[{from_date} .. {to_date}] → {result.rows_inserted} filas")
                exitosos += 1
                total_filas += result.rows_inserted
            except Exception as e:
                await session.rollback()
                print(f"  ✗ {asset.symbol:<6} ERROR: {e}")
                fallidos.append((asset.symbol, str(e)))

    print(f"\n--- Resumen ---")
    print(f"  Exitosos: {exitosos}/{len(all_assets)}")
    print(f"  Total filas insertadas: {total_filas}")
    if fallidos:
        print(f"  Fallidos:")
        for sym, err in fallidos:
            print(f"    {sym}: {err}")


if __name__ == "__main__":
    asyncio.run(main())
