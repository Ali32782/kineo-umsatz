#!/usr/bin/env python3
"""Importiert Fitness-Abo + Runnerslab Excel in die lokale/REMOTE DB (DATABASE_URL)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

DEFAULT_FITNESS = BACKEND / "fixtures" / "fitness_abo_thalwil.xlsx"
DEFAULT_RUNNERS = BACKEND / "fixtures" / "runnerslab_umsaetze.xlsx"


def main() -> int:
    p = argparse.ArgumentParser(description="CC-KPI Excel → DB")
    p.add_argument("--fitness", type=Path, default=DEFAULT_FITNESS)
    p.add_argument("--runnerslab", type=Path, default=DEFAULT_RUNNERS)
    p.add_argument("--ilaria", default="Ilaria.F")
    p.add_argument("--marc", default="Marc.W")
    args = p.parse_args()

    from database import SessionLocal, init_db, UmsatzData, MAStammdaten
    from fitness_abo_import import parse_fitness_abo_excel
    from runnerslab_import import parse_runnerslab_excel
    from mitglieder import upsert_mitglieder
    from datetime import datetime

    init_db()
    db = SessionLocal()
    try:
        if args.fitness.is_file():
            rows = parse_fitness_abo_excel(args.fitness)
            for r in rows:
                upsert_mitglieder(
                    db,
                    ma_name=args.ilaria,
                    year=r["year"],
                    month=r["month"],
                    count=r["count"],
                    notes="Fitness-Abo Excel",
                    updated_by="import_cc_kpis",
                )
            print(f"Fitness: {len(rows)} Monate → {args.ilaria}")
            for r in rows:
                if r["year"] >= 2025:
                    print(f"  {r['year']}-{r['month']:02d}: {r['count']}")
        else:
            print(f"Übersprungen (fehlt): {args.fitness}")

        if args.runnerslab.is_file():
            if not db.query(MAStammdaten).filter_by(name=args.marc).first():
                print(f"FEHLER: {args.marc} nicht in Stammdaten")
                return 1
            rows = parse_runnerslab_excel(args.runnerslab)
            for r in rows:
                row = (
                    db.query(UmsatzData)
                    .filter_by(ma_name=args.marc, year=r["year"], month=r["month"])
                    .first()
                )
                if row:
                    row.umsatz = r["umsatz"]
                    row.uploaded_by = "import_cc_kpis"
                    row.uploaded_at = datetime.utcnow()
                else:
                    db.add(
                        UmsatzData(
                            ma_name=args.marc,
                            year=r["year"],
                            month=r["month"],
                            umsatz=r["umsatz"],
                            uploaded_by="import_cc_kpis",
                        )
                    )
            db.commit()
            print(f"Runnerslab: {len(rows)} Monate → {args.marc}")
            for r in rows:
                if r["year"] >= 2025:
                    print(f"  {r['year']}-{r['month']:02d}: {r['umsatz']}")
        else:
            print(f"Übersprungen (fehlt): {args.runnerslab}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
