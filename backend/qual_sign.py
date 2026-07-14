"""Quali-Ziele unterzeichnen → PDF in MA-Ablage."""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from database import BilatData, MAStammdaten, QualSignature, User
from documents_store import get_signature, save_bytes_document, signature_as_dict
from qual_goals import goals_as_dicts, list_qual_goals
from simple_pdf import build_text_pdf
from auth import names_match_confirm


def supersede_signatures(db: Session, ma_name: str, year: int, period_label: str) -> int:
    """Markiert bestehende Signaturen als überholt (nach Edit / Re-Sign)."""
    rows = (
        db.query(QualSignature)
        .filter_by(ma_name=ma_name, year=year, period_label=period_label, status="signed")
        .all()
    )
    for sig in rows:
        sig.status = "superseded"
    return len(rows)


def sign_qual_goals(
    db: Session,
    *,
    ma: MAStammdaten,
    year: int,
    period_label: str,
    current_user: User,
    fk_display_name: str,
    ma_confirm_name: str,
    vereinbarungen: str | None = None,
    notes: str | None = None,
) -> dict:
    goals = goals_as_dicts(list_qual_goals(db, ma.name, year, period_label))
    if not goals:
        raise ValueError("Keine Quali-Ziele gespeichert — bitte zuerst unter Quali-Themen speichern.")

    fk_name = (fk_display_name or "").strip()
    ma_name_confirm = (ma_confirm_name or "").strip()
    if len(fk_name) < 2:
        raise ValueError("Bitte Namen der Führungskraft zur Bestätigung eintragen.")
    if len(ma_name_confirm) < 2:
        raise ValueError("Bitte Namen der Mitarbeiterin / des Mitarbeiters zur Bestätigung eintragen.")

    expected = ma.display_name or ma.name
    if not names_match_confirm(expected, ma_name_confirm):
        raise ValueError(
            f"MA-Name stimmt nicht mit Stammdaten überein (erwartet: {expected})."
        )

    if vereinbarungen is None:
        bilat = (
            db.query(BilatData)
            .filter_by(ma_name=ma.name, year=year, period_label=period_label)
            .first()
        )
        vereinbarungen = (bilat.vereinbarungen if bilat else None) or ""

    now = datetime.utcnow()
    sections = [
        (
            "Qualitative Ziele",
            [
                f"{i + 1}. {g['name']}"
                + (f"  |  Ergebnis: {g['result']}" if g.get("result") else "")
                + (f"  |  Status: {g['status']}" if g.get("status") else "")
                + (f"  |  {g['detail']}" if g.get("detail") else "")
                for i, g in enumerate(goals)
            ],
        ),
    ]
    if vereinbarungen.strip():
        sections.append(("Vereinbarungen / naechste Schritte", [vereinbarungen.strip()]))
    if notes and notes.strip():
        sections.append(("Bemerkung zur Unterzeichnung", [notes.strip()]))

    sections.append((
        "Unterzeichnungen",
        [
            f"Fuehrungskraft: {fk_name}  — bestaetigt am {now.strftime('%d.%m.%Y %H:%M')} UTC",
            f"Mitarbeiter/in: {ma_name_confirm}  — bestaetigt am {now.strftime('%d.%m.%Y %H:%M')} UTC",
            f"Erfasst durch App-User: {current_user.full_name or current_user.username}",
        ],
    ))

    pdf_bytes = build_text_pdf(
        title="Quali-Ziele — unterzeichnet",
        subtitle=f"{ma.display_name or ma.name}  |  {ma.team or '—'}  |  {period_label}",
        sections=sections,
        footer="FK-intern — bestaetigte Quali-Vereinbarung (digital mit Zeitstempel).",
    )

    # Alte Signaturen ungültig + PDF + neue Signatur in einer Transaktion
    supersede_signatures(db, ma.name, year, period_label)

    filename = f"Quali_{ma.name}_{period_label.replace(' ', '_')}_signed.pdf"
    doc = save_bytes_document(
        db,
        ma_name=ma.name,
        title=f"Quali unterzeichnet — {period_label}",
        doc_type="qual_signed",
        filename=filename,
        content=pdf_bytes,
        mime_type="application/pdf",
        created_by=current_user.username,
        year=year,
        period_label=period_label,
        notes=notes,
        commit=False,
    )

    sig = QualSignature(
        ma_name=ma.name,
        year=year,
        period_label=period_label,
        status="signed",
        goals_snapshot=json.dumps(goals, ensure_ascii=False),
        vereinbarungen=vereinbarungen.strip() or None,
        fk_display_name=fk_name,
        fk_username=current_user.username,
        fk_confirmed_at=now,
        ma_display_name=ma_name_confirm,
        ma_confirmed_at=now,
        document_id=doc.id,
        created_at=now,
        created_by=current_user.username,
    )
    db.add(sig)
    db.commit()
    db.refresh(sig)
    db.refresh(doc)

    return {
        "message": "Quali-Ziele unterzeichnet und PDF abgelegt",
        "signature": signature_as_dict(sig),
        "document": {
            "id": doc.id,
            "filename": doc.filename,
            "title": doc.title,
            "ma_name": doc.ma_name,
        },
    }


def latest_signature_dict(db: Session, ma_name: str, year: int, period_label: str) -> dict | None:
    return signature_as_dict(get_signature(db, ma_name, year, period_label))
