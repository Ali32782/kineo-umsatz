"""Tests Selbstzahler-Dashboard-Logik."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from database import SessionLocal, init_db
from mitglieder import upsert_mitglieder
from selbstzahler import (
    FITNESS_CHF_PER_MEMBER,
    dashboard_units,
    upsert_selbstzahler_umsatz,
)


def test_fitness_umsatz_from_mitglieder():
    init_db()
    db = SessionLocal()
    try:
        upsert_mitglieder(
            db, ma_name="Ilaria.F", year=2026, month=4, count=159,
            notes=None, updated_by="test",
        )
        units = {u["unit"]: u for u in dashboard_units(db, 2026, 4)}
        assert units["fitness"]["mitglieder"] == 159
        assert units["fitness"]["umsatz"] == round(159 * FITNESS_CHF_PER_MEMBER)
        assert units["fitness"]["status"] == "aktiv"
        assert units["hyrox"]["status"] == "offen"
        assert units["performance_lab"]["status"] == "offen"
        assert units["shop"]["status"] == "offen"
    finally:
        db.close()


def test_shop_from_excel_upsert():
    init_db()
    db = SessionLocal()
    try:
        upsert_selbstzahler_umsatz(
            db, unit="shop", year=2026, month=3, umsatz=12500,
            updated_by="test", notes="excel",
        )
        units = {u["unit"]: u for u in dashboard_units(db, 2026, 3)}
        assert units["shop"]["umsatz"] == 12500
        assert units["shop"]["status"] == "aktiv"
    finally:
        db.close()
