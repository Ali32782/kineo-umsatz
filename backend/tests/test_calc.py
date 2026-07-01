import os
import tempfile
from datetime import date

import pytest

_test_dir = tempfile.mkdtemp(prefix="kineo-test-")
os.environ["DATA_DIR"] = _test_dir

from calc import (  # noqa: E402
    compute_zeg,
    compute_soll_tage,
    zeg_color,
    parse_csv_umsatz,
    pattern_from_schedule,
    get_feiertage_sets,
    default_feiertage_entries,
    get_pattern,
    get_standort_splits,
    day_pct_to_halves,
    schedule_needs_reseed,
)
from database import init_db, SessionLocal, MAScheduleEntry, Feiertag, Base, engine, seed_all_ma_schedules  # noqa: E402


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
        pat = get_pattern("Test.MA", 5, db=db)
        assert pat["mo"] == 0.20
        assert pat["fr"] == 0.20
    finally:
        db.query(MAScheduleEntry).filter_by(ma_name="Test.MA").delete()
        db.commit()
        db.close()


def test_seed_all_ma_schedules_barbara():
    seed_all_ma_schedules()
    db = SessionLocal()
    try:
        entries = db.query(MAScheduleEntry).filter_by(ma_name="Barbara.V").order_by(MAScheduleEntry.weekday).all()
        assert len(entries) == 4  # Mo–Do
        for e in entries:
            assert e.vm_pct == 0.10
            assert e.nm_pct == 0.10
            assert e.vm_standort == "Wipkingen"
    finally:
        db.close()


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


def test_get_standort_splits_primary_fallback():
    assert get_standort_splits("Emma.L", "Wipkingen") == {"Wipkingen": 1.0}


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
