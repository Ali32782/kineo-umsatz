"""Zuordnung MA-Name → individuelle Bilateral-Wordvorlage (HJ1)."""
from __future__ import annotations

import os
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates" / "bilat_ma"

# Explizite Zuordnung (DB-Name → Dateiname). Clara.B: reguläre Vorlage (nicht Covered).
MA_BILAT_TEMPLATE: dict[str, str] = {
    "Ali.P": "Bilat_Ali_P_HJ1_2026.docx",
    "Andrina.K": "Bilat_Andrina_K_HJ1_2026.docx",
    "Barbara.V": "Bilat_Barbara_V_HJ1_2026.docx",
    "Carmen.W": "Bilat_Carmen_W_HJ1_2026.docx",
    "Clara.B": "Bilat_Clara_B_HJ1_2026.docx",
    "Emma.L": "Bilat_Emma_L_HJ1_2026.docx",
    "Eva.D": "Bilat_Eva_D_HJ1_2026.docx",
    "Eve.S": "Bilat_Eve_S_HJ1_2026.docx",
    "Hanna.R": "Bilat_Hanna_R_HJ1_2026.docx",
    "Helen.S": "Bilat_Helen_S_HJ1_2026.docx",
    "Joëlle.R": "Bilat_Joëlle_R_HJ1_2026.docx",
    "Lucrecia.G": "Bilat_Lucrecia_G_HJ1_2026.docx",
    "Martino.C": "Bilat_Martino_C_HJ1_2026.docx",
    "Meike.V": "Bilat_Meike_V_HJ1_2026.docx",
    "Noah.S": "Bilat_Noah_S_HJ1_2026.docx",
    "Pablo.G": "Bilat_Pablo_G_HJ1_2026.docx",
    "Pablo.M": "Bilat_Pablo_M_HJ1_2026.docx",
    "Raphael.H": "Bilat_Raphael_H_HJ1_2026.docx",
    "Sereina.U": "Bilat_Sereina_U_HJ1_2026.docx",
    "Sonia.M": "Bilat_Sonia_M_HJ1_2026.docx",
    "Valerio.S": "Bilat_Valerio_L_HJ1_2026.docx",
}

DEFAULT_TEMPLATE = "Bilat_Barbara_V_HJ1_2026.docx"


def _own_template_path(ma_name: str) -> Path | None:
    """Eigene MA-Vorlage (ohne Default-Fallback auf eine andere Person)."""
    filename = MA_BILAT_TEMPLATE.get(ma_name)
    if filename:
        path = TEMPLATES_DIR / filename
        if path.is_file():
            return path
    safe = ma_name.replace(".", "_").replace(" ", "_")
    for pattern in (f"Bilat_{safe}_HJ1_*.docx", f"Bilat_{safe}*_HJ1_*.docx"):
        matches = sorted(TEMPLATES_DIR.glob(pattern))
        if matches:
            return matches[0]
    return None


def has_own_bilat_template(ma_name: str) -> bool:
    """True nur bei individueller Vorlage — CC o. Ä. ohne Fake-Fremdinhalte."""
    return _own_template_path(ma_name) is not None


def resolve_bilat_template(ma_name: str) -> Path:
    own = _own_template_path(ma_name)
    if own is not None:
        return own
    fallback = TEMPLATES_DIR / DEFAULT_TEMPLATE
    if fallback.is_file():
        return fallback
    raise FileNotFoundError(f"Keine Bilat-Vorlage für {ma_name} in {TEMPLATES_DIR}")
