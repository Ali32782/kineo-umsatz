"""Tests für MA-Sichtbarkeit nach Team und Arbeitsplan."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from database import SessionLocal, User, MAStammdaten, init_db
from ma_access import filter_mas_for_user, ma_visible_to_user, months_for_period


def _user(role, team):
    u = User(username="x", role=role, team=team)
    return u


def test_months_for_period_hj1():
    assert months_for_period("HJ1 2026") == list(range(1, 7))


def test_teamlead_sees_home_team_and_scheduled_mas():
    init_db()
    db = SessionLocal()
    try:
        hanna = _user("teamlead", "Thalwil")
        all_mas = db.query(MAStammdaten).filter_by(is_active=True).all()
        visible = filter_mas_for_user(all_mas, hanna, db, year=2026, months=[6])
        names = {m.name for m in visible}
        assert "Hanna.R" in names
        assert "Pablo.G" in names  # arbeitet laut Plan in Thalwil
    finally:
        db.close()


def test_clara_sees_valerio_after_team_backfill():
    init_db()
    db = SessionLocal()
    try:
        clara = _user("teamlead", "Escher Wyss")
        valerio = db.query(MAStammdaten).filter_by(name="Valerio.S").first()
        assert valerio is not None
        assert valerio.team == "Escher Wyss"
        all_mas = db.query(MAStammdaten).filter_by(is_active=True).all()
        visible = filter_mas_for_user(all_mas, clara, db, year=2026, months=[5, 6])
        names = {m.name for m in visible}
        assert "Clara.B" in names
        assert "Valerio.S" in names
    finally:
        db.close()


def test_full_access_sees_all():
    init_db()
    db = SessionLocal()
    try:
        ali = _user("ceo", None)
        all_mas = db.query(MAStammdaten).all()
        assert len(filter_mas_for_user(all_mas, ali, db)) == len(all_mas)
    finally:
        db.close()
