import os
import tempfile

_test_dir = tempfile.mkdtemp(prefix="kineo-umsatz-agg-")
os.environ["DATA_DIR"] = _test_dir

from database import init_db, SessionLocal, MAStammdaten, UmsatzData, Base, engine  # noqa: E402
from umsatz_agg import ma_year_umsatz, monthly_and_year_totals  # noqa: E402
from calc import is_employed_in_month  # noqa: E402


def setup_module():
    Base.metadata.drop_all(bind=engine)
    init_db()


def test_ma_year_umsatz_includes_months_without_soll():
    db = SessionLocal()
    try:
        ma = MAStammdaten(
            name="Umsatz.Test", display_name="U Test", team="Seefeld",
            role="therapeut", bg_pct=1.0, eintritt="2026-01-01", austritt="2026-02-28",
        )
        db.add(ma)
        db.add(UmsatzData(ma_name="Umsatz.Test", year=2026, month=2, umsatz=5000))
        db.add(UmsatzData(ma_name="Umsatz.Test", year=2026, month=3, umsatz=9999))
        db.commit()

        umsatz_map = {(r.ma_name, r.month): r.umsatz for r in db.query(UmsatzData).filter_by(year=2026)}
        total = ma_year_umsatz(umsatz_map, ma, 2026)
        assert total == 5000  # März nicht gezählt (nach Austritt)
    finally:
        db.query(UmsatzData).filter_by(ma_name="Umsatz.Test").delete()
        db.query(MAStammdaten).filter_by(name="Umsatz.Test").delete()
        db.commit()
        db.close()


def test_monthly_totals_match_sum():
    db = SessionLocal()
    try:
        mas = db.query(MAStammdaten).filter_by(is_active=True).all()
        umsatz_map = {(r.ma_name, r.month): r.umsatz for r in db.query(UmsatzData).all()}
        monthly, year_total = monthly_and_year_totals(umsatz_map, mas, 2026)
        assert len(monthly) == 12
        assert year_total == sum(monthly)
    finally:
        db.close()
