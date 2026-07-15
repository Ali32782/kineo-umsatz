"""Tests für HJ1-2026 Quali-Auswertung Import-Daten."""
from hj1_qual_eval_2026 import goals_for_ma, all_ma_goals, STANDORTLEITER_BONUS


def test_emma_has_three_kpi_goals_plus_total():
    goals = goals_for_ma("Emma.L")
    names = [g["name"] for g in goals]
    assert any("Customer Satisfaction" in n for n in names)
    assert any("Operational Excellence" in n for n in names)
    assert any("Profitabilität" in n for n in names)
    assert any("Insgesamt" in n for n in names)
    cs = next(g for g in goals if "Customer Satisfaction" in g["name"])
    assert cs["result"] == "erreicht"
    assert cs["status"] == "erreicht"


def test_hanna_leadership_only():
    goals = goals_for_ma("Hanna.R")
    assert len(goals) == 3  # leit1, leit2, insgesamt
    assert all("Customer Satisfaction" not in g["name"] for g in goals)
    leit1 = next(g for g in goals if "Leitungsziel 1" in g["name"])
    assert leit1["result"] == "80%"


def test_standortleiter_bonus_note():
    for ma in STANDORTLEITER_BONUS:
        detail = next(g["detail"] for g in goals_for_ma(ma) if "Insgesamt" in g["name"])
        assert "Pizza" in detail
        assert "500" in detail


def test_all_twelve_people():
    assert len(all_ma_goals()) == 12
