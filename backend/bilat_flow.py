"""Bilateral-Gesprächsflow: FK-Vorbereitung → MA-Selbsteinschätzung → Abgleich."""
from __future__ import annotations

from database import BilatData

# A–D sind Pflicht für Phasenwechsel; E/F optional (Vorlage)
REQUIRED_KAT_KEYS = ("a", "b", "c", "d")
OPTIONAL_KAT_KEYS = ("e", "f")
KAT_KEYS = REQUIRED_KAT_KEYS + OPTIONAL_KAT_KEYS
KAT_LABELS = {
    "a": "Profitabilität & Auslastung",
    "b": "Qualität & Operational Excellence",
    "c": "Satisfaction Intern – Team & Kultur",
    "d": "Satisfaction Extern – Patienten & Zuweiser",
    "e": "Entwicklung & Potenzial",
    "f": "Zusammenarbeit & Kommunikation",
}
RATING_LABELS = {
    1: "Entwicklungsbedarf",
    2: "Unter Erwartung",
    3: "Erwartung erfüllt",
    4: "Gut",
    5: "Ausgezeichnet",
}

# Kurze Gesprächsfragen für die Abgleich-Agenda
TALK_PROMPTS = {
    "a": [
        "Was hat die Auslastung / den Umsatz im Halbjahr am stärksten beeinflusst?",
        "Welche 1–2 Massnahmen würden die nächste Periode spürbar verbessern?",
    ],
    "b": [
        "Wo steht die Qualität der Arbeit heute — und was soll sich verbessern?",
        "Welche Quali-Ziele sind kritisch, welche auf Kurs?",
    ],
    "c": [
        "Wie läuft die Zusammenarbeit im Team / mit der Führung?",
        "Was braucht die Person, um sich im Team stark zu fühlen?",
    ],
    "d": [
        "Wie erleben Patienten und Zuweiser die Person?",
        "Gibt es Feedback oder Situationen, die wir gemeinsam anschauen sollten?",
    ],
    "e": [
        "Welche Stärken wollen wir gezielt weiterentwickeln?",
        "Was ist das nächste konkrete Entwicklungsschritt?",
    ],
    "f": [
        "Wie funktioniert die Abstimmung im Alltag?",
        "Wo braucht es klarere Erwartungen oder Feedback?",
    ],
}

# Abweichung ≥ 2 Stufen = sensibel (kein harter Zahlenvergleich im Gespräch)
GRAVE_GAP = 2

PHASE_FK_PREP = "fk_prep"
PHASE_MA_SELF = "ma_self"
PHASE_REVEAL = "reveal"
PHASE_DONE = "done"


def _fk_complete(b: BilatData) -> bool:
    return all(getattr(b, f"kat_{k}_fk") is not None for k in REQUIRED_KAT_KEYS)


def _self_complete(b: BilatData) -> bool:
    return all(getattr(b, f"kat_{k}_self") is not None for k in REQUIRED_KAT_KEYS)


def compute_deviations(b: BilatData | None) -> dict:
    if not b:
        return {"categories": [], "has_grave": False, "all_mild": False, "ready": False}
    categories = []
    for k in KAT_KEYS:
        self_v = getattr(b, f"kat_{k}_self", None)
        fk_v = getattr(b, f"kat_{k}_fk", None)
        if self_v is None or fk_v is None:
            continue
        gap = abs(fk_v - self_v)
        fk_lower = fk_v < self_v
        categories.append({
            "cat": k,
            "label": KAT_LABELS.get(k, f"Kategorie {k.upper()}"),
            "self": self_v,
            "fk": fk_v,
            "gap": gap,
            "fk_lower": fk_lower,
            "grave": gap >= GRAVE_GAP,
            "self_label": RATING_LABELS.get(self_v, str(self_v)),
            "fk_label": RATING_LABELS.get(fk_v, str(fk_v)),
            "comment": getattr(b, f"kat_{k}_comment", None) or "",
            "talk_prompts": list(TALK_PROMPTS.get(k, [])),
            "hint": fk_hint({
                "label": KAT_LABELS.get(k, f"Kategorie {k.upper()}"),
                "grave": gap >= GRAVE_GAP,
                "fk_lower": fk_lower,
                "gap": gap,
            }),
        })
    has_grave = any(c["grave"] for c in categories)
    required_ready = all(
        getattr(b, f"kat_{k}_self") is not None and getattr(b, f"kat_{k}_fk") is not None
        for k in REQUIRED_KAT_KEYS
    )
    return {
        "categories": categories,
        "has_grave": has_grave,
        "all_mild": bool(categories) and not has_grave,
        "ready": required_ready,
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


def format_vereinbarungen(items: list[dict] | None) -> str:
    """Strukturierte Vereinbarungen → lesbarer Text für DB/Word."""
    if not items:
        return ""
    lines = []
    for i, it in enumerate(items, 1):
        what = (it.get("what") or "").strip()
        if not what:
            continue
        who = (it.get("who") or "").strip() or "—"
        until = (it.get("until") or "").strip() or "—"
        lines.append(f"{i}. {what}  |  Wer: {who}  |  Bis: {until}")
    return "\n".join(lines)


def parse_vereinbarungen(text: str | None) -> list[dict]:
    """Versucht strukturierte Zeilen zu parsen; sonst eine freie Zeile."""
    raw = (text or "").strip()
    if not raw:
        return [{"what": "", "who": "", "until": ""}]
    items = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # "1. Foo  |  Wer: Bar  |  Bis: 2026-09-01"
        if "|" in line and "Wer:" in line:
            parts = [p.strip() for p in line.split("|")]
            what = parts[0]
            what = what.lstrip("0123456789.").strip()
            who = ""
            until = ""
            for p in parts[1:]:
                if p.lower().startswith("wer:"):
                    who = p.split(":", 1)[1].strip()
                elif p.lower().startswith("bis:"):
                    until = p.split(":", 1)[1].strip()
            items.append({"what": what, "who": who, "until": until})
        else:
            items.append({"what": line.lstrip("0123456789.").strip(), "who": "", "until": ""})
    while len(items) < 1:
        items.append({"what": "", "who": "", "until": ""})
    return items[:20]


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
    """
    action vorwärts: submit_fk | submit_self | complete_reveal
    action zurück:   reopen_reveal | reopen_self | reopen_prep | rewind
    """
    current = (getattr(b, "flow_phase", None) or PHASE_FK_PREP)

    # ── Zurück ──────────────────────────────────────────────────────────
    if action == "rewind":
        order = [PHASE_FK_PREP, PHASE_MA_SELF, PHASE_REVEAL, PHASE_DONE]
        try:
            idx = order.index(current)
        except ValueError:
            idx = 0
        if idx <= 0:
            raise ValueError("Bereits in der ersten Phase — nichts zum Zurückgehen.")
        b.flow_phase = order[idx - 1]
        return b.flow_phase
    if action == "reopen_reveal":
        if current != PHASE_DONE:
            raise ValueError("Wiederöffnen nur aus der Abschluss-Phase möglich.")
        b.flow_phase = PHASE_REVEAL
        return b.flow_phase
    if action == "reopen_self":
        if current not in (PHASE_REVEAL, PHASE_DONE):
            raise ValueError("Zurück zur Selbsteinschätzung nur ab Abgleich/Abschluss.")
        b.flow_phase = PHASE_MA_SELF
        return b.flow_phase
    if action == "reopen_prep":
        if current == PHASE_FK_PREP:
            raise ValueError("Bereits in der FK-Vorbereitung.")
        b.flow_phase = PHASE_FK_PREP
        return b.flow_phase

    # ── Vorwärts ────────────────────────────────────────────────────────
    if action == "submit_fk":
        if current not in (PHASE_FK_PREP,):
            raise ValueError("FK-Freigabe nur in der Vorbereitungsphase möglich.")
        if not _fk_complete(b):
            raise ValueError("Bitte alle vier FK-Bewertungen (A–D) erfassen.")
        b.flow_phase = PHASE_MA_SELF
        return b.flow_phase
    if action == "submit_self":
        if current not in (PHASE_MA_SELF,):
            raise ValueError("Selbsteinschätzung nur in Phase 2 möglich.")
        if not _self_complete(b):
            raise ValueError("Bitte alle vier Selbsteinschätzungen (A–D) erfassen.")
        b.flow_phase = PHASE_REVEAL
        return b.flow_phase
    if action == "complete_reveal":
        if current not in (PHASE_REVEAL,):
            raise ValueError("Abschluss nur in der Abgleich-Phase möglich.")
        b.flow_phase = PHASE_DONE
        return b.flow_phase
    raise ValueError(f"Unbekannte Aktion: {action}")
