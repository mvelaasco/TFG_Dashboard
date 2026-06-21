"""
Minera reglas de asociación sobre el dataset de variaciones semanales.

Usa NiaARM + DifferentialEvolution para encontrar reglas del tipo:
  "IF GLD_pct_change BETWEEN 1.0 AND 3.0 AND month = 8
   THEN AAPL_pct_change BETWEEN -2.5 AND -0.5"

Uso:
    cd NiaARM
    PYTHONPATH=../backend/src python3 scripts/mine_rules.py
    PYTHONPATH=../backend/src python3 scripts/mine_rules.py --input csv_scripts/percentage_dataset.csv --output csv_scripts/rules.csv 
"""
import argparse
import csv
import re
import time
from pathlib import Path

from niaarm import Dataset, get_rules
from niapy.algorithms.basic import DifferentialEvolution

 # Formatea las condiciones de los antecedentes y consecuentes para que sean más legibles, por ejemplo:
 # "GLD_pct_change([1.0, 3.0])" se convierte en "GLD [1.00, 3.00]%"
def _clean_condition(raw: str) -> str:
    inner = raw.strip()
    if inner.startswith("[") and inner.endswith("]"):
        inner = inner[1:-1]

    parts = []
    depth = 0
    buf = ""
    for ch in inner:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(buf.strip())
            buf = ""
            continue
        buf += ch
    if buf.strip():
        parts.append(buf.strip())

    cleaned = []
    for p in parts:
        m = re.match(r'(\w+)_pct_change\(\[([\d.-]+),\s*([\d.-]+)\]\)', p)
        if m:
            sym, lo, hi = m.group(1), float(m.group(2)), float(m.group(3))
            cleaned.append(f"{sym} [{lo:.2f}, {hi:.2f}]%")
        else:
            cleaned.append(p)
    return ", ".join(cleaned)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Minera reglas de asociación con NiaARM."
    )
    parser.add_argument("--input", default="csv_scripts/percentage_dataset.csv")
    parser.add_argument("--output", default="csv_scripts/rules.csv")
    parser.add_argument("--max-iters", type=int, default=750)
    parser.add_argument("--pop-size", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print(f"Cargando dataset: {args.input}")
    data = Dataset(args.input)
    print(data)

    algo = DifferentialEvolution(
        population_size=args.pop_size,
        differential_weight=0.5,
        crossover_probability=0.9,
        seed=args.seed,
    )
    metrics = {"support": 0.05, "confidence": 0.1, "amplitude": 0.15}

    print(f"\nEjecutando DifferentialEvolution (pob={args.pop_size}, iters={args.max_iters})...")
    print(f"Métricas: {metrics}")
    start = time.perf_counter()

    rules, run_time = get_rules(
        data,
        algo,
        metrics,
        max_iters=args.max_iters,
        logging=True,
    )

    elapsed = time.perf_counter() - start

    print(f"\nTiempo de ejecución: {run_time:.2f}s (reloj: {elapsed:.2f}s)")
    print(f"\n{len(rules)} reglas encontradas")

    rules = [r for r in rules
             if r.support >= 0.01
             and r.lift >= 1.1
             and len(r.consequent) <= 1]
    print(f"{len(rules)} reglas tras filtrar (support≥0.01, lift≥1.1, consecuente único)")

    if len(rules) > 0:
        headers = ["antecedent", "consequent", "lift", "confidence", "support", "netconf", "amplitude", "coverage"]
        write_header = not Path(args.output).exists() or Path(args.output).stat().st_size == 0
        with open(args.output, "a", newline="") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(headers)
            for rule in rules:
                writer.writerow([
                    _clean_condition(str(rule.antecedent)),
                    _clean_condition(str(rule.consequent)),
                    round(rule.lift, 3),
                    round(rule.confidence, 3),
                    round(rule.support, 3),
                    round(rule.netconf, 3),
                    round(rule.amplitude, 3),
                    round(rule.coverage, 3),
                ])
        print(f"Reglas exportadas: {args.output} (modo append)")

        print("\n--- Top 10 reglas por lift ---")
        for i, rule in enumerate(sorted(rules, key=lambda r: r.lift, reverse=True)[:10]):
            print(f"{i+1:>2}. {rule}  (lift={rule.lift:.3f}, support={rule.support:.3f})")


if __name__ == "__main__":
    main()
