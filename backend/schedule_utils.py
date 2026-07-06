"""Hilfsfunktionen für versionierte Arbeitspläne (gültig ab Monat + Monats-Override)."""
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


def _entries_for_set(db, schedule_set) -> list:
    from database import MAScheduleEntry
    return (
        db.query(MAScheduleEntry)
        .filter_by(schedule_set_id=schedule_set.id)
        .order_by(MAScheduleEntry.weekday)
        .all()
    )


def get_schedule_entries_for_month(ma_name: str, year: int, month: int, db) -> list:
    """Monats-Override > Version gültig ab ≤ Monat > Legacy."""
    from database import MAScheduleEntry, MAScheduleSet

    month_override = (
        db.query(MAScheduleSet)
        .filter_by(ma_name=ma_name, override_year=year, override_month=month)
        .first()
    )
    if month_override:
        return _entries_for_set(db, month_override)

    target = month_start_iso(year, month)
    schedule_set = (
        db.query(MAScheduleSet)
        .filter(
            MAScheduleSet.ma_name == ma_name,
            MAScheduleSet.override_year.is_(None),
            MAScheduleSet.valid_from <= target,
        )
        .order_by(MAScheduleSet.valid_from.desc())
        .first()
    )
    if schedule_set:
        return _entries_for_set(db, schedule_set)

    return (
        db.query(MAScheduleEntry)
        .filter_by(ma_name=ma_name, schedule_set_id=None)
        .order_by(MAScheduleEntry.weekday)
        .all()
    )


def _save_schedule_set(db, schedule_set, ma_name: str, days: list[dict]) -> int:
    from database import MAScheduleEntry
    db.query(MAScheduleEntry).filter_by(schedule_set_id=schedule_set.id).delete()
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


def create_schedule_set(db, ma_name: str, valid_from: str, days: list[dict]) -> int:
    from database import MAScheduleSet

    valid_from = normalize_valid_from(valid_from)
    existing = (
        db.query(MAScheduleSet)
        .filter_by(ma_name=ma_name, valid_from=valid_from, override_year=None, override_month=None)
        .first()
    )
    if existing:
        schedule_set = existing
    else:
        schedule_set = MAScheduleSet(ma_name=ma_name, valid_from=valid_from)
        db.add(schedule_set)
        db.flush()
    return _save_schedule_set(db, schedule_set, ma_name, days)


def create_month_schedule_override(db, ma_name: str, year: int, month: int, days: list[dict]) -> int:
    from database import MAScheduleSet

    existing = (
        db.query(MAScheduleSet)
        .filter_by(ma_name=ma_name, override_year=year, override_month=month)
        .first()
    )
    if existing:
        schedule_set = existing
    else:
        schedule_set = MAScheduleSet(
            ma_name=ma_name,
            valid_from=month_start_iso(year, month),
            override_year=year,
            override_month=month,
        )
        db.add(schedule_set)
        db.flush()
    return _save_schedule_set(db, schedule_set, ma_name, days)


def seed_default_schedule_for_ma(db, ma, valid_from: str = "2026-01") -> bool:
    """Arbeitsplan aus MA_PATTERNS + Haupt-Team — nur wenn noch keine Version existiert."""
    from calc import MA_PATTERNS, TAG_PCT, day_pct_to_halves
    from database import MAScheduleSet

    if db.query(MAScheduleSet).filter_by(ma_name=ma.name).first():
        return False

    pat = MA_PATTERNS.get(ma.name)
    if not pat:
        pat = {k: TAG_PCT for k in ("mo", "di", "mi", "do", "fr")}

    standort = ma.team if ma.team not in ("Management", "Office") else None
    day_keys = {0: "mo", 1: "di", 2: "mi", 3: "do", 4: "fr"}
    days: list[dict] = []
    for wd, key in day_keys.items():
        vm, nm = day_pct_to_halves(pat.get(key, 0) or 0)
        if vm or nm:
            days.append({
                "weekday": wd,
                "vm_pct": vm,
                "vm_standort": standort if vm else None,
                "nm_pct": nm,
                "nm_standort": standort if nm else None,
            })
    if not days:
        return False
    create_schedule_set(db, ma.name, valid_from, days)
    return True


def list_schedule_versions(db, ma_name: str) -> list[dict]:
    from database import MAScheduleSet

    sets = (
        db.query(MAScheduleSet)
        .filter_by(ma_name=ma_name)
        .order_by(MAScheduleSet.valid_from.desc())
        .all()
    )
    versions = []
    for s in sets:
        if s.override_year and s.override_month:
            from calc import MONTH_NAMES_DE
            label = f"Nur {MONTH_NAMES_DE[s.override_month]} {s.override_year}"
            versions.append({
                "type": "month",
                "year": s.override_year,
                "month": s.override_month,
                "label": label,
            })
        else:
            versions.append({
                "type": "from",
                "valid_from": s.valid_from[:7],
                "label": f"Ab {format_valid_from_label(s.valid_from)}",
            })
    return versions
