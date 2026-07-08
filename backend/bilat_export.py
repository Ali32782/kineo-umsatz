import os
import zipfile

from sqlalchemy.orm import Session

from bilat_hj1_export import fill_hj1_template
from calc import MONTH_NAMES_DE, is_employed_in_month
from database import BilatData, MAStammdaten, MonthlyInput, UmsatzData, User
from ma_access import filter_mas_for_user, ma_visible_to_user, months_for_period

EXPORTS_DIR = os.environ.get("EXPORTS_DIR", os.path.join(os.path.dirname(__file__), "../exports"))


def _half_for_month(month: int) -> int:
    return 1 if month <= 6 else 2


def _safe_filename(ma_name: str) -> str:
    return ma_name.replace(".", "_").replace(" ", "_")


def _bilat_filename(ma_name: str, year: int) -> str:
    return f"Bilat_{_safe_filename(ma_name)}_HJ1_{year}.docx"


def generate_bilats_zip(year: int, month: int, db: Session, current_user: User, period_label: str = None) -> str:
    all_mas = db.query(MAStammdaten).all()
    mas = [
        m for m in all_mas
        if any(is_employed_in_month(m.eintritt, m.austritt, year, mo, m.is_active) for mo in range(1, month + 1))
    ]
    mas = filter_mas_for_user(
        mas, current_user, db,
        year=year,
        months=list(range(1, month + 1)),
    )

    umsatz_all = {}
    inputs_all = {}
    for m in range(1, month + 1):
        for r in db.query(UmsatzData).filter(UmsatzData.year == year, UmsatzData.month == m).all():
            umsatz_all[(r.ma_name, m)] = r.umsatz
        for r in db.query(MonthlyInput).filter(MonthlyInput.year == year, MonthlyInput.month == m).all():
            inputs_all[(r.ma_name, m)] = r

    if period_label:
        bilat_all = {b.ma_name: b for b in db.query(BilatData).filter_by(year=year, period_label=period_label).all()}
    else:
        half = _half_for_month(month)
        bilat_all = {b.ma_name: b for b in db.query(BilatData).filter_by(year=year, half=half).all()}

    os.makedirs(EXPORTS_DIR, exist_ok=True)
    zip_path = os.path.join(EXPORTS_DIR, f"Bilats_{MONTH_NAMES_DE[month]}_{year}.zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for ma in mas:
            bilat = bilat_all.get(ma.name)
            doc_path = _generate_bilat_doc(ma, year, month, umsatz_all, inputs_all, bilat, db=db)
            zf.write(doc_path, os.path.basename(doc_path))
            os.remove(doc_path)

    return zip_path


def _generate_bilat_doc(
    ma: MAStammdaten,
    year: int,
    month: int,
    umsatz_all: dict,
    inputs_all: dict,
    bilat: BilatData | None = None,
    db=None,
) -> str:
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    path = os.path.join(EXPORTS_DIR, _bilat_filename(ma.name, year))
    return fill_hj1_template(ma, year, month, umsatz_all, inputs_all, bilat, db, path)


def generate_single_bilat(year: int, month: int, ma_name: str, db, period_label: str = None) -> str:
    ma = db.query(MAStammdaten).filter_by(name=ma_name).first()
    if not ma:
        raise ValueError(f"MA {ma_name} not found")
    if not is_employed_in_month(ma.eintritt, ma.austritt, year, month, ma.is_active):
        raise ValueError(f"MA {ma_name} war im Berichtsmonat nicht angestellt")

    umsatz_all = {(r.ma_name, r.month): r.umsatz for r in db.query(UmsatzData).filter(UmsatzData.year == year).all()}
    inputs_all = {(r.ma_name, r.month): r for r in db.query(MonthlyInput).filter(MonthlyInput.year == year).all()}

    if period_label:
        bilat = db.query(BilatData).filter_by(ma_name=ma_name, year=year, period_label=period_label).first()
    else:
        half = _half_for_month(month)
        bilat = db.query(BilatData).filter_by(ma_name=ma_name, year=year, half=half).first()

    return _generate_bilat_doc(ma, year, month, umsatz_all, inputs_all, bilat, db=db)
