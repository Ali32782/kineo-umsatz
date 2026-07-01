import os
from pathlib import Path

import pytest

_test_dir = os.path.join(os.path.dirname(__file__), "..", "data")
_xlsx = Path(_test_dir) / "Kineo_Standort_Uebersicht_2026.xlsx"

from schedule_seed import (  # noqa: E402
    parse_day_cell,
    load_excel_schedules,
    normalize_standort,
)


@pytest.mark.skipif(not _xlsx.exists(), reason="Excel seed file missing")
def test_load_excel_schedules_count():
    schedules = load_excel_schedules(_xlsx)
    assert len(schedules) == 19


@pytest.mark.skipif(not _xlsx.exists(), reason="Excel seed file missing")
def test_emma_mixed_standorte():
    schedules = load_excel_schedules(_xlsx)
    emma = {d["weekday"]: d for d in schedules["Emma.L"]}
    assert emma[0]["vm_standort"] == "Thalwil"
    assert emma[1]["vm_standort"] == "Stauffacher"
    assert emma[2]["vm_standort"] == "Thalwil"


def test_parse_split_day():
    vm, vm_loc, nm, nm_loc = parse_day_cell("Seefeld/Stauf.", 0.20)
    assert vm == 0.10 and vm_loc == "Seefeld"
    assert nm == 0.10 and nm_loc == "Stauffacher"


def test_parse_vm_only():
    vm, vm_loc, nm, nm_loc = parse_day_cell("Stauffacher VM", 0.10)
    assert vm == 0.10 and vm_loc == "Stauffacher"
    assert nm == 0.0 and nm_loc is None


def test_parse_half_day_single_standort():
    vm, vm_loc, nm, nm_loc = parse_day_cell("Seefeld", 0.10)
    assert vm == 0.10 and vm_loc == "Seefeld"
    assert nm == 0.0


def test_parse_full_day():
    vm, vm_loc, nm, nm_loc = parse_day_cell("Wipkingen", 0.20)
    assert vm == 0.10 and nm == 0.10
    assert vm_loc == nm_loc == "Wipkingen"


def test_normalize_aliases():
    assert normalize_standort("Stauf.") == "Stauffacher"
    assert normalize_standort("Off.") == "Office"
