import os
import tempfile
from datetime import date
from pathlib import Path

import pytest

_test_dir = tempfile.mkdtemp(prefix="kineo-test-")
os.environ["DATA_DIR"] = _test_dir

from calc import (  # noqa: E402
    compute_zeg,
    compute_soll_tage,
    zeg_color,
    parse_csv_umsatz,
    parse_csv_umsatz_result,
    parse_chf_amount,
    pattern_from_schedule,
    get_feiertage_sets,
    default_feiertage_entries,
    get_pattern,
    get_standort_splits,
    day_pct_to_halves,
    schedule_needs_reseed,
    get_standort_fte_weights,
    is_employed_in_month,
)
from database import init_db, SessionLocal, MAScheduleEntry, Feiertag, Base, engine, seed_schedules_from_excel  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()
    yield
    Base.metadata.drop_all(bind=engine)


class _ScheduleEntry:
    def __init__(self, weekday, vm_pct, nm_pct=0):
        self.weekday = weekday
        self.vm_pct = vm_pct
        self.nm_pct = nm_pct


def test_zeg_color():
    assert zeg_color(None) == "gray"
    assert zeg_color(1.0) == "green"
    assert zeg_color(0.9) == "amber"
    assert zeg_color(0.8) == "red"


def test_parse_csv_umsatz():
    csv = "Name;Umsatz\nEmma.L;12'500.00\nSumme;999\n"
    assert parse_csv_umsatz(csv)["Emma.L"] == 12500.0


def test_parse_csv_umsatz_filters_by_month_column():
    csv = (
        "Mitarbeiter;Monat;Umsatz\n"
        "Emma L.;1;10'000.00\n"
        "Emma L.;2;11'000.00\n"
        "Emma L.;6;12'500.00\n"
        "Emma L.;6;2'500.00\n"
    )
    result = parse_csv_umsatz_result(csv, year=2026, month=6)
    assert result["by_name"]["Emma L."] == 15000.0
    assert result["rows_skipped"] == 2


def test_parse_csv_umsatz_warns_on_many_rows_without_month():
    lines = ["Name;Umsatz"] + [f"Emma L.;5'000.00" for _ in range(6)]
    result = parse_csv_umsatz_result("\n".join(lines), year=2026, month=6)
    assert result["by_name"]["Emma L."] == 30000.0
    assert any("Monatsexport" in w for w in result["warnings"])


def test_parse_chf_amount_swiss_formats():
    assert parse_chf_amount("1'234.56") == 1234.56
    assert parse_chf_amount("1'234,56") == 1234.56


def test_parse_kineo_pivot_csv_uses_month_column_not_ytd_betrag():
    """Kineo Taxpunkte-Export: Betrag=Jahr, Jun 2026=Monat."""
    fixture = Path(__file__).resolve().parent / "fixtures" / "kineo_taxpunkte_pivot_2026.csv"
    if not fixture.exists():
        return
    content = fixture.read_text(encoding="utf-8-sig")
    result = parse_csv_umsatz_result(content, year=2026, month=6)
    assert abs(result["total"] - 294_940.67) < 1
    assert result["by_name"]["Andrina.K"] == 16043.84
    assert result["by_name"]["Emma.L"] == 24241.2
    assert any("Jahressumme" in w or "Juni" in w for w in result["warnings"])


def test_parse_kineo_pivot_csv_all_months():
    from calc import parse_csv_pivot_all_months_result

    fixture = Path(__file__).resolve().parent / "fixtures" / "kineo_taxpunkte_pivot_2026.csv"
    if not fixture.exists():
        return
    content = fixture.read_text(encoding="utf-8-sig")
    result = parse_csv_pivot_all_months_result(content, 2026)
    assert result is not None
    assert 1 in result["months"]
    assert 6 in result["months"]
    assert len(result["months"]) >= 6
    assert result["by_month"][6]["Andrina.K"] == 16043.84
    assert result["by_month"][1]["Andrina.K"] == 18127.40


def test_compute_soll_tage_emma_may():
    soll = compute_soll_tage("Emma.L", 2026, 5)
    assert soll > 0


def test_compute_zeg_with_umsatz():
    zeg = compute_zeg("Emma.L", 2026, 5, 20000)
    assert zeg["zeg_b"] is not None
    assert zeg["soll_tage"] > 0
    assert 0 < zeg["zeg_b"] < 2


def test_compute_zeg_no_umsatz():
    zeg = compute_zeg("Emma.L", 2026, 5, 0)
    assert zeg["zeg_b"] is None


def test_day_pct_to_halves():
    assert day_pct_to_halves(0.20) == (0.10, 0.10)
    assert day_pct_to_halves(0.10) == (0.10, 0.0)
    assert day_pct_to_halves(0) == (0.0, 0.0)


def test_schedule_needs_reseed():
    assert schedule_needs_reseed([]) is True
    assert schedule_needs_reseed([_ScheduleEntry(0, 0.10, 0.10)]) is False
    assert schedule_needs_reseed([_ScheduleEntry(0, 0.20, 0.20)]) is True


def test_pattern_from_schedule():
    pat = pattern_from_schedule([
        _ScheduleEntry(0, 0.10, 0.10),
        _ScheduleEntry(1, 0.10, 0.10),
    ])
    assert pat["mo"] == 0.20
    assert pat["di"] == 0.20
    assert pat["mgmt"] == 0


def test_feiertage_from_db():
    db = SessionLocal()
    try:
        db.query(Feiertag).filter_by(year=2099).delete()
        db.add(Feiertag(year=2099, date_str="2099-01-01", name="Testfeiertag", faktor=1.0))
        db.commit()
        full, half = get_feiertage_sets(2099, db=db)
        assert date(2099, 1, 1) in full
        assert len(half) == 0
    finally:
        db.query(Feiertag).filter_by(year=2099).delete()
        db.commit()
        db.close()


def test_default_feiertage_entries_2026():
    entries = default_feiertage_entries(2026)
    assert len(entries) >= 10
    assert all(e["date_str"].startswith("2026") for e in entries)


def test_default_feiertage_entries_unknown_year():
    assert default_feiertage_entries(2030) == []


def test_schedule_overrides_hardcoded_pattern():
    db = SessionLocal()
    try:
        db.query(MAScheduleEntry).filter_by(ma_name="Test.MA").delete()
        for wd in range(5):
            db.add(MAScheduleEntry(
                ma_name="Test.MA", weekday=wd, vm_pct=0.10, nm_pct=0.10,
            ))
        db.commit()
        pat = get_pattern("Test.MA", 2026, 5, db=db)
        assert pat["mo"] == 0.20
        assert pat["fr"] == 0.20
    finally:
        db.query(MAScheduleEntry).filter_by(ma_name="Test.MA").delete()
        db.commit()
        db.close()


def test_seed_schedules_from_excel_emma():
    seed_schedules_from_excel()
    db = SessionLocal()
    try:
        entries = db.query(MAScheduleEntry).filter_by(ma_name="Emma.L").order_by(MAScheduleEntry.weekday).all()
        assert len(entries) == 5
        assert entries[1].vm_standort == "Stauffacher"
        assert entries[0].vm_standort == "Thalwil"
    finally:
        db.close()


def test_get_standort_fte_weights_sereina():
    class E:
        def __init__(self, vm_pct, vm_standort, nm_pct=0, nm_standort=None):
            self.vm_pct = vm_pct
            self.vm_standort = vm_standort
            self.nm_pct = nm_pct
            self.nm_standort = nm_standort
    entries = [
        E(0.10, "Office", 0.10, "Seefeld"),
        E(0.10, "Seefeld", 0.10, "Seefeld"),
        E(0.10, "Office", 0.10, "Seefeld"),
        E(0.10, "Seefeld", 0, None),
        E(0.10, "Office", 0.10, "Seefeld"),
    ]
    weights = get_standort_fte_weights("Sereina.U", "Management", 0.9, entries)
    assert weights == {"Seefeld": 0.6}


def test_get_standort_fte_weights_emma_split():
    class E:
        def __init__(self, vm_pct, vm_standort, nm_pct=0, nm_standort=None):
            self.vm_pct = vm_pct
            self.vm_standort = vm_standort
            self.nm_pct = nm_pct
            self.nm_standort = nm_standort
    entries = [
        E(0.10, "Thalwil", 0.10, "Thalwil"),
        E(0.10, "Stauffacher", 0.10, "Stauffacher"),
        E(0.10, "Thalwil", 0.10, "Thalwil"),
        E(0.10, "Stauffacher", 0.10, "Stauffacher"),
        E(0.10, "Thalwil", 0.10, "Thalwil"),
    ]
    weights = get_standort_fte_weights("Emma.L", "Wipkingen", 1.0, entries)
    assert weights == {"Thalwil": 0.6, "Stauffacher": 0.4}


def test_get_standort_splits_helen_meike():
    splits = get_standort_splits("Helen.S", "Zollikon")
    assert splits == {"Zollikon": 0.5, "Seefeld": 0.5}
    splits = get_standort_splits("Meike.V", "Seefeld")
    assert splits == {"Zollikon": 0.5, "Seefeld": 0.5}


def test_get_standort_splits_schedule_overrides():
    class E:
        def __init__(self, vm_pct, vm_standort, nm_pct=0, nm_standort=None):
            self.vm_pct = vm_pct
            self.vm_standort = vm_standort
            self.nm_pct = nm_pct
            self.nm_standort = nm_standort
    entries = [E(0.10, "Wipkingen", 0.10, "Wipkingen")]
    splits = get_standort_splits("Helen.S", "Zollikon", entries)
    assert splits == {"Wipkingen": 1.0}


def test_is_employed_in_month_austritt():
    # Austritt Ende Februar → nicht mehr im März
    assert is_employed_in_month("2026-01-01", "2026-02-28", 2026, 2, True) is True
    assert is_employed_in_month("2026-01-01", "2026-02-28", 2026, 3, True) is False
    # Austritt im März → noch im März gezählt
    assert is_employed_in_month("2026-01-01", "2026-03-15", 2026, 3, True) is True
    assert is_employed_in_month("2026-01-01", "2026-03-15", 2026, 4, True) is False


def test_is_employed_in_month_eintritt():
    assert is_employed_in_month("2026-03-01", None, 2026, 2, True) is False
    assert is_employed_in_month("2026-03-01", None, 2026, 3, True) is True


def test_is_employed_in_month_inactive_without_austritt():
    assert is_employed_in_month("2026-01-01", None, 2026, 3, False) is False


def test_departed_ma_employment_months():
    from database import _backfill_departed_mas, MAStammdaten

    _backfill_departed_mas()
    db = SessionLocal()
    try:
        felica = db.query(MAStammdaten).filter_by(name="Felica K.").first()
        eve = db.query(MAStammdaten).filter_by(name="Eve.S").first()
        assert felica and felica.austritt == "2026-03-31"
        assert eve and eve.austritt == "2026-06-30"
        assert is_employed_in_month(felica.eintritt, felica.austritt, 2026, 3, felica.is_active)
        assert not is_employed_in_month(felica.eintritt, felica.austritt, 2026, 4, felica.is_active)
        assert is_employed_in_month(eve.eintritt, eve.austritt, 2026, 6, eve.is_active)
        assert not is_employed_in_month(eve.eintritt, eve.austritt, 2026, 7, eve.is_active)
    finally:
        db.close()


def test_compute_soll_tage_after_austritt():
    db = SessionLocal()
    try:
        from database import MAStammdaten
        ma = db.query(MAStammdaten).filter_by(name="Barbara.V").first()
        assert ma is not None
        old = ma.austritt
        ma.austritt = "2026-02-28"
        db.commit()
        assert compute_soll_tage("Barbara.V", 2026, 2, db=db) > 0
        assert compute_soll_tage("Barbara.V", 2026, 3, db=db) == 0
    finally:
        ma.austritt = old
        db.commit()
        db.close()


def test_get_feiertage_sets_prefers_db_over_fallback():
    db = SessionLocal()
    try:
        db.query(Feiertag).filter_by(year=2099).delete()
        db.add(Feiertag(year=2099, date_str="2099-06-15", name="Test", faktor=1.0))
        db.commit()
        full_db, _ = get_feiertage_sets(2099, db=db)
        full_fb, _ = get_feiertage_sets(2099)
        assert date(2099, 6, 15) in full_db
        assert date(2099, 6, 15) not in full_fb
    finally:
        db.query(Feiertag).filter_by(year=2099).delete()
        db.commit()
        db.close()
