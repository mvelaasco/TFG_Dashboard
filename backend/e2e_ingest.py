# backend/e2e_ingest.py
"""
Script end-to-end: ingesta precios reales de Tiingo para un conjunto
representativo de activos y los persiste en TimescaleDB.
Ejecutar con:
    PYTHONPATH=src python3 e2e_ingest.py
"""
import asyncio
from datetime import date

from core.config import settings
from core.db_session import AsyncSessionFactory
from application.use_cases.ingest_prices import IngestPrices, IngestPricesRequest
from infrastructure.db.repositories.pg_asset_repository import PgAssetRepository
from infrastructure.db.repositories.pg_price_repository import PgPriceRepository
from infrastructure.external_apis.tiingo_client import TiingoClient


# ---------------------------------------------------------------------------
# Activos a ingerir
# ---------------------------------------------------------------------------

SYMBOLS = [
    # --- Acciones large-cap USA (referencia y correlación) ---
    "AAPL",   # Apple — tecnología, alta liquidez
    "MSFT",   # Microsoft — tecnología, defensiva
    "GOOGL",  # Alphabet — tecnología, publicidad
    "NVDA",   # Nvidia — semiconductores, IA
    "JPM",    # JPMorgan — financiero, referencia bancaria
    "XOM",    # ExxonMobil — energía, correlación con materias primas
    "SAP",    # SAP — tecnología europea, diversificación geográfica
    "CPB",    # Campbell Soup — consumo defensivo, baja volatilidad
    "CLX",    # Clorox — consumo defensivo, baja volatilidad
    "EFX",    # Equifax — financiero, riesgo moderado
    "BA",     # Boeing — industrial, alta volatilidad

    # --- ETFs de índices amplios (referencia de mercado) ---
    "SPY",    # S&P 500 — referencia del mercado USA
    "QQQ",    # Nasdaq 100 — tecnología pesada
    "IWM",    # Russell 2000 — small caps, riesgo mayor
    "DIA",    # Dow Jones Industrial Average

    # --- ETFs sectoriales (diversificación del análisis) ---
    "XLF",    # Financiero
    "XLK",    # Tecnología
    "XLE",    # Energía
    "XLV",    # Salud

    # --- ETFs de renta fija (indicadores de riesgo) ---
    "TLT",    # Bonos del Tesoro USA a 20+ años — proxy del bono 10a
    "SHY",    # Bonos corto plazo — referencia tipo libre de riesgo
    "HYG",    # High yield (bonos basura) — indicador de apetito de riesgo

    # --- ETFs de volatilidad e indicadores de mercado ---
    "VIXY",   # Proxy del VIX — miedo del mercado (VIX no está en Tiingo)
    "GLD",    # Oro — activo refugio
    "UUP",    # Dólar USA index — proxy del DXY
]

FROM_DATE = date(2004, 1, 1)
TO_DATE   = date(2026, 6, 5)


# ---------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------

async def main() -> None:
    print(f"Conectando a: {settings.db_url}")
    print(f"Rango: {FROM_DATE} → {TO_DATE}")
    print(f"Activos: {len(SYMBOLS)}\n")

    exitosos  = []
    fallidos  = []

    async with AsyncSessionFactory() as session:
        use_case = IngestPrices(
            asset_repo=PgAssetRepository(session),
            price_repo=PgPriceRepository(session),
            market_client=TiingoClient(),
        )

        for symbol in SYMBOLS:
            try:
                result = await use_case.execute(IngestPricesRequest(
                    symbol=symbol,
                    from_date=FROM_DATE,
                    to_date=TO_DATE,
                ))
                status = "ya existía" if result.already_existed else "nuevo"
                print(f"  ✓ {result.symbol:<6} {result.rows_inserted:>4} filas ({status})")
                exitosos.append(symbol)
            except Exception as e:
                print(f"  ✗ {symbol:<6} ERROR: {e}")
                fallidos.append((symbol, str(e)))

        await session.commit()

    print(f"\n--- Resumen ---")
    print(f"  Exitosos: {len(exitosos)}/{len(SYMBOLS)}")
    if fallidos:
        print(f"  Fallidos:")
        for sym, err in fallidos:
            print(f"    {sym}: {err}")

    print("\n--- Verifica en la BD ---")
    print('docker exec -it tfg_db psql -U tfg_user -d tfg_finance -c "SELECT a.symbol, COUNT(*) as filas, MIN(ap.time)::date as desde, MAX(ap.time)::date as hasta FROM asset_prices ap JOIN assets a ON a.id = ap.asset_id GROUP BY a.symbol ORDER BY a.symbol;"')


if __name__ == "__main__":
    asyncio.run(main())