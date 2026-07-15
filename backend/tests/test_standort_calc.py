"""Tests für Standort-Aufteilung inkl. Management und ZEG-B pro Standort."""
from standort_calc import (
    expand_ma_standort_rows,
    aggregate_team_summary,
    revenue_fte_total,
    is_revenue_team,
)


class _Entry:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _sched(seefeld=0, zollikon=0, office=0):
    """Einfaches Wochenmuster: Mo VM/NM an einem Standort."""
    days = []
    if seefeld:
        days.append(_Entry(weekday=0, vm_pct=seefeld, vm_standort="Seefeld", nm_pct=0, nm_standort=""))
    if zollikon:
        days.append(_Entry(weekday=1, vm_pct=zollikon, vm_standort="Zollikon", nm_pct=0, nm_standort=""))
    if office:
        days.append(_Entry(weekday=2, vm_pct=office, vm_standort="Office", nm_pct=0, nm_standort=""))
    return days


def test_expand_splits_umsatz_and_zeg_per_standort():
    ma_row = {"name": "Helen.S", "display_name": "Helen S.", "team": "Seefeld", "umsatz": 10000, "prod_b": 8, "zeg_b": 1.2}
    sched = _sched(seefeld=0.10, zollikon=0.10)
    rows = expand_ma_standort_rows(ma_row, 0.2, "Seefeld", sched)

    clinical = [r for r in rows if not r["is_office"]]
    assert len(clinical) == 2
    assert sum(r["umsatz"] for r in clinical) == 10000
    for r in clinical:
        assert abs(r["zeg_b"] - ma_row["zeg_b"]) < 0.01


def test_office_row_renamed_to_management():
    ma_row = {"name": "Test.MA", "display_name": "Test", "team": "Seefeld", "umsatz": 5000, "prod_b": 5}
    sched = [
        _Entry(weekday=0, vm_pct=0.10, vm_standort="Seefeld", nm_pct=0.10, nm_standort="Seefeld"),
        _Entry(weekday=1, vm_pct=0.10, vm_standort="Office", nm_pct=0, nm_standort=""),
    ]
    rows = expand_ma_standort_rows(ma_row, 0.3, "Seefeld", sched)
    office = next(r for r in rows if r["is_office"])
    assert office["team"] == "Management"
    assert office["umsatz"] == 0
    assert office["zeg_b"] is None
    assert office["bg_pct"] > 0
    assert office["counts_for_fte"] is False


def test_aggregate_revenue_only_excludes_management_and_cc():
    rows = [
        {"team": "Seefeld", "umsatz": 6000, "bg_pct": 0.6, "zeg_b": 1.0, "prod_b_standort": 5, "is_office": False, "counts_for_fte": True, "primary_team": "Seefeld"},
        {"team": "Zollikon", "umsatz": 4000, "bg_pct": 0.4, "zeg_b": 0.8, "prod_b_standort": 4, "is_office": False, "counts_for_fte": True, "primary_team": "Zollikon"},
        {"team": "Management", "umsatz": 0, "bg_pct": 0.1, "zeg_b": None, "prod_b_standort": 0, "is_office": True, "counts_for_fte": False, "primary_team": "Seefeld"},
        {"team": "CC", "umsatz": 0, "bg_pct": 1.0, "zeg_b": None, "prod_b_standort": 0, "is_office": False, "counts_for_fte": False, "primary_team": "CC"},
    ]
    summary = aggregate_team_summary(rows, revenue_only=True)
    assert "Seefeld" in summary
    assert "Management" not in summary
    assert "CC" not in summary
    assert revenue_fte_total(rows) == 1.0
    assert not is_revenue_team("CC")
    assert not is_revenue_team("Management")
    assert is_revenue_team("Seefeld")
