"""Beschäftigungsgrad (BG%) als Anteil 0–1."""


def normalize_bg_pct(value) -> float:
    """Beschäftigungsgrad als Anteil 0–1. Eingaben wie 90 → 0.9."""
    try:
        x = float(value)
    except (TypeError, ValueError):
        return 1.0
    if x > 1.5:
        x = x / 100.0
    if x <= 0:
        x = 0.1
    if x > 1.0:
        x = 1.0
    return round(x, 4)
