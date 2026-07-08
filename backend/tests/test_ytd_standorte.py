"""Standorte für Jahresübersicht aus Arbeitsplan."""
import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="kineo-ytd-standorte-")

from database import init_db, SessionLocal  # noqa: E402
from schedule_utils import (  # noqa: E402
    build_schedule_cache,
    collect_ma_standorte_for_year,
    create_schedule_set,
    standorte_from_entries,
)


class _Entry:
    def __init__(self, vm_standort=None, nm_standort=None):
        self.vm_standort = vm_standort
        self.nm_standort = nm_standort


def test_standorte_from_entries_normalizes_aliases():
    assert standorte_from_entries([_Entry("Stauf.", "Thalwil")]) == ["Stauffacher", "Thalwil"]


def test_collect_ma_standorte_for_year_multi_site():
    init_db()
    db = SessionLocal()
    try:
        create_schedule_set(db, "Helen.S", "2026-01", [
            {"weekday": 1, "vm_pct": 0.10, "vm_standort": "Zollikon", "nm_pct": 0.10, "nm_standort": "Zollikon"},
            {"weekday": 2, "vm_pct": 0.10, "vm_standort": "Seefeld", "nm_pct": 0.10, "nm_standort": "Seefeld"},
        ])
        db.commit()
        cache = build_schedule_cache(db, ["Helen.S"], 2026, 6)
        sites = collect_ma_standorte_for_year("Helen.S", cache, 6, "Seefeld", db=db, year=2026)
        assert sites == ["Seefeld", "Zollikon"]
    finally:
        db.close()
