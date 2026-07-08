"""Tests für Bilateral-Gesprächsflow."""
from bilat_flow import (
    PHASE_MA_SELF,
    PHASE_REVEAL,
    advance_phase,
    compute_deviations,
    fk_hint,
)


class _Bilat:
    flow_phase = "fk_prep"
    kat_a_self = kat_b_self = kat_c_self = kat_d_self = None
    kat_a_fk = kat_b_fk = kat_c_fk = kat_d_fk = None


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
    dev = compute_deviations(b)
    assert dev["has_grave"] is True
    assert any(c["cat"] == "a" and c["grave"] for c in dev["categories"])


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
