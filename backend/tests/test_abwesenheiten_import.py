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
    assert classify_art("Krankheit") == "krank_t"
    assert classify_art("Gleitzeitsaldo Bezug") == "ferien_t"
    assert classify_art("Umzug") == "ferien_t"


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
        assert match_ma_name("Eva Monika Danko", mas) == "Eva.D"
        assert match_ma_name("Sonia Montero Cuevas", mas) == "Sonia.M"
    finally:
        db.close()


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
