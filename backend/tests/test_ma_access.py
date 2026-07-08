"""Tests für MA-Sichtbarkeit nach expliziter FK-Zuordnung."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from database import SessionLocal, User, MAStammdaten, init_db
from ma_access import filter_mas_for_user, months_for_period


def _user(role, team, *, username="tl", linked_ma_name=None):
    u = User(username=username, role=role, team=team, linked_ma_name=linked_ma_name)
    return u


def test_months_for_period_hj1():
    assert months_for_period("HJ1 2026") == list(range(1, 7))


def test_list_assignable_fk_includes_ceo_coo_and_teamleads():
    from ma_access import list_assignable_fk_users

    init_db()
    db = SessionLocal()
    try:
        options = list_assignable_fk_users(db)
        by_user = {o["username"]: o for o in options}
        assert "ali" in by_user
        assert by_user["ali"]["role"] == "ceo"
        assert "sereina" in by_user
        assert by_user["sereina"]["role"] == "coo"
        assert "clara" in by_user
        assert "hanna" in by_user
        assert options[0]["username"] == "ali"
        assert options[1]["username"] == "sereina"
    finally:
        db.close()


def test_teamlead_sees_assigned_mas_by_fk():
    init_db()
    db = SessionLocal()
    try:
        hanna = db.query(User).filter_by(username="hanna").first()
        pablo = db.query(MAStammdaten).filter_by(name="Pablo.G").first()
        pablo.fk_username = "hanna"
        db.commit()

        all_mas = db.query(MAStammdaten).filter_by(is_active=True).all()
        visible = filter_mas_for_user(all_mas, hanna, db, year=2026, months=[6])
        names = {m.name for m in visible}
        assert "Pablo.G" in names
        assert "Hanna.R" in names  # linked_ma_name
    finally:
        db.close()


def test_clara_sees_valerio_when_fk_assigned():
    init_db()
    db = SessionLocal()
    try:
        clara = db.query(User).filter_by(username="clara").first()
        valerio = db.query(MAStammdaten).filter_by(name="Valerio.S").first()
        assert valerio is not None
        valerio.fk_username = "clara"
        db.commit()

        all_mas = db.query(MAStammdaten).filter_by(is_active=True).all()
        visible = filter_mas_for_user(all_mas, clara, db, year=2026, months=[5, 6])
        names = {m.name for m in visible}
        assert "Clara.B" in names
        assert "Valerio.S" in names
    finally:
        db.close()


def test_teamlead_does_not_see_other_fk_mas():
    init_db()
    db = SessionLocal()
    try:
        hanna = db.query(User).filter_by(username="hanna").first()
        valerio = db.query(MAStammdaten).filter_by(name="Valerio.S").first()
        valerio.fk_username = "clara"
        db.commit()

        all_mas = db.query(MAStammdaten).filter_by(is_active=True).all()
        visible = filter_mas_for_user(all_mas, hanna, db, year=2026, months=[6])
        names = {m.name for m in visible}
        assert "Valerio.S" not in names
    finally:
        db.close()


def test_full_access_sees_all():
    init_db()
    db = SessionLocal()
    try:
        ali = _user("ceo", None, username="ali")
        all_mas = db.query(MAStammdaten).all()
        assert len(filter_mas_for_user(all_mas, ali, db)) == len(all_mas)
    finally:
        db.close()


def test_manual_fk_change_survives_restart():
    init_db()
    db = SessionLocal()
    try:
        valerio = db.query(MAStammdaten).filter_by(name="Valerio.S").first()
        valerio.fk_username = "hanna"
        db.commit()
    finally:
        db.close()

    init_db()

    db = SessionLocal()
    try:
        valerio = db.query(MAStammdaten).filter_by(name="Valerio.S").first()
        assert valerio.fk_username == "hanna"
    finally:
        db.close()
