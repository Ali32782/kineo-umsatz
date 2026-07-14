"""Qualitative Ziele — Management-Input für Bilats."""
import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from database import SessionLocal, init_db, MAStammdaten
from qual_goals import replace_qual_goals, resolve_qual_goals_for_bilat, list_qual_goals
from bilat_hj1_export import build_faktenblatt, canonical_period_label


def test_canonical_period_label():
    assert canonical_period_label("HJ1 2026", 2026) == "HJ1 2026"
    assert canonical_period_label("1. HJ 2026", 2026) == "HJ1 2026"
    assert canonical_period_label(None, 2026, 6) == "HJ1 2026"
    assert canonical_period_label(None, 2026, 9) == "HJ2 2026"


def test_qual_goals_override_template_in_faktenblatt():
    init_db()
    db = SessionLocal()
    try:
        ma = db.query(MAStammdaten).filter_by(name="Noah.S").first()
        assert ma
        period = "HJ1 2026"
        replace_qual_goals(
            db,
            ma_name="Noah.S",
            year=2026,
            period_label=period,
            goals=[
                {"name": "Test-Quali aus Management-UI", "result": "88%", "status": "gut", "detail": "App"},
            ],
            updated_by="test",
        )
        assert len(list_qual_goals(db, "Noah.S", 2026, period)) == 1
        resolved = resolve_qual_goals_for_bilat(db, "Noah.S", 2026, period)
        assert resolved[0]["name"] == "Test-Quali aus Management-UI"

        fb = build_faktenblatt(ma, 2026, 6, {}, {}, None, db, period_label=period)
        assert fb["qual_goals_source"] == "db"
        assert fb["qual_goals"][0]["name"] == "Test-Quali aus Management-UI"
        assert any("Test-Quali" in p for p in fb["leitfaden_points"])
    finally:
        db.close()


def test_cc_mas_have_no_fake_template_notes():
    """CC ohne eigene Word-Vorlage: keine Barbara-Qualiziele / Fake-Notizen."""
    from bilat_template_map import has_own_bilat_template
    from database import _seed_cc_team_pamela

    init_db()
    _seed_cc_team_pamela()
    db = SessionLocal()
    try:
        for name in ("Nina.S", "Marc.W", "Ilaria.F", "Susanne.K", "Larissa.S", "Pamela.P"):
            assert not has_own_bilat_template(name)
            resolved = resolve_qual_goals_for_bilat(db, name, 2026, "HJ1 2026")
            assert resolved == []
            ma = db.query(MAStammdaten).filter_by(name=name).first()
            assert ma, f"MA {name} fehlt nach CC-Seed"
            fb = build_faktenblatt(ma, 2026, 6, {}, {}, None, db, period_label="HJ1 2026")
            assert fb["qual_goals"] == []
            assert fb["qual_goals_source"] == "none"
            joined = " ".join(fb["leitfaden_points"])
            for fake in ("Fachkontent: Schröpfen", "Dokumentationsqualität", "Provisionstermine", "Alterszentrum Letzipark"):
                assert fake not in joined
            assert fb.get("extended_rating_keys") == []
        pamela = db.query(MAStammdaten).filter_by(name="Pamela.P").first()
        assert pamela.fk_username == "sereina"
    finally:
        db.close()
