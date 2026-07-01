import os
import tempfile

_test_dir = tempfile.mkdtemp(prefix="kineo-sched-test-")
os.environ["DATA_DIR"] = _test_dir

from database import init_db, SessionLocal, MAScheduleEntry, MAScheduleSet, Base, engine  # noqa: E402
from schedule_utils import create_schedule_set, get_schedule_entries_for_month  # noqa: E402
from calc import get_pattern  # noqa: E402


def setup_module():
    Base.metadata.drop_all(bind=engine)
    init_db()


def test_schedule_version_applies_from_month():
    db = SessionLocal()
    try:
        create_schedule_set(db, "Version.Test", "2026-01", [
            {"weekday": 0, "vm_pct": 0.10, "vm_standort": "Seefeld", "nm_pct": 0.10, "nm_standort": "Seefeld"},
        ])
        create_schedule_set(db, "Version.Test", "2026-04", [
            {"weekday": 0, "vm_pct": 0.10, "vm_standort": "Thalwil", "nm_pct": 0.10, "nm_standort": "Thalwil"},
        ])
        db.commit()

        feb = get_schedule_entries_for_month("Version.Test", 2026, 2, db)
        apr = get_schedule_entries_for_month("Version.Test", 2026, 4, db)
        assert feb[0].vm_standort == "Seefeld"
        assert apr[0].vm_standort == "Thalwil"

        feb_pat = get_pattern("Version.Test", 2026, 2, db=db)
        apr_pat = get_pattern("Version.Test", 2026, 4, db=db)
        assert feb_pat["mo"] == 0.20
        assert apr_pat["mo"] == 0.20
    finally:
        db.query(MAScheduleEntry).filter_by(ma_name="Version.Test").delete()
        db.query(MAScheduleSet).filter_by(ma_name="Version.Test").delete()
        db.commit()
        db.close()
