"""Qualitative Ziele für Bilaterals — DB-Source of Truth für Management-UI."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from database import QualGoal


def list_qual_goals(db: Session, ma_name: str, year: int, period_label: str) -> list[QualGoal]:
    return (
        db.query(QualGoal)
        .filter_by(ma_name=ma_name, year=year, period_label=period_label)
        .order_by(QualGoal.sort_order, QualGoal.id)
        .all()
    )


def goals_as_dicts(rows: list[QualGoal]) -> list[dict]:
    return [
        {
            "id": r.id,
            "name": r.name,
            "result": r.result or "",
            "status": r.status or "",
            "detail": r.detail or "",
            "sort_order": r.sort_order or 0,
        }
        for r in rows
    ]


def replace_qual_goals(
    db: Session,
    *,
    ma_name: str,
    year: int,
    period_label: str,
    goals: list[dict],
    updated_by: str | None,
) -> list[QualGoal]:
    db.query(QualGoal).filter_by(
        ma_name=ma_name, year=year, period_label=period_label,
    ).delete()
    rows: list[QualGoal] = []
    for i, g in enumerate(goals):
        name = (g.get("name") or "").strip()
        if not name:
            continue
        row = QualGoal(
            ma_name=ma_name,
            year=year,
            period_label=period_label,
            sort_order=int(g.get("sort_order") if g.get("sort_order") is not None else i),
            name=name,
            result=(g.get("result") or "").strip() or None,
            status=(g.get("status") or "").strip() or None,
            detail=(g.get("detail") or "").strip() or None,
            updated_at=datetime.utcnow(),
            updated_by=updated_by,
        )
        db.add(row)
        rows.append(row)
    db.commit()
    for r in rows:
        db.refresh(r)
    return list_qual_goals(db, ma_name, year, period_label)


def resolve_qual_goals_for_bilat(
    db: Session,
    ma_name: str,
    year: int,
    period_label: str,
) -> list[dict]:
    """DB zuerst; sonst nur eigene Word-Vorlage (kein Default-Fremd-Template)."""
    rows = list_qual_goals(db, ma_name, year, period_label)
    if rows:
        return goals_as_dicts(rows)
    from bilat_template_map import has_own_bilat_template
    if not has_own_bilat_template(ma_name):
        return []
    from bilat_hj1_export import _read_qual_goals_from_template
    return _read_qual_goals_from_template(ma_name)
