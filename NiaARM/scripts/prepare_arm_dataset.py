"""
Preprocesa weekly_prices.csv para minería de reglas de asociación.

Convierte el formato largo (symbol, week, close) a formato ancho:
  - Una fila por semana
  - Una columna por símbolo con la variación porcentual
  - Columna 'month' extraída de la fecha (para detectar estacionalidad)

Uso:
    cd NiaARM
    PYTHONPATH=../backend/src python3 scripts/prepare_arm_dataset.py
    PYTHONPATH=../backend/src python3 scripts/prepare_arm_dataset.py --input csv_scripts/weekly_prices.csv --output csv_scripts/percentage_dataset.csv
"""
import argparse

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepara dataset semanal de precios para NiaARM."
    )
    parser.add_argument("--input", default="csv_scripts/weekly_prices.csv")
    parser.add_argument("--output", default="csv_scripts/percentage_dataset.csv")
    args = parser.parse_args()

    df = pd.read_csv(args.input, parse_dates=["week_start"])
    print(f"Leído: {args.input} — {len(df)} filas, {df.symbol.nunique()} símbolos")

    counts = df["symbol"].value_counts()
    valid = counts[counts >= 1000].index
    df = df[df["symbol"].isin(valid)]
    print(f"Símbolos con ≥1000 semanas: {df.symbol.nunique()}")

    # 1. Pivotar: filas = semanas, columnas = símbolos, valores = close
    pivoted = df.pivot(
        index="week_start", columns="symbol", values="close"
    ).sort_index()

    # 2. Calcular cambio porcentual semanal
    pct = pivoted.pct_change() * 100.0

    # 3. Renombrar columnas: symbol -> symbol_pct_change
    pct.columns = [f"{col}_pct_change" for col in pct.columns]

    # 4. Añadir mes como categórica
    pct["month"] = pct.index.month.astype(str)

    # 5. Eliminar primera fila (NaN por el pct_change)
    pct = pct.dropna(how="all").reset_index()

    # 6. Convertir week_start a número de semana (1 = semana del 2004-01-02)
    pct["week_number"] = (pct["week_start"] - pd.Timestamp("2004-01-02")).dt.days // 7 + 1
    pct = pct.drop(columns=["week_start"])

    print(f"Guardado: {args.output} — {len(pct)} semanas, {len(pct.columns) - 1} features + week_number + month")
    pct.to_csv(args.output, index=False)


if __name__ == "__main__":
    main()
