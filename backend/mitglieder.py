"""Mitgliederzahlen (CC / Ilaria) — monatsweise Kennzahl statt Umsatz/ZEG."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from database import MitgliederData


def list_mitglieder(db: Session, year: int, month: int | None = None) -> list[MitgliederData]:
    q = db.query(MitgliederData).filter(MitgliederData.year == year)
    if month is not None:
        q = q.filter(MitgliederData.month == month)
    return q.order_by(MitgliederData.month, MitgliederData.ma_name).all()


def upsert_mitglieder(
    db: Session,
    *,
    ma_name: str,
    year: int,
    month: int,
    count: float,
    notes: str | None,
    updated_by: str | None,
) -> MitgliederData:
    row = (
        db.query(MitgliederData)
        .filter_by(ma_name=ma_name, year=year, month=month)
        .first()
    )
    if row:
        row.count = float(count)
        row.notes = notes
        row.updated_at = datetime.utcnow()
        row.updated_by = updated_by
    else:
        row = MitgliederData(
            ma_name=ma_name,
            year=year,
            month=month,
            count=float(count),
            notes=notes,
            updated_at=datetime.utcnow(),
            updated_by=updated_by,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def mitglieder_as_dict(row: MitgliederData) -> dict:
    return {
        "ma_name": row.ma_name,
        "year": row.year,
        "month": row.month,
        "count": row.count,
        "notes": row.notes,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "updated_by": row.updated_by,
    }


def parse_mitglieder_csv(text: str) -> list[dict]:
    """
    CSV: ma_name,month,count[,notes]
    oder: Monat;Anzahl (für eine MA — dann ma_name separat setzen)
    """
    import csv
    import io

    raw = (text or "").strip()
    if not raw:
        return []
    sample = raw[:400]
    delim = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(raw), delimiter=delim)
    if not reader.fieldnames:
        return []
    fields = {f.strip().lower(): f for f in reader.fieldnames if f}
    out = []
    for row in reader:
        def get(*names):
            for n in names:
                key = fields.get(n)
                if key and row.get(key) not in (None, ""):
                    return str(row[key]).strip()
            return None

        ma = get("ma_name", "ma", "name", "mitarbeiter")
        month_s = get("month", "monat", "m")
        count_s = get("count", "anzahl", "mitglieder", "value", "zahl")
        notes = get("notes", "notiz", "bemerkung")
        if not month_s or count_s is None:
            continue
        try:
            month = int(float(month_s.replace(",", ".")))
            count = float(count_s.replace("'", "").replace(",", "."))
        except ValueError:
            continue
        if month < 1 or month > 12:
            continue
        out.append({"ma_name": ma, "month": month, "count": count, "notes": notes})
    return out
