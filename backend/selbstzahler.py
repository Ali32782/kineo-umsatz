"""Selbstzahler-Umsätze: Shop, Fitness, HYROX, Performance Lab."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from database import SelbstzahlerUmsatz, MitgliederData

# Fitness: Umsatz = Mitglieder × CHF 1'200
FITNESS_CHF_PER_MEMBER = 1200.0

# unit key → Meta (Dashboard / Eingabe)
# source: excel | derived | open
SELBSTZAHLER_UNITS: dict[str, dict] = {
    "shop": {
        "label": "Shop / Retail",
        "owner": "Marc.W",
        "owner_label": "Marc Walser",
        "source": "excel",  # Runnerslab-Excel
        "has_mitglieder": False,
    },
    "fitness": {
        "label": "Fitness",
        "owner": "Ilaria.F",
        "owner_label": "Ilaria Ferrante",
        "source": "derived",  # Mitglieder × 1200
        "has_mitglieder": True,
    },
    "hyrox": {
        "label": "HYROX",
        "owner": "Nina.S",
        "owner_label": "Nina Schulte",
        "source": "excel",  # Training-Club Rechnungen (Stunde Hyrox)
        "has_mitglieder": False,
    },
    "performance_lab": {
        "label": "Performance Lab",
        "owner": "Nina.S",
        "owner_label": "Nina Schulte",
        "source": "open",
        "has_mitglieder": False,
    },
}

UNIT_ORDER = ("shop", "fitness", "hyrox", "performance_lab")


def upsert_selbstzahler_umsatz(
    db: Session,
    *,
    unit: str,
    year: int,
    month: int,
    umsatz: float,
    updated_by: str | None,
    notes: str | None = None,
) -> SelbstzahlerUmsatz:
    if unit not in SELBSTZAHLER_UNITS:
        raise ValueError(f"Unbekannte Einheit: {unit}")
    row = (
        db.query(SelbstzahlerUmsatz)
        .filter_by(unit=unit, year=year, month=month)
        .first()
    )
    if row:
        row.umsatz = float(umsatz)
        if notes is not None:
            row.notes = notes
        row.updated_at = datetime.utcnow()
        row.updated_by = updated_by
    else:
        row = SelbstzahlerUmsatz(
            unit=unit,
            year=year,
            month=month,
            umsatz=float(umsatz),
            notes=notes,
            updated_at=datetime.utcnow(),
            updated_by=updated_by,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def dashboard_units(db: Session, year: int, month: int) -> list[dict]:
    """Monats-Snapshot für Dashboard-Karten."""
    out = []
    for key in UNIT_ORDER:
        meta = SELBSTZAHLER_UNITS[key]
        entry = {
            "unit": key,
            "label": meta["label"],
            "owner": meta["owner"],
            "owner_label": meta["owner_label"],
            "source": meta["source"],
            "status": "offen" if meta["source"] == "open" else "aktiv",
            "umsatz": None,
            "mitglieder": None,
            "notes": None,
            "formula": None,
        }
        if key == "fitness":
            m = (
                db.query(MitgliederData)
                .filter_by(ma_name=meta["owner"], year=year, month=month)
                .first()
            )
            if m and m.count is not None:
                entry["mitglieder"] = m.count
                entry["umsatz"] = round(float(m.count) * FITNESS_CHF_PER_MEMBER)
                entry["formula"] = f"{m.count:g} × CHF {int(FITNESS_CHF_PER_MEMBER):,}".replace(",", "'")
                entry["notes"] = m.notes
                entry["status"] = "aktiv"
            else:
                entry["status"] = "offen"
                entry["formula"] = f"Mitglieder × CHF {int(FITNESS_CHF_PER_MEMBER):,}".replace(",", "'")
        elif meta["source"] == "excel":
            row = (
                db.query(SelbstzahlerUmsatz)
                .filter_by(unit=key, year=year, month=month)
                .first()
            )
            if row:
                entry["umsatz"] = round(float(row.umsatz or 0))
                entry["notes"] = row.notes
                entry["status"] = "aktiv"
            else:
                entry["status"] = "offen"
        else:
            # hyrox / performance_lab — noch keine Quelle
            entry["status"] = "offen"
        out.append(entry)
    return out
