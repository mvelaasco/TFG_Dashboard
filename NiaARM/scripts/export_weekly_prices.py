"""
Exporta precios de cierre semanales para todos los activos desde 2004-01-02.

Para cada símbolo y semana, toma el último close disponible de esa semana
(habitualmente el viernes, o el último trading day previo si es festivo).

Calcula week_number = 1 para la semana del 2004-01-02.

Resultados:
  - Tabla BD: weekly_prices (UPSERT)
  - Archivo:   weekly_prices.csv

Uso:
    cd NiaARM
    PYTHONPATH=../backend/src python3 scripts/export_weekly_prices.py
    PYTHONPATH=../backend/src python3 scripts/export_weekly_prices.py --csv csv_scripts/weekly_prices.csv
"""
import argparse
import asyncio
import csv
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from core.config import settings
from core.db_session import AsyncSessionFactory
from infrastructure.db.models.weekly_price_model import WeeklyPriceModel
from infrastructure.db.repositories.pg_asset_repository import PgAssetRepository

WEEK_0 = date(2004, 1, 2)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exporta precios semanales (último close de cada semana) a BD y CSV."
    )
    parser.add_argument(
        "--csv",
        default="weekly_prices.csv",
        help="Ruta del CSV de salida (default: weekly_prices.csv)",
    )
    parser.add_argument(
        "--from-date",
        default=WEEK_0,
        type=date.fromisoformat,
        help=f"Fecha inicial (default: {WEEK_0})",
    )
    args = parser.parse_args()

    print(f"Conectando a: {settings.db_url}")

    async with AsyncSessionFactory() as session:
        asset_repo = PgAssetRepository(session)
        all_assets = await asset_repo.find_all()
        print(f"Activos encontrados: {len(all_assets)}\n")

        weekly_sql = text("""
            WITH ranked AS (
                SELECT a.symbol,
                       ap.time::date AS trading_date,
                       ap.close,
                       FLOOR((ap.time::date - :week0) / 7)::INTEGER + 1 AS week_number,
                       ROW_NUMBER() OVER (
                           PARTITION BY a.symbol,
                               FLOOR((ap.time::date - :week0) / 7)::INTEGER
                           ORDER BY ap.time DESC
                       ) AS rn
                FROM asset_prices ap
                JOIN assets a ON a.id = ap.asset_id
                WHERE a.symbol = :symbol
                  AND ap.time >= :week0
            )
            SELECT symbol, week_number, close
            FROM ranked
            WHERE rn = 1
            ORDER BY week_number ASC
        """)

        total_rows = 0

        for asset in all_assets:
            result = await session.execute(
                weekly_sql,
                {"symbol": asset.symbol, "week0": args.from_date},
            )
            rows = result.all()

            if not rows:
                continue

            db_rows = []
            prev_close = None
            for row in rows:
                ws = WEEK_0 + timedelta(weeks=row.week_number - 1)
                pct = None
                if prev_close is not None and prev_close != 0:
                    pct = (float(row.close) - float(prev_close)) / float(prev_close) * 100
                db_rows.append({
                    "symbol": row.symbol,
                    "week_number": row.week_number,
                    "week_start": ws,
                    "close": row.close,
                    "pct_change": pct,
                })
                prev_close = row.close

            stmt = insert(WeeklyPriceModel).values(db_rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "week_number"],
                set_={"close": stmt.excluded.close, "pct_change": stmt.excluded.pct_change},
            )
            await session.execute(stmt)
            await session.flush()

            total_rows += len(db_rows)
            print(f"  ✓ {asset.symbol:<6} {len(db_rows):>5} semanas")

        # Exportar todo a CSV
        all_data = await session.execute(
            text("SELECT symbol, week_number, week_start, close, pct_change "
                 "FROM weekly_prices ORDER BY symbol, week_number")
        )

        with open(args.csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["symbol", "week_number", "week_start", "close", "pct_change"])
            for row in all_data:
                pct = f"{row.pct_change:.6f}" if row.pct_change is not None else ""
                writer.writerow([row.symbol, row.week_number,
                                 row.week_start.isoformat(), row.close, pct])

        await session.commit()

    print(f"\n--- Resumen ---")
    print(f"  Filas en weekly_prices: {total_rows}")
    print(f"  CSV guardado: {args.csv}")


if __name__ == "__main__":
    asyncio.run(main())
