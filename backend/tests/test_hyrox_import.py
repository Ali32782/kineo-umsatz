"""Tests HYROX Training-Club Rechnungsimport."""
from pathlib import Path

from hyrox_import import parse_hyrox_invoices_excel

FIX = Path(__file__).resolve().parent.parent / "fixtures"


def test_parse_hyrox_invoices():
    path = FIX / "hyrox_invoices.xlsx"
    assert path.is_file(), f"Fixture fehlt: {path}"
    rows = parse_hyrox_invoices_excel(path)
    assert len(rows) >= 6
    by = {(r["year"], r["month"]): r for r in rows}
    assert (2026, 1) in by
    assert by[(2026, 1)]["umsatz"] > 9000
    assert by[(2026, 1)]["count"] > 50
    # nur Bezahlt + Stunde Hyrox
    total = sum(r["umsatz"] for r in rows)
    assert 30000 < total < 40000
