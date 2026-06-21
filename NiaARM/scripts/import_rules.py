"""
Importa association_rules.csv a la base de datos.

Borra las reglas existentes y las reemplaza con las del CSV.

Uso:
    cd NiaARM
    PYTHONPATH=../backend/src python3 scripts/import_rules.py
    PYTHONPATH=../backend/src python3 scripts/import_rules.py --input reglas_tercera_ejec.csv
    """
import asyncio
import csv
import argparse

from sqlalchemy import delete

from core.config import settings
from core.db_session import AsyncSessionFactory
from infrastructure.db.models.rule_model import RuleModel


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Importa reglas de asociación desde CSV a la base de datos."
    )
    parser.add_argument("--input", default="reglas_tercera_ejec.csv",
                        help="Ruta del CSV con reglas (default: reglas_tercera_ejec.csv)")
    args = parser.parse_args()
    csv_path = args.input

    print(f"Conectando a: {settings.db_url}")
    print(f"Leyendo: {csv_path}")

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)

    print(f"Reglas en CSV: {len(rows)}")

    async with AsyncSessionFactory() as session:
        #Ejecuta un borrado sobre la tabla de reglas, elimina las existentes
        await session.execute(delete(RuleModel))
        await session.flush()
        
        #Inserta las nuevas reglas que obtiene del CSV
        for row in rows:
            session.add(RuleModel(
                antecedent=row["antecedent"],
                consequent=row["consequent"],
                lift=row.get("lift"),
                confidence=row.get("confidence"),
                support=row.get("support"),
                netconf=row.get("netconf"),
                amplitude=row.get("amplitude"),
                coverage=row.get("coverage")
            ))

        #Confirma los cambios en la base de datos
        await session.commit()

    print(f"Importadas {len(rows)} reglas correctamente.")


if __name__ == "__main__":
    asyncio.run(main())
