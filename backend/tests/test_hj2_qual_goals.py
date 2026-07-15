"""Tests für HJ2-2026 Quali-Ziele."""
from hj2_qual_goals_2026 import (
    all_ma_goals,
    goals_for_ma,
    PHYSIO_THERAPEUTEN,
    TEAMLEADS,
    STANDORTLEADS,
    HOOR_OWNERS,
)


def test_emma_physio_three_goals():
    goals = goals_for_ma("Emma.L")
    assert len(goals) == 3
    names = " ".join(g["name"] for g in goals)
    assert "Operational Excellence" in names
    assert "Profitabilität" in names
    assert "Satisfaction" in names
    assert "15" in goals[0]["detail"]


def test_hanna_teamlead_includes_bilat_and_physio():
    goals = goals_for_ma("Hanna.R")
    names = [g["name"] for g in goals]
    assert any("Bilat-Struktur" in n for n in names)
    assert any("Team-Umsatzziel" in n for n in names)
    assert any("Patientenberichte" in n for n in names)
    oe = next(g for g in goals if "Patientenberichte" in g["name"])
    assert "10" in oe["detail"]


def test_standortlead_has_sop_and_bd():
    goals = goals_for_ma("Helen.S")
    names = [g["name"] for g in goals]
    assert any("SOPs Standort" in n for n in names)
    assert any("Business Development" in n for n in names)


def test_pamela_lead_cc():
    goals = goals_for_ma("Pamela.P")
    assert len(goals) == 3
    assert any("Onboarding" in g["name"] for g in goals)


def test_martino_three_lead_goals():
    goals = goals_for_ma("Martino.C")
    assert len(goals) == 3
    assert any("HYROX" in g["detail"] for g in goals)


def test_ilaria_fitness_sop_and_kpi():
    goals = goals_for_ma("Ilaria.F")
    assert len(goals) == 2
    assert any("Fitness" in g["name"] for g in goals)
    assert any("240" in g["detail"] for g in goals)


def test_nina_hyrox_and_perf_lab():
    goals = goals_for_ma("Nina.S")
    names = [g["name"] for g in goals]
    assert any("HYROX" in n for n in names)
    assert any("Performance Lab" in n for n in names)


def test_marc_perf_lab():
    goals = goals_for_ma("Marc.W")
    assert any("Performance Lab" in g["name"] for g in goals)
    assert any("160" in g["detail"] for g in goals)


def test_sereina_and_anne_full_hoor():
    for ma in HOOR_OWNERS:
        goals = goals_for_ma(ma)
        assert len(goals) >= 8
        names = " ".join(g["name"] for g in goals)
        assert "Fitness" in names and "HYROX" in names and "Shop" in names


def test_all_ma_coverage():
    payload = all_ma_goals()
    for ma in PHYSIO_THERAPEUTEN + TEAMLEADS + STANDORTLEADS + HOOR_OWNERS:
        assert ma in payload
    assert "Nina.S" in payload and "Marc.W" in payload
    assert "Pamela.P" in payload
    assert "Martino.C" in payload
    assert len(payload) >= 24
