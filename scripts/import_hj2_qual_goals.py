#!/usr/bin/env python3
"""Importiert HJ2-2026 Quali-Ziele in qual_goals (period HJ2 2026)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--year", type=int, default=2026)
    p.add_argument("--period", default="HJ2 2026")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    from database import SessionLocal, init_db, MAStammdaten
    from hj2_qual_goals_2026 import all_ma_goals
    from qual_goals import replace_qual_goals

    init_db()
    db = SessionLocal()
    try:
        known = {m.name for m in db.query(MAStammdaten).all()}
        payload = all_ma_goals()
        written = 0
        for ma_name, goals in payload.items():
            if ma_name not in known:
                print(f"SKIP {ma_name} (nicht in Stammdaten)")
                continue
            print(f"{ma_name}: {len(goals)} Ziele")
            for g in goals:
                print(f"  - {g['name']}")
            if not args.dry_run:
                replace_qual_goals(
                    db,
                    ma_name=ma_name,
                    year=args.year,
                    period_label=args.period,
                    goals=goals,
                    updated_by="import_hj2_qual",
                )
                written += 1
        if args.dry_run:
            print(f"Dry-run — {len(payload)} MA, nichts geschrieben.")
        else:
            print(f"Fertig — {written} MA → {args.period}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
