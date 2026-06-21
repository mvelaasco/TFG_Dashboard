"""
build_sankey_csvs.py
--------------------
Reads reglas_intervalos.csv and generates one CSV per consequent symbol
in frontend/public/sankey/.

Each output CSV has the columns:
    antecedent_symbol, interval_label, count

Where interval_label classifies the consequent interval (a rule can belong
to multiple types simultaneously, count is divided equally among them):
    - "negativo" : hi <= 2%
    - "positivo" : lo >= -2%
    - "cruce"    : interval lies within (-5%, 5%) but does not qualify as negative or positive
    - "otro"     : does not fit any of the above

Usage:
    cd NiaARM
    PYTHONPATH=../backend/src python3 scripts/sankey.py
    PYTHONPATH=../backend/src python3 scripts/sankey.py --input reglas_tercera_ejec.csv --output-dir ../frontend/public/sankey3/
Defaults:
    --input      *.csv que contenga las reglas
    --output-dir ../frontend/public/sankey/
"""

import argparse
import csv
import os
import re
from collections import defaultdict

# ---------------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------------
# Matches a stock item in the antecedent, e.g. "MSFT [-12.37, 7.43]%"
# Ignores non-stock items like month([11, 12]) or week_number([505, 766])
ANTECEDENT_ITEM_RE = re.compile(r'([A-Z]+)\s*\[[-\d.,\s]+\]%')

# Matches the full consequent, e.g. "XLK [-17.04, -6.42]%"
CONSEQUENT_RE = re.compile(r'([A-Z]+)\s*\[([-\d.]+),\s*([-\d.]+)\]%')


def classify_interval(lo, hi):
    """
    Classify the consequent interval.
    Returns a list of labels that apply (a rule can belong to multiple types).
    - "negativo" : hi <= 2%
    - "positivo" : lo >= -2%
    - "cruce"    : lo > -5% and hi < 5%
    - "otro"     : does not fit any of the above
    """
    labels = []
    if hi <= 2:
        labels.append("negativo")
    if lo >= -2:
        labels.append("positivo")
    if lo > -5 and hi < 5:
        labels.append("cruce")
    return labels if labels else ["otro"]
    return "otro"


def parse_antecedent_symbols(antecedent):
    """Return list of stock symbols found in the antecedent string."""
    return ANTECEDENT_ITEM_RE.findall(antecedent)


def parse_consequent(consequent):
    """
    Return (symbol, interval_label) for the consequent, or None if unparseable.
    """
    m = CONSEQUENT_RE.match(consequent.strip())
    if not m:
        return None
    symbol = m.group(1)
    lo = float(m.group(2))
    hi = float(m.group(3))
    labels = classify_interval(lo, hi)
    return symbol, labels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="reglas_tercera_ejec.csv",
        help="Path to reglas_intervalos.csv (default: rules_segunda.csv)",
    )
    parser.add_argument(
        "--output-dir",
        default="../frontend/public/sankey3",
        help="Directory to write output CSVs (default: ../frontend/public/sankey3)",
    )
    args = parser.parse_args()

    # counts[consequent_symbol][interval_label][antecedent_symbol] = count
    counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    skipped = 0
    total = 0

    with open(args.input, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            total += 1
            result = parse_consequent(row["consequent"])
            if result is None:
                skipped += 1
                continue
            cons_symbol, labels = result
            ant_symbols = parse_antecedent_symbols(row["antecedent"])
            count_share = 1.0 / len(labels)
            for sym in ant_symbols:
                for label in labels:
                    counts[cons_symbol][label][sym] += count_share

    os.makedirs(args.output_dir, exist_ok=True)

    files_written = 0
    for cons_symbol, labels in counts.items():
        rows = []
        for interval_label, ant_counts in labels.items():
            for ant_symbol, count in ant_counts.items():
                rows.append({
                    "antecedent_symbol": ant_symbol,
                    "interval_label": interval_label,
                    "count": count,
                })

        # Sort for deterministic output: by interval_label then antecedent_symbol
        rows.sort(key=lambda r: (r["interval_label"], r["antecedent_symbol"]))

        out_path = os.path.join(args.output_dir, f"{cons_symbol}.csv")
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["antecedent_symbol", "interval_label", "count"])
            writer.writeheader()
            writer.writerows(rows)

        files_written += 1
        print(f"  Written: {out_path}  ({len(rows)} rows)")

    print(f"\nDone. {total} rules processed, {skipped} skipped, {files_written} files written.")


if __name__ == "__main__":
    main()
