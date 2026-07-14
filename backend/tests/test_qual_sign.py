"""Quali unterzeichnen + PDF-Ablage."""
import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="kineo-docs-")

from database import SessionLocal, init_db, MAStammdaten, User, MaDocument
from auth import hash_password
from qual_goals import replace_qual_goals
from qual_sign import sign_qual_goals
from documents_store import list_documents_for_mas
from simple_pdf import build_text_pdf


def test_simple_pdf_bytes():
    b = build_text_pdf(title="T", subtitle="S", sections=[("A", ["line"])])
    assert b.startswith(b"%PDF")
    assert b"%EOF" in b


def test_sign_qual_creates_pdf_in_ablage():
    init_db()
    db = SessionLocal()
    try:
        ma = db.query(MAStammdaten).filter_by(name="Noah.S").first()
        assert ma
        user = db.query(User).filter_by(username="ali").first()
        if not user:
            user = User(
                username="ali", full_name="Ali Peters", role="ceo",
                hashed_password=hash_password("x"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        replace_qual_goals(
            db,
            ma_name="Noah.S",
            year=2026,
            period_label="HJ1 2026",
            goals=[{"name": "Movement Control", "result": "90%", "status": "gut", "detail": "ok"}],
            updated_by="ali",
        )
        result = sign_qual_goals(
            db,
            ma=ma,
            year=2026,
            period_label="HJ1 2026",
            current_user=user,
            fk_display_name="Clara Benning",
            ma_confirm_name="Noah Sutter",
            vereinbarungen="Naechster Check in 3 Monaten",
            notes=None,
        )
        assert result["signature"]["status"] == "signed"
        doc_id = result["document"]["id"]
        doc = db.query(MaDocument).filter_by(id=doc_id).first()
        assert doc is not None
        assert doc.doc_type == "qual_signed"
        assert doc.ma_name == "Noah.S"
        assert doc.content and bytes(doc.content).startswith(b"%PDF")
        from documents_store import read_document_bytes
        assert read_document_bytes(doc).startswith(b"%PDF")
        listed = list_documents_for_mas(db, ["Noah.S"])
        assert any(d.id == doc_id for d in listed)
    finally:
        db.close()
