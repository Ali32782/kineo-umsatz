"""Quali-Sperre nach Signatur, atomare Re-Signatur, Upload-Whitelist."""
import os
import tempfile

import pytest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="kineo-lock-")

from database import SessionLocal, init_db, MAStammdaten, User, QualSignature, MaDocument
from auth import hash_password
from documents_store import get_signature, validate_upload_file
from qual_goals import replace_qual_goals, list_qual_goals
from qual_sign import sign_qual_goals, supersede_signatures


def _user(db):
    user = db.query(User).filter_by(username="ali").first()
    if not user:
        user = User(
            username="ali", full_name="Ali Peters", role="ceo",
            hashed_password=hash_password("x"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def test_validate_upload_allows_pdf_rejects_exe():
    assert validate_upload_file("bericht.pdf", "application/pdf") == "bericht.pdf"
    with pytest.raises(ValueError):
        validate_upload_file("malware.exe", "application/octet-stream")
    with pytest.raises(ValueError):
        validate_upload_file("ok.pdf", "application/x-msdownload")


def test_sign_then_supersede_clears_active_signature():
    init_db()
    db = SessionLocal()
    try:
        ma = db.query(MAStammdaten).filter_by(name="Noah.S").first()
        user = _user(db)
        replace_qual_goals(
            db, ma_name="Noah.S", year=2026, period_label="HJ1 2026",
            goals=[{"name": "MC", "result": "90%", "status": "gut"}],
            updated_by="ali",
        )
        sign_qual_goals(
            db, ma=ma, year=2026, period_label="HJ1 2026",
            current_user=user, fk_display_name="Clara", ma_confirm_name="Noah",
        )
        assert get_signature(db, "Noah.S", 2026, "HJ1 2026") is not None

        n = supersede_signatures(db, "Noah.S", 2026, "HJ1 2026")
        assert n >= 1
        replace_qual_goals(
            db, ma_name="Noah.S", year=2026, period_label="HJ1 2026",
            goals=[{"name": "MC", "result": "92%", "status": "sehr gut"}],
            updated_by="ali",
        )
        assert get_signature(db, "Noah.S", 2026, "HJ1 2026") is None
        goals = list_qual_goals(db, "Noah.S", 2026, "HJ1 2026")
        assert goals[0].result == "92%"
        old = db.query(QualSignature).filter_by(ma_name="Noah.S", status="superseded").count()
        assert old >= 1
    finally:
        db.close()


def test_resign_is_atomic_one_active_signature_and_new_pdf():
    init_db()
    db = SessionLocal()
    try:
        ma = db.query(MAStammdaten).filter_by(name="Noah.S").first()
        user = _user(db)
        replace_qual_goals(
            db, ma_name="Noah.S", year=2026, period_label="HJ2 2026",
            goals=[{"name": "Dok", "status": "offen"}],
            updated_by="ali",
        )
        r1 = sign_qual_goals(
            db, ma=ma, year=2026, period_label="HJ2 2026",
            current_user=user, fk_display_name="Clara", ma_confirm_name="Noah",
        )
        doc1 = r1["document"]["id"]
        r2 = sign_qual_goals(
            db, ma=ma, year=2026, period_label="HJ2 2026",
            current_user=user, fk_display_name="Clara B.", ma_confirm_name="Noah S.",
        )
        signed = (
            db.query(QualSignature)
            .filter_by(ma_name="Noah.S", year=2026, period_label="HJ2 2026", status="signed")
            .all()
        )
        assert len(signed) == 1
        assert signed[0].document_id == r2["document"]["id"]
        assert signed[0].document_id != doc1
        assert get_signature(db, "Noah.S", 2026, "HJ2 2026").fk_display_name == "Clara B."
        assert db.query(MaDocument).filter_by(id=r2["document"]["id"]).first().content
    finally:
        db.close()
