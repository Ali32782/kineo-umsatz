"""CC-Team unter Pamela Possamai."""
import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from database import SessionLocal, User, MAStammdaten, init_db, _seed_cc_team_pamela
from ma_access import filter_mas_for_user


def test_seed_cc_team_pamela_creates_user_and_reports():
    init_db()
    _seed_cc_team_pamela()  # idempotent
    db = SessionLocal()
    try:
        pamela = db.query(User).filter_by(username="pamela").first()
        assert pamela is not None
        assert pamela.role == "teamlead"
        assert pamela.team == "CC"
        assert pamela.linked_ma_name == "Pamela.P"

        names = {
            "Pamela.P", "Nina.S", "Marc.W", "Ilaria.F", "Susanne.K", "Larissa.S",
        }
        mas = {m.name: m for m in db.query(MAStammdaten).filter(MAStammdaten.name.in_(names)).all()}
        assert set(mas) == names
        for name in ("Nina.S", "Marc.W", "Ilaria.F", "Susanne.K", "Larissa.S"):
            assert mas[name].fk_username == "pamela"
            assert mas[name].team == "CC"
        assert mas["Pamela.P"].fk_username == "sereina"

        from ma_access import CC_KPI_TYPE
        assert CC_KPI_TYPE["Nina.S"] == "umsatz"
        assert CC_KPI_TYPE["Marc.W"] == "umsatz"
        assert CC_KPI_TYPE["Ilaria.F"] == "mitglieder"
        from calc import MA_PATTERNS
        assert "Nina.S" in MA_PATTERNS and "Marc.W" in MA_PATTERNS
        assert "Ilaria.F" not in MA_PATTERNS

        visible = filter_mas_for_user(
            db.query(MAStammdaten).all(), pamela, db, year=2026, months=list(range(1, 7)),
        )
        visible_names = {m.name for m in visible}
        assert "Nina.S" in visible_names
        assert "Marc.W" in visible_names
        assert "Ilaria.F" in visible_names
        assert "Susanne.K" in visible_names
        assert "Larissa.S" in visible_names
        assert "Pamela.P" in visible_names  # linked own MA
        assert "Noah.S" not in visible_names
    finally:
        db.close()
