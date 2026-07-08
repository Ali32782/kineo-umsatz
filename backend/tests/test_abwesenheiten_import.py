import os
import tempfile
from datetime import date
from pathlib import Path

_test_dir = tempfile.mkdtemp(prefix="kineo-abw-test-")
os.environ["DATA_DIR"] = _test_dir

from database import init_db, SessionLocal, MAStammdaten, Base, engine  # noqa: E402
from abwesenheiten_import import (  # noqa: E402
    match_ma_name,
    weekdays_in_month,
    parse_abwesenheiten_xlsx,
    classify_art,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "Abwesenheiten_Juni_2026.xlsx"


def setup_module():
    Base.metadata.drop_all(bind=engine)
    init_db()


def test_classify_art():
    assert classify_art("Urlaub") == "ferien_t"
    assert classify_art("Unbezahlter Urlaub") == "ferien_t"
    assert classify_art("Krankheit") == "krank_t"
    assert classify_art("Gleitzeitsaldo Bezug") is None
    assert classify_art("Umzug") is None
    assert classify_art("Eigene Hochzeit / Hochzeit von Kindern") is None


def test_weekdays_in_month_clips_range():
    # Meike 29.6.–19.7. → nur Juni-Tage
    days = weekdays_in_month(date(2026, 6, 29), date(2026, 7, 19), 2026, 6)
    assert days == 2  # Mo 29, Di 30


def test_match_ma_names():
    db = SessionLocal()
    try:
        mas = db.query(MAStammdaten).all()
        assert match_ma_name("Clara Benning", mas) == "Clara.B"
        assert match_ma_name("Valerio Lo Sasso", mas) == "Valerio.S"
        assert match_ma_name("Valerio.L.S", mas) == "Valerio.S"
        assert match_ma_name("Eva Monika Danko", mas) == "Eva.D"
        assert match_ma_name("Sonia Montero Cuevas", mas) == "Sonia.M"
    finally:
        db.close()


def test_is_half_day_only_explicit_yes():
    from abwesenheiten_import import _is_half_day
    assert _is_half_day("Ja")
    assert _is_half_day("0.5")
    assert _is_half_day(0.5)
    assert _is_half_day("-") is False
    assert _is_half_day("Nein") is False
    assert _is_half_day("1") is False
    assert _is_half_day(1) is False
    assert _is_half_day(1.0) is False
    assert _is_half_day("") is False
    assert _is_half_day("beggining_of_day") is False
    assert _is_half_day("end_of_day") is False


def test_old_bug_numeric_one_halved_everything():
    """Alter Code: «1» in Halbtag → alles ×0.5. Eva Jan 5 Kranktage → 2.5."""
    from abwesenheiten_import import _is_half_day, weekdays_in_month
    from datetime import date

    def old_is_half(v):
        if v is None:
            return False
        s = str(v).strip().lower()
        return s not in ("", "-", "nein", "no", "false", "0")

    assert old_is_half(1) is True
    assert _is_half_day(1) is False
    von, bis = date(2026, 1, 6), date(2026, 1, 9)
    w = weekdays_in_month(von, bis, 2026, 1)
    assert w == 4.0
    assert w * 0.5 if old_is_half(1) else w == 2.0
    assert w * 0.5 if _is_half_day(1) else w == 4.0


def test_eva_krank_july_three_days():
    """2.7.–6.7. = Do, Fr, Mo → 3 Kranktage (nicht 1.5 durch Halbtag-Bug)."""
    import io
    from datetime import date
    from openpyxl import Workbook
    from abwesenheiten_import import weekdays_in_month, parse_abwesenheiten_xlsx_for_year

    von, bis = date(2026, 7, 2), date(2026, 7, 6)
    assert weekdays_in_month(von, bis, 2026, 7) == 3.0

    wb = Workbook()
    ws = wb.active
    ws.append(["Mitarbeitende", "Abwesenheitsart", "Von", "Bis", "Halbtag"])
    ws.append(["Eva Monika Danko", "Krankheit", von, bis, 1])
    buf = io.BytesIO()
    wb.save(buf)

    db = SessionLocal()
    try:
        mas = db.query(MAStammdaten).all()
        result = parse_abwesenheiten_xlsx_for_year(buf.getvalue(), 2026, mas)
        assert result["by_month"][7]["Eva.D"]["krank_t"] == 3.0
    finally:
        db.close()


def test_eva_krank_july_three_days_or_half():
    """2.7.–6.7. = Do, Fr, Mo → 3 AT; mit Halbtag = 1.5 T."""
    from abwesenheiten_import import weekdays_in_month, _is_half_day
    von, bis = date(2026, 7, 2), date(2026, 7, 6)
    assert weekdays_in_month(von, bis, 2026, 7) == 3.0
    assert weekdays_in_month(von, bis, 2026, 7) * 0.5 == 1.5
    assert _is_half_day("Ja") is True


def test_parse_juni_2026_fixture():
    if not FIXTURE.exists():
        return
    db = SessionLocal()
    try:
        mas = db.query(MAStammdaten).all()
        result = parse_abwesenheiten_xlsx(FIXTURE.read_bytes(), 2026, 6, mas)
        assert "Clara.B" in result["by_ma"]
        clara = result["by_ma"]["Clara.B"]
        assert clara["ferien_t"] >= 1
        assert clara["krank_t"] >= 1
        assert result["details"]
    finally:
        db.close()


def test_parse_year_splits_across_months():
    import io
    from openpyxl import Workbook
    from abwesenheiten_import import parse_abwesenheiten_xlsx_for_year

    wb = Workbook()
    ws = wb.active
    ws.append(["Mitarbeitende", "Abwesenheitsart", "Von", "Bis", "Halbtag"])
    ws.append(["Clara Benning", "Urlaub", date(2026, 1, 5), date(2026, 1, 9), "-"])
    ws.append(["Clara Benning", "Krankheit", date(2026, 6, 10), date(2026, 6, 12), "-"])
    buf = io.BytesIO()
    wb.save(buf)

    db = SessionLocal()
    try:
        mas = db.query(MAStammdaten).all()
        result = parse_abwesenheiten_xlsx_for_year(buf.getvalue(), 2026, mas)
        assert 1 in result["months"]
        assert 6 in result["months"]
        assert result["by_month"][1]["Clara.B"]["ferien_t"] >= 1
        assert result["by_month"][6]["Clara.B"]["krank_t"] >= 1
    finally:
        db.close()
