"""Dokumenten-Ablage: unterzeichnete Quali-PDFs und Uploads pro MA.

Inhalt wird in der DB gespeichert (Postgres Free bleibt persistent ohne Disk).
Optional zusätzlich auf Disk gecacht, falls DATA_DIR beschreibbar ist.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from database import DATA_DIR, MaDocument, QualSignature

DOCUMENTS_ROOT = Path(DATA_DIR) / "documents"


def _safe_ma_dir(ma_name: str) -> Path | None:
    """Versucht lokalen Cache-Ordner; bei Read-only/ephemeral Fehler → None."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", ma_name or "unknown").strip("._") or "unknown"
    path = DOCUMENTS_ROOT / safe
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except OSError:
        return None


def absolute_path(doc: MaDocument) -> Path:
    return DOCUMENTS_ROOT / (doc.relative_path or "")


def read_document_bytes(doc: MaDocument) -> bytes | None:
    if doc.content:
        return bytes(doc.content)
    path = absolute_path(doc)
    try:
        if path.is_file():
            return path.read_bytes()
    except OSError:
        pass
    return None


def document_as_dict(doc: MaDocument) -> dict:
    return {
        "id": doc.id,
        "ma_name": doc.ma_name,
        "title": doc.title,
        "doc_type": doc.doc_type,
        "year": doc.year,
        "period_label": doc.period_label,
        "filename": doc.filename,
        "mime_type": doc.mime_type,
        "size_bytes": doc.size_bytes,
        "notes": doc.notes,
        "storage": "db" if doc.content else "file",
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "created_by": doc.created_by,
    }


def signature_as_dict(sig: QualSignature | None) -> dict | None:
    if not sig:
        return None
    goals = []
    if sig.goals_snapshot:
        try:
            goals = json.loads(sig.goals_snapshot)
        except json.JSONDecodeError:
            goals = []
    return {
        "id": sig.id,
        "ma_name": sig.ma_name,
        "year": sig.year,
        "period_label": sig.period_label,
        "status": sig.status,
        "goals": goals,
        "vereinbarungen": sig.vereinbarungen,
        "fk_display_name": sig.fk_display_name,
        "fk_username": sig.fk_username,
        "fk_confirmed_at": sig.fk_confirmed_at.isoformat() if sig.fk_confirmed_at else None,
        "ma_display_name": sig.ma_display_name,
        "ma_confirmed_at": sig.ma_confirmed_at.isoformat() if sig.ma_confirmed_at else None,
        "document_id": sig.document_id,
        "created_at": sig.created_at.isoformat() if sig.created_at else None,
    }


def get_signature(db: Session, ma_name: str, year: int, period_label: str) -> QualSignature | None:
    return (
        db.query(QualSignature)
        .filter_by(ma_name=ma_name, year=year, period_label=period_label, status="signed")
        .order_by(QualSignature.id.desc())
        .first()
    )


def save_bytes_document(
    db: Session,
    *,
    ma_name: str,
    title: str,
    doc_type: str,
    filename: str,
    content: bytes,
    mime_type: str,
    created_by: str | None,
    year: int | None = None,
    period_label: str | None = None,
    notes: str | None = None,
) -> MaDocument:
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    unique = uuid.uuid4().hex[:8]
    stored_name = f"{stamp}_{unique}_{filename}"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", ma_name or "unknown").strip("._") or "unknown"
    rel = f"{safe}/{stored_name}"

    # Optionaler Disk-Cache (Free ohne Disk: wird übersprungen)
    ma_dir = _safe_ma_dir(ma_name)
    if ma_dir is not None:
        try:
            (ma_dir / stored_name).write_bytes(content)
        except OSError:
            pass

    doc = MaDocument(
        ma_name=ma_name,
        title=title,
        doc_type=doc_type,
        year=year,
        period_label=period_label,
        filename=filename,
        relative_path=rel,
        mime_type=mime_type,
        size_bytes=len(content),
        content=content,
        notes=notes,
        created_at=datetime.utcnow(),
        created_by=created_by,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def list_documents_for_mas(db: Session, ma_names: list[str]) -> list[MaDocument]:
    if not ma_names:
        return []
    return (
        db.query(MaDocument)
        .filter(MaDocument.ma_name.in_(ma_names))
        .order_by(MaDocument.created_at.desc(), MaDocument.id.desc())
        .all()
    )


def delete_document(db: Session, doc: MaDocument) -> None:
    path = absolute_path(doc)
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass
    for sig in db.query(QualSignature).filter_by(document_id=doc.id).all():
        sig.document_id = None
        if sig.status == "signed":
            sig.status = "document_deleted"
    db.delete(doc)
    db.commit()
