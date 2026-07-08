"""Bilateral-Gesprächsflow: FK-Vorbereitung → MA-Selbsteinschätzung → Abgleich."""
from __future__ import annotations

from database import BilatData

KAT_KEYS = ("a", "b", "c", "d")
KAT_LABELS = {
    "a": "Profitabilität & Auslastung",
    "b": "Qualität & Operational Excellence",
    "c": "Satisfaction Intern",
    "d": "Satisfaction Extern",
}
RATING_LABELS = {
    1: "Entwicklungsbedarf",
    2: "Unter Erwartung",
    3: "Erwartung erfüllt",
    4: "Gut",
    5: "Ausgezeichnet",
}

# Abweichung ≥ 2 Stufen = sensibel (kein harter Zahlenvergleich im Gespräch)
GRAVE_GAP = 2

PHASE_FK_PREP = "fk_prep"
PHASE_MA_SELF = "ma_self"
PHASE_REVEAL = "reveal"
PHASE_DONE = "done"


def _fk_complete(b: BilatData) -> bool:
    return all(getattr(b, f"kat_{k}_fk") is not None for k in KAT_KEYS)


def _self_complete(b: BilatData) -> bool:
    return all(getattr(b, f"kat_{k}_self") is not None for k in KAT_KEYS)


def compute_deviations(b: BilatData | None) -> dict:
    if not b:
        return {"categories": [], "has_grave": False, "all_mild": False, "ready": False}
    categories = []
    for k in KAT_KEYS:
        self_v = getattr(b, f"kat_{k}_self")
        fk_v = getattr(b, f"kat_{k}_fk")
        if self_v is None or fk_v is None:
            continue
        gap = abs(fk_v - self_v)
        fk_lower = fk_v < self_v
        categories.append({
            "cat": k,
            "label": KAT_LABELS[k],
            "self": self_v,
            "fk": fk_v,
            "gap": gap,
            "fk_lower": fk_lower,
            "grave": gap >= GRAVE_GAP,
            "self_label": RATING_LABELS.get(self_v, str(self_v)),
            "fk_label": RATING_LABELS.get(fk_v, str(fk_v)),
        })
    has_grave = any(c["grave"] for c in categories)
    return {
        "categories": categories,
        "has_grave": has_grave,
        "all_mild": bool(categories) and not has_grave,
        "ready": len(categories) == len(KAT_KEYS),
    }


def fk_hint(cat: dict) -> str:
    label = cat["label"]
    if cat["grave"] and cat["fk_lower"]:
        return (
            f"{label}: Deutlich strengere FK-Sicht — im Gespräch behutsam ansprechen, "
            "keine Skalen-Zahlen vorlesen."
        )
    if cat["grave"] and not cat["fk_lower"]:
        return (
            f"{label}: MA sieht sich deutlich kritischer als die FK — Raum für Gespräch schaffen."
        )
    if cat["gap"] == 0:
        return f"{label}: Übereinstimmende Einschätzung."
    return f"{label}: Leichte Abweichung — gemeinsam kurz besprechen."


def mild_summary(cat: dict) -> str:
    if cat["gap"] == 0:
        return f"Kat. {cat['cat'].upper()} — {cat['label']}: Beide ähnlich ({cat['self_label']})."
    return (
        f"Kat. {cat['cat'].upper()} — {cat['label']}: "
        f"MA {cat['self_label']}, FK {cat['fk_label']} (kleine Differenz)."
    )


def infer_phase(b: BilatData | None) -> str:
    if b is None:
        return PHASE_FK_PREP
    phase = getattr(b, "flow_phase", None) or PHASE_FK_PREP
    if phase == PHASE_DONE:
        return PHASE_DONE
    if not _fk_complete(b):
        return PHASE_FK_PREP
    if not _self_complete(b):
        return PHASE_MA_SELF if phase != PHASE_FK_PREP else PHASE_MA_SELF
    if phase in (PHASE_REVEAL, PHASE_DONE):
        return phase
    return PHASE_REVEAL


def advance_phase(b: BilatData, action: str) -> str:
    """action: submit_fk | submit_self | complete_reveal"""
    if action == "submit_fk":
        if not _fk_complete(b):
            raise ValueError("Bitte alle vier FK-Bewertungen (A–D) erfassen.")
        b.flow_phase = PHASE_MA_SELF
        return b.flow_phase
    if action == "submit_self":
        if not _self_complete(b):
            raise ValueError("Bitte alle vier Selbsteinschätzungen (A–D) erfassen.")
        b.flow_phase = PHASE_REVEAL
        return b.flow_phase
    if action == "complete_reveal":
        b.flow_phase = PHASE_DONE
        return b.flow_phase
    raise ValueError(f"Unbekannte Aktion: {action}")
