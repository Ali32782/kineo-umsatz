"""Tests für Bilateral-Gesprächsflow."""
from bilat_flow import (
    PHASE_MA_SELF,
    advance_phase,
    compute_deviations,
    fk_hint,
    format_vereinbarungen,
    parse_vereinbarungen,
)


class _Bilat:
    flow_phase = "fk_prep"
    kat_a_self = kat_b_self = kat_c_self = kat_d_self = None
    kat_a_fk = kat_b_fk = kat_c_fk = kat_d_fk = None
    kat_a_comment = kat_b_comment = kat_c_comment = kat_d_comment = None


def test_advance_fk_to_ma_self():
    b = _Bilat()
    b.kat_a_fk = b.kat_b_fk = b.kat_c_fk = b.kat_d_fk = 3
    assert advance_phase(b, "submit_fk") == PHASE_MA_SELF


def test_deviations_grave_when_gap_two():
    b = _Bilat()
    b.kat_a_self, b.kat_a_fk = 5, 2
    b.kat_b_self, b.kat_b_fk = 3, 3
    b.kat_c_self, b.kat_c_fk = 4, 3
    b.kat_d_self, b.kat_d_fk = 3, 4
    b.kat_a_comment = "Auslastung beobachten"
    dev = compute_deviations(b)
    assert dev["has_grave"] is True
    a = next(c for c in dev["categories"] if c["cat"] == "a")
    assert a["grave"] is True
    assert a["talk_prompts"]
    assert a["comment"] == "Auslastung beobachten"


def test_deviations_mild_when_gap_one():
    b = _Bilat()
    for k in "abcd":
        setattr(b, f"kat_{k}_self", 4)
        setattr(b, f"kat_{k}_fk", 3)
    dev = compute_deviations(b)
    assert dev["all_mild"] is True
    assert not dev["has_grave"]


def test_fk_hint_no_raw_numbers():
    hint = fk_hint({"label": "Qualität", "grave": True, "fk_lower": True, "gap": 3})
    assert "5" not in hint and "2" not in hint
    assert "behutsam" in hint


def test_vereinbarungen_roundtrip():
    text = format_vereinbarungen([
        {"what": "Doku verbessern", "who": "Noah", "until": "2026-09-01"},
        {"what": "", "who": "x", "until": "y"},
    ])
    assert "Doku verbessern" in text
    assert "Wer: Noah" in text
    items = parse_vereinbarungen(text)
    assert items[0]["what"] == "Doku verbessern"
    assert items[0]["who"] == "Noah"
    assert items[0]["until"] == "2026-09-01"
