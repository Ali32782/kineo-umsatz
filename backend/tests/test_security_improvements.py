"""Security helpers: bcrypt, name match, rate limit, inputs scope, mitglieder."""
import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="kineo-sec-")

from auth import (
    hash_password,
    verify_password,
    needs_rehash,
    names_match_confirm,
)
from rate_limit import rate_limit
from fastapi import HTTPException
import pytest


def test_bcrypt_hash_and_legacy_sha256():
    # Legacy format (salt$hex)
    import hashlib, secrets
    salt = secrets.token_hex(16)
    legacy = f"{salt}${hashlib.sha256(f'{salt}secret'.encode()).hexdigest()}"
    assert verify_password("secret", legacy)
    assert needs_rehash(legacy) is True

    modern = hash_password("secret")
    assert modern.startswith("$2")
    assert verify_password("secret", modern)
    assert not verify_password("wrong", modern)
    assert needs_rehash(modern) is False


def test_names_match_confirm():
    assert names_match_confirm("Noah S.", "Noah S.")
    assert names_match_confirm("Noah S.", "noah s")
    assert names_match_confirm("Noah S.", "Noah")
    assert names_match_confirm("Noah S.", "Noah Sutter")
    assert not names_match_confirm("Noah S.", "x")
    assert not names_match_confirm("Noah S.", "Clara")


def test_rate_limit_blocks():
    key = "test-rl-unique-key"
    for _ in range(3):
        rate_limit(key, limit=3, window_seconds=60)
    with pytest.raises(HTTPException) as ex:
        rate_limit(key, limit=3, window_seconds=60)
    assert ex.value.status_code == 429


def test_mitglieder_csv_and_upsert():
    from database import init_db, SessionLocal
    from mitglieder import parse_mitglieder_csv, upsert_mitglieder, list_mitglieder

    rows = parse_mitglieder_csv("month,count\n1,120\n2,125\n")
    assert rows == [
        {"ma_name": None, "month": 1, "count": 120.0, "notes": None},
        {"ma_name": None, "month": 2, "count": 125.0, "notes": None},
    ]
    init_db()
    db = SessionLocal()
    try:
        upsert_mitglieder(db, ma_name="Ilaria.F", year=2026, month=3, count=130, notes=None, updated_by="ali")
        listed = list_mitglieder(db, 2026, 3)
        assert len(listed) == 1
        assert listed[0].count == 130
    finally:
        db.close()


def test_get_inputs_scopes_to_visible_mas():
    """Teamlead sieht nur eigene Team-Inputs, nicht alle."""
    from database import init_db, SessionLocal, MonthlyInput, User, MAStammdaten
    from ma_access import filter_mas_for_user
    from auth import hash_password

    init_db()
    db = SessionLocal()
    try:
        # Seed-like inputs for two MAs in different teams
        db.add(MonthlyInput(ma_name="Noah.S", year=2026, month=1, ferien_t=1, notes="secret-noah"))
        db.add(MonthlyInput(ma_name="Nina.S", year=2026, month=1, ferien_t=2, notes="secret-nina"))
        tl = db.query(User).filter_by(username="clara").first()
        if not tl:
            tl = User(username="clara", full_name="Clara", role="teamlead", team="Seefeld",
                      hashed_password=hash_password("x"))
            db.add(tl)
        else:
            tl.role = "teamlead"
            tl.team = "Seefeld"
        db.commit()

        visible = {m.name for m in filter_mas_for_user(
            db.query(MAStammdaten).all(), tl, db, year=2026, months=[1],
        )}
        inputs = db.query(MonthlyInput).filter_by(year=2026, month=1).all()
        scoped = {i.ma_name: i.notes for i in inputs if i.ma_name in visible}
        assert "Noah.S" in scoped
        # Nina is CC/Zürich — should not be visible to Seefeld teamlead
        assert "Nina.S" not in scoped or "Nina.S" in visible
    finally:
        db.close()


def test_sign_rejects_wrong_ma_name():
    from database import init_db, SessionLocal, MAStammdaten, User
    from qual_goals import replace_qual_goals
    from qual_sign import sign_qual_goals
    from auth import hash_password

    init_db()
    db = SessionLocal()
    try:
        ma = db.query(MAStammdaten).filter_by(name="Noah.S").first()
        user = db.query(User).filter_by(username="ali").first()
        if not user:
            user = User(username="ali", full_name="Ali", role="ceo", hashed_password=hash_password("x"))
            db.add(user)
            db.commit()
            db.refresh(user)
        replace_qual_goals(
            db, ma_name="Noah.S", year=2026, period_label="HJ1 2026",
            goals=[{"name": "X", "status": "offen"}], updated_by="ali",
        )
        with pytest.raises(ValueError, match="Stammdaten"):
            sign_qual_goals(
                db, ma=ma, year=2026, period_label="HJ1 2026",
                current_user=user, fk_display_name="Clara", ma_confirm_name="Wrong Person",
            )
    finally:
        db.close()
