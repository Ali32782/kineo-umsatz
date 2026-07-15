"""Tests für Fitness-Abo- und Runnerslab-Excel-Parser."""
from pathlib import Path

from fitness_abo_import import parse_fitness_abo_excel
from runnerslab_import import parse_runnerslab_excel

FIX = Path(__file__).resolve().parent.parent / "fixtures"


def test_parse_fitness_abo_sample():
    rows = parse_fitness_abo_excel(FIX / "fitness_abo_sample.xlsx")
    by_m = {r["month"]: r["count"] for r in rows if r["year"] == 2026}
    # KW 6–9 → Feb (169); KW 10+13 → Mär (166); KW 14+18 → Apr (159); KW 19 → Mai (159)
    assert by_m[2] == 169
    assert by_m[3] == 166
    assert by_m[4] == 159
    assert by_m[5] == 159


def test_parse_runnerslab_sample():
    rows = parse_runnerslab_excel(FIX / "runnerslab_sample.xlsx")
    by_m = {r["month"]: r["umsatz"] for r in rows if r["year"] == 2026}
    assert by_m == {1: 110.0, 2: 220.0, 3: 330.0, 4: 440.0, 5: 550.0}


def test_parse_real_fitness_if_present():
    path = FIX / "fitness_abo_thalwil.xlsx"
    if not path.is_file():
        return
    rows = parse_fitness_abo_excel(path)
    y26 = {r["month"]: r["count"] for r in rows if r["year"] == 2026}
    assert y26[2] == 169
    assert y26[3] == 166
    assert y26[4] == 159
    assert y26[5] == 159


def test_parse_real_runnerslab_if_present():
    path = FIX / "runnerslab_umsaetze.xlsx"
    if not path.is_file():
        return
    rows = parse_runnerslab_excel(path)
    y26 = {r["month"]: r["umsatz"] for r in rows if r["year"] == 2026}
    assert y26[1] == 13049.0
    assert y26[5] == 31964.4
