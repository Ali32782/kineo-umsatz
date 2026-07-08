"""Tests für Bilateral-Export mit pro-MA-Vorlagen."""
from pathlib import Path

from bilat_hj1_export import fill_hj1_template, _find_tables
from bilat_template_map import MA_BILAT_TEMPLATE, resolve_bilat_template, TEMPLATES_DIR
from docx import Document


def test_all_mapped_templates_exist():
    for ma_name, filename in MA_BILAT_TEMPLATE.items():
        path = TEMPLATES_DIR / filename
        assert path.is_file(), f"Vorlage fehlt für {ma_name}: {filename}"


def test_resolve_bilat_template_barbara():
    path = resolve_bilat_template("Barbara.V")
    assert path.name == "Bilat_Barbara_V_HJ1_2026.docx"


def test_template_has_expected_sections():
    doc = Document(resolve_bilat_template("Barbara.V"))
    tables = _find_tables(doc)
    assert "header" in tables
    assert "zeg_matrix" in tables
    assert "qual_goals" in tables
    assert "ratings" in tables
    assert "perf_detail" in tables
    assert "calc_detail" in tables
    assert "leitfaden" in tables


def test_generate_bilat_barbara(tmp_path):
    import os
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    from database import init_db, SessionLocal, MAStammdaten, UmsatzData

    init_db()
    db = SessionLocal()
    try:
        ma = db.query(MAStammdaten).filter_by(name="Barbara.V").first()
        if not ma:
            return
        db.add(UmsatzData(ma_name="Barbara.V", year=2026, month=3, umsatz=20000))
        db.commit()
        out = tmp_path / "out.docx"
        fill_hj1_template(ma, 2026, 6, {("Barbara.V", 3): 20000}, {}, None, db, str(out))
        assert out.is_file()
        doc = Document(out)
        tables = _find_tables(doc)
        assert "qual_goals" in tables
        goals = [r.cells[0].text for r in tables["qual_goals"].rows[1:3]]
        assert any("Schröpfen" in g or "Dokumentation" in g for g in goals)
    finally:
        db.close()
