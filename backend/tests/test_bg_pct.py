"""Tests für BG%-Normalisierung (90 → 0.9)."""
from bg_pct import normalize_bg_pct


def test_normalize_fraction_unchanged():
    assert normalize_bg_pct(0.9) == 0.9
    assert normalize_bg_pct(1.0) == 1.0


def test_normalize_percent_input():
    assert normalize_bg_pct(90) == 0.9
    assert normalize_bg_pct(80) == 0.8
    assert normalize_bg_pct(100) == 1.0


def test_normalize_clamps():
    assert normalize_bg_pct(0) == 0.1
    assert normalize_bg_pct(150) == 1.0
    assert normalize_bg_pct(1.2) == 1.0
