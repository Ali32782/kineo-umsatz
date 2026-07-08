"""Sichtbarkeit von MA-Datensätzen nach Rolle, Stammdaten-Team und Arbeitsplan."""
from __future__ import annotations

from datetime import date

from auth import has_full_access

TEAM_SCOPE_ROLES = frozenset({"teamlead", "sl"})

# FK-Heimatstandort — falls in der DB falsch gesetzt (z. B. nach manuellem Edit)
CANONICAL_MA_TEAMS: dict[str, str] = {
    "Valerio.S": "Escher Wyss",
}


def normalize_team(team: str | None) -> str:
    return (team or "").strip()


def months_for_period(period_label: str | None) -> list[int]:
    if not period_label:
        return list(range(1, 13))
    pl = period_label.upper()
    if "HJ1" in pl or pl.startswith("1."):
        return list(range(1, 7))
    if "HJ2" in pl or pl.startswith("2."):
        return list(range(7, 13))
    return list(range(1, 13))


def ma_works_at_standort(
    ma_name: str,
    standort: str,
    db,
    year: int,
    months: list[int],
) -> bool:
    from schedule_utils import get_schedule_entries_for_month

    target = normalize_team(standort)
    if not target:
        return False
    for month in months:
        for entry in get_schedule_entries_for_month(ma_name, year, month, db):
            if normalize_team(entry.vm_standort) == target or normalize_team(entry.nm_standort) == target:
                return True
    return False


_SCHEDULE_ONLY_EXCLUDED_ROLES = frozenset({"management", "bd", "ceo", "coo"})


def ma_visible_to_user(
    ma,
    user,
    db,
    *,
    year: int | None = None,
    months: list[int] | None = None,
) -> bool:
    if has_full_access(user.role):
        return True
    team = normalize_team(user.team)
    if user.role not in TEAM_SCOPE_ROLES or not team:
        return True
    if normalize_team(ma.team) == team:
        return True
    if (ma.role or "") in _SCHEDULE_ONLY_EXCLUDED_ROLES:
        return False
    y = year or date.today().year
    if months is None:
        from calc import reporting_through_month
        through = reporting_through_month(y)
        months = list(range(1, through + 1)) if through else [date.today().month]
    return ma_works_at_standort(ma.name, team, db, y, months)


def filter_mas_for_user(
    mas,
    user,
    db,
    *,
    year: int | None = None,
    months: list[int] | None = None,
):
    if has_full_access(user.role):
        return list(mas)
    team = normalize_team(user.team)
    if user.role not in TEAM_SCOPE_ROLES or not team:
        return list(mas)
    seen: set[str] = set()
    visible = []
    for ma in mas:
        if ma.name in seen:
            continue
        if ma_visible_to_user(ma, user, db, year=year, months=months):
            visible.append(ma)
            seen.add(ma.name)
    return visible
