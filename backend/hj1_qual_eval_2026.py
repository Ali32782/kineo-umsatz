"""HJ1 2026 — Auswertung qualitative Ziele (Management)."""
from __future__ import annotations

# Spalten: Customer Satisfaction | Operational Excellence | Profitabilität | Leitungsziel 1 | Leitungsziel 2 | Insgesamt
# "x" = kein Ziel für diese Person

HJ1_2026_SCORES: dict[str, dict] = {
    "Hanna.R": {"cs": None, "oe": None, "profit": None, "leit1": 80, "leit2": 100, "total": 90},
    "Emma.L": {"cs": 100, "oe": 98, "profit": 99.5, "leit1": None, "leit2": None, "total": 99},
    "Helen.S": {"cs": 100, "oe": 91, "profit": 99.5, "leit1": None, "leit2": None, "total": 98},
    "Noah.S": {"cs": 100, "oe": 100, "profit": 98, "leit1": None, "leit2": None, "total": 99},
    "Andrina.K": {"cs": 100, "oe": 91, "profit": 99.5, "leit1": None, "leit2": None, "total": 97},
    "Meike.V": {"cs": 100, "oe": 88, "profit": 93.5, "leit1": None, "leit2": None, "total": 94},
    "Eva.D": {"cs": 100, "oe": 100, "profit": 99, "leit1": None, "leit2": None, "total": 100},
    "Carmen.W": {"cs": 100, "oe": 100, "profit": 99, "leit1": None, "leit2": None, "total": 100},
    "Sonia.M": {"cs": 100, "oe": 94, "profit": 98, "leit1": None, "leit2": None, "total": 97},
    "Raphael.H": {"cs": 100, "oe": 100, "profit": 89, "leit1": None, "leit2": None, "total": 94},
    "Clara.B": {"cs": None, "oe": None, "profit": None, "leit1": 80, "leit2": 94, "total": 87},
    "Barbara.V": {"cs": 100, "oe": 91, "profit": 82, "leit1": None, "leit2": None, "total": 91},
}

# Standortleiter-Bonus erreicht: Zollikon (Helen) + Andrina (laut Auswertung)
STANDORTLEITER_BONUS = {
    "Helen.S": "Standort Zollikon — Ziel erreicht: Teamevent Pizza (Budget CHF 40/Person) + Equipment-Budget CHF 500",
    "Andrina.K": "Standort — Ziel erreicht: Teamevent Pizza (Budget CHF 40/Person) + Equipment-Budget CHF 500",
}

GOAL_DEFS = {
    "cs": {
        "name": "Customer Satisfaction — Fachkontent erstellen",
        "detail": "Ziel: Fachkontent erstellen. Bewertung: erreicht / nicht erreicht.",
    },
    "oe": {
        "name": "Operational Excellence — Dokumentation Patientenakten",
        "detail": "Ziel: Dokumentation der Patientenakten.",
    },
    "profit": {
        "name": "Profitabilität — Termine & Alterszentrumsplanung",
        "detail": (
            "Ziel 1: Provisorische Termine nicht buchen — alle Termine richtig verrechnet. "
            "Ziel 2: Ökonomische Alterszentrumsplanung."
        ),
    },
    "leit1": {
        "name": "Leitungsziel 1 — Domizil & Alterszentren",
        "detail": "Optimierung von Domizil- und Alterszentren-Einsatz.",
    },
    "leit2": {
        "name": "Leitungsziel 2 — KPI-Boards",
        "detail": "Vollständige KPI-Boards / Verantwortung.",
    },
}


def _status_for(score: float | None, *, binary: bool = False) -> str:
    if score is None:
        return ""
    if binary:
        return "erreicht" if score >= 100 else "nicht erreicht"
    if score >= 98:
        return "gut"
    if score >= 90:
        return "läuft"
    return "offen"


def _result_str(score: float | None, *, binary: bool = False) -> str:
    if score is None:
        return ""
    if binary:
        return "erreicht" if score >= 100 else "nicht erreicht"
    if score == int(score):
        return f"{int(score)}%"
    return f"{score:g}%"


def goals_for_ma(ma_name: str) -> list[dict]:
    scores = HJ1_2026_SCORES.get(ma_name)
    if not scores:
        return []
    out: list[dict] = []
    order = 0

    for key, binary in (("cs", True), ("oe", False), ("profit", False), ("leit1", False), ("leit2", False)):
        score = scores.get(key)
        if score is None:
            continue
        meta = GOAL_DEFS[key]
        out.append({
            "name": meta["name"],
            "result": _result_str(score, binary=binary),
            "status": _status_for(score, binary=binary),
            "detail": meta["detail"],
            "sort_order": order,
        })
        order += 1

    total = scores.get("total")
    if total is not None:
        detail = f"Auswertung 1. Halbjahr 2026 — Gesamt { _result_str(total) }."
        bonus = STANDORTLEITER_BONUS.get(ma_name)
        if bonus:
            detail = f"{detail} {bonus}"
        out.append({
            "name": "Insgesamt — HJ1 2026",
            "result": _result_str(total),
            "status": _status_for(total),
            "detail": detail,
            "sort_order": order,
        })
    return out


def all_ma_goals() -> dict[str, list[dict]]:
    return {ma: goals_for_ma(ma) for ma in HJ1_2026_SCORES}
