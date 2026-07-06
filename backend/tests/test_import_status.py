import os
import tempfile
from datetime import datetime

import pytest

_test_dir = tempfile.mkdtemp(prefix="kineo-import-status-")
os.environ["DATA_DIR"] = _test_dir

from database import init_db, SessionLocal, UmsatzData, MonthlyInput, Base, engine  # noqa: E402
from calc import MONTH_NAMES_DE  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    db.add(UmsatzData(
        ma_name="Test.MA", year=2026, month=6, umsatz=12000.0,
        uploaded_at=datetime(2026, 7, 1, 10, 0), uploaded_by="martino",
    ))
    db.add(MonthlyInput(
        ma_name="Test.MA", year=2026, month=6, ferien_t=2.0,
        updated_at=datetime(2026, 7, 2, 9, 0), updated_by="martino",
    ))
    db.commit()
    db.close()
    yield


def test_import_status_aggregation():
    """Gleiche Logik wie /api/import-status — Juni hat Umsatz + Inputs."""
    db = SessionLocal()
    year = 2026
    umsatz_agg = {}
    for row in db.query(UmsatzData).filter(UmsatzData.year == year).all():
        m = row.month
        if m not in umsatz_agg:
            umsatz_agg[m] = {"ma_count": 0, "total": 0.0, "uploaded_by": None}
        umsatz_agg[m]["ma_count"] += 1
        umsatz_agg[m]["total"] += row.umsatz or 0
        umsatz_agg[m]["uploaded_by"] = row.uploaded_by

    june = umsatz_agg[6]
    assert june["ma_count"] == 1
    assert june["total"] == 12000.0
    assert june["uploaded_by"] == "martino"
    assert MONTH_NAMES_DE[6] == "Juni"
    db.close()
