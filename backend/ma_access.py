"""Sichtbarkeit von MA-Datensätzen nach Rolle und expliziter FK-Zuordnung."""
from __future__ import annotations

from datetime import date

from auth import has_full_access

TEAM_SCOPE_ROLES = frozenset({"teamlead", "sl"})

# FK-Heimatstandort — einmalige Korrektur (siehe database._backfill_ma_teams)
CANONICAL_MA_TEAMS: dict[str, str] = {
    "Valerio.S": "Escher Wyss",
}

# CC-Team: welche Kennzahl gilt
CC_KPI_TYPE: dict[str, str] = {
    "Nina.S": "umsatz",
    "Marc.W": "umsatz",
    "Ilaria.F": "mitglieder",
    "Susanne.K": "keine",
    "Larissa.S": "keine",
    "Pamela.P": "keine",
}

# Dashboard-Sonderbereich — nicht in der ZEG-B-Jahresübersicht
SPECIALTY_PERFORMANCE: dict[str, dict] = {
    "Ilaria.F": {
        "units": ["Fitness"],
        "title": "Fitness",
        "kpi": "mitglieder",
    },
    "Nina.S": {
        "units": ["HYROX", "Performance Lab"],
        "title": "HYROX / Performance Lab",
        "kpi": "umsatz",
    },
    "Marc.W": {
        "units": ["Runnerslab", "Performance Lab"],
        "title": "Runnerslab / Performance Lab",
        "kpi": "umsatz",
    },
}

ZEG_OVERVIEW_EXCLUDED = frozenset(SPECIALTY_PERFORMANCE.keys())


def cc_kpi_label(ma_name: str) -> str | None:
    kind = CC_KPI_TYPE.get(ma_name)
    if kind == "umsatz":
        return "Umsatz / ZEG-B"
    if kind == "mitglieder":
        return "Mitgliederzahlen"
    if kind == "keine":
        return "kein Umsatz-KPI"
    return None


def is_zeg_overview_excluded(ma_name: str) -> bool:
    return ma_name in ZEG_OVERVIEW_EXCLUDED


def normalize_team(team: str | None) -> str:
    return (team or "").strip()


def months_for_period(period_label: str | None) -> list[int]:
    """Monate einer Bilat-Periode: HJ1 = Feb–Jul, HJ2 = Aug–Dez (Jan = HJ2 Vorjahr)."""
    if not period_label:
        return list(range(1, 13))
    pl = period_label.upper()
    if "HJ1" in pl or pl.startswith("1."):
        return list(range(2, 8))
    if "HJ2" in pl or pl.startswith("2."):
        return list(range(8, 13))
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


def _legacy_team_visible(ma, user, db, *, year: int | None, months: list[int] | None) -> bool:
    """Fallback wenn fk_username noch nicht gesetzt — Team/Arbeitsplan."""
    team = normalize_team(user.team)
    if not team:
        return False
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
    if user.role not in TEAM_SCOPE_ROLES:
        return True

    linked = getattr(user, "linked_ma_name", None)
    if linked and ma.name == linked:
        return True

    if ma.fk_username:
        return ma.fk_username == user.username

    return _legacy_team_visible(ma, user, db, year=year, months=months)


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
    if user.role not in TEAM_SCOPE_ROLES:
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


ASSIGNABLE_FK_ROLES = ("ceo", "coo", "teamlead")
_FK_ROLE_ORDER = {"ceo": 0, "coo": 1, "teamlead": 2}


def list_assignable_fk_users(db):
    """Führungspersonen für Admin-Dropdown: CEO, COO, Teamleads."""
    from database import User

    users = (
        db.query(User)
        .filter(User.is_active == True, User.role.in_(ASSIGNABLE_FK_ROLES))
        .all()
    )
    users.sort(key=lambda u: (_FK_ROLE_ORDER.get(u.role, 9), (u.full_name or u.username or "").lower()))
    return [
        {
            "username": u.username,
            "full_name": u.full_name or u.username,
            "team": u.team,
            "role": u.role,
        }
        for u in users
    ]


def build_team_fk_index(db) -> dict[str, object]:
    """Standort → zuständige FK (Teamlead bevorzugt, sonst Standortlead)."""
    from database import User

    by_team: dict[str, object] = {}
    for u in db.query(User).filter(
        User.is_active == True,
        User.role.in_(("teamlead", "sl")),
        User.team.isnot(None),
    ).all():
        team = normalize_team(u.team)
        if not team:
            continue
        if u.role == "teamlead" or team not in by_team:
            by_team[team] = u
    return by_team


def resolve_ma_fk_user(ma, db, *, fk_users_by_name: dict | None = None, team_fk_by_team: dict | None = None):
    """Effektive FK — explizite Zuordnung oder Standort-Teamlead/SL."""
    from database import User

    if ma.fk_username:
        if fk_users_by_name and ma.fk_username in fk_users_by_name:
            return fk_users_by_name[ma.fk_username]
        fk = db.query(User).filter_by(username=ma.fk_username).first()
        if fk:
            return fk

    team = normalize_team(ma.team)
    if not team or team in ("Management", "Office"):
        return None

    if team_fk_by_team is None:
        team_fk_by_team = build_team_fk_index(db)
    return team_fk_by_team.get(team)
