"""Hilfsfunktionen für versionierte Arbeitspläne (gültig ab Monat)."""
from __future__ import annotations

from datetime import date


def month_start_iso(year: int, month: int) -> str:
    return date(year, month, 1).isoformat()


def normalize_valid_from(value: str) -> str:
    """YYYY-MM oder YYYY-MM-DD → YYYY-MM-01."""
    value = value.strip()
    if len(value) == 7:
        return f"{value}-01"
    if len(value) >= 10:
        return f"{value[:7]}-01"
    raise ValueError("Ungültiges Datum — Format YYYY-MM erwartet")


def format_valid_from_label(valid_from: str) -> str:
    """YYYY-MM-01 → «März 2026»."""
    from calc import MONTH_NAMES_DE
    y, m, _ = valid_from.split("-")
    return f"{MONTH_NAMES_DE[int(m)]} {y}"


def get_schedule_entries_for_month(ma_name: str, year: int, month: int, db) -> list:
    """Arbeitsplan-Einträge, die für den Monat gelten (neueste Version mit valid_from ≤ Monat)."""
    from database import MAScheduleEntry, MAScheduleSet

    target = month_start_iso(year, month)
    schedule_set = (
        db.query(MAScheduleSet)
        .filter(MAScheduleSet.ma_name == ma_name, MAScheduleSet.valid_from <= target)
        .order_by(MAScheduleSet.valid_from.desc())
        .first()
    )
    if schedule_set:
        return (
            db.query(MAScheduleEntry)
            .filter_by(schedule_set_id=schedule_set.id)
            .order_by(MAScheduleEntry.weekday)
            .all()
        )
    # Legacy-Einträge ohne Version
    return (
        db.query(MAScheduleEntry)
        .filter_by(ma_name=ma_name, schedule_set_id=None)
        .order_by(MAScheduleEntry.weekday)
        .all()
    )


def create_schedule_set(db, ma_name: str, valid_from: str, days: list[dict]) -> int:
    from database import MAScheduleEntry, MAScheduleSet

    valid_from = normalize_valid_from(valid_from)
    existing = (
        db.query(MAScheduleSet)
        .filter_by(ma_name=ma_name, valid_from=valid_from)
        .first()
    )
    if existing:
        db.query(MAScheduleEntry).filter_by(schedule_set_id=existing.id).delete()
        schedule_set = existing
    else:
        schedule_set = MAScheduleSet(ma_name=ma_name, valid_from=valid_from)
        db.add(schedule_set)
        db.flush()

    for day in days:
        db.add(MAScheduleEntry(
            ma_name=ma_name,
            schedule_set_id=schedule_set.id,
            weekday=day["weekday"],
            vm_pct=day.get("vm_pct", 0),
            vm_standort=day.get("vm_standort"),
            nm_pct=day.get("nm_pct", 0),
            nm_standort=day.get("nm_standort"),
        ))
    return schedule_set.id
