from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "../data"))


def _resolve_database_url() -> tuple[str, bool]:
    raw = os.environ.get("DATABASE_URL", "").strip()
    if raw:
        url = raw
        if url.startswith("postgres://"):
            url = "postgresql+psycopg2://" + url[len("postgres://"):]
        elif url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
            url = "postgresql+psycopg2://" + url[len("postgresql://"):]
        return url, False
    os.makedirs(DATA_DIR, exist_ok=True)
    return f"sqlite:///{os.path.join(DATA_DIR, 'kineo.db')}", True


DATABASE_URL, IS_SQLITE = _resolve_database_url()

if IS_SQLITE:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    full_name = Column(String)
    email = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    reset_token = Column(String, nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)
    role = Column(String, default="teamlead")  # ceo, coo, bd, teamlead
    team = Column(String, nullable=True)        # z.B. "Seefeld", "Wipkingen"
    linked_ma_name = Column(String, nullable=True)  # eigenes MA-Kürzel (z.B. Clara.B)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class MAStammdaten(Base):
    __tablename__ = "ma_stammdaten"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    display_name = Column(String)
    team = Column(String)
    role = Column(String, default="therapeut")  # therapeut, teamlead, sl, bd, management
    bg_pct = Column(Float, default=1.0)
    is_active = Column(Boolean, default=True)
    eintritt = Column(String, nullable=True)
    austritt = Column(String, nullable=True)
    fk_username = Column(String, nullable=True)  # zuständige/r Teamlead (users.username)

class UmsatzData(Base):
    __tablename__ = "umsatz_data"
    id = Column(Integer, primary_key=True)
    ma_name = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    umsatz = Column(Float, default=0.0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    uploaded_by = Column(String)


class MitgliederData(Base):
    """Monats-Mitgliederzahlen (z.B. Ilaria / CC)."""
    __tablename__ = "mitglieder_data"
    id = Column(Integer, primary_key=True)
    ma_name = Column(String, nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False)
    count = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
    updated_by = Column(String)

class MonthlyInput(Base):
    __tablename__ = "monthly_inputs"
    id = Column(Integer, primary_key=True)
    ma_name = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    ferien_t = Column(Float, default=0.0)
    kurs_h = Column(Float, default=0.0)
    workshop_h = Column(Float, default=0.0)
    marketing_h = Column(Float, default=0.0)
    laufanalyse_h = Column(Float, default=0.0)
    bd_h = Column(Float, default=0.0)  # Business Development (Stunden)
    krank_t = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
    updated_by = Column(String)

class MAPattern(Base):
    __tablename__ = "ma_patterns"
    id = Column(Integer, primary_key=True)
    ma_name = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    mo_pct = Column(Float, default=0.0)
    di_pct = Column(Float, default=0.0)
    mi_pct = Column(Float, default=0.0)
    do_pct = Column(Float, default=0.0)
    fr_pct = Column(Float, default=0.0)
    bg_pct = Column(Float, default=0.0)
    mgmt_pct = Column(Float, default=0.0)
    leit_h = Column(Float, default=0.0)


class MAScheduleSet(Base):
    """Versionierter Wochen-Arbeitsplan — gilt ab valid_from oder nur für override_year/month."""
    __tablename__ = "ma_schedule_sets"
    id = Column(Integer, primary_key=True)
    ma_name = Column(String, nullable=False, index=True)
    valid_from = Column(String, nullable=False)  # YYYY-MM-01
    override_year = Column(Integer, nullable=True)
    override_month = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    entries = relationship("MAScheduleEntry", back_populates="schedule_set", cascade="all, delete-orphan")


class MAScheduleEntry(Base):
    __tablename__ = "ma_schedule"
    id = Column(Integer, primary_key=True)
    ma_name = Column(String, nullable=False)
    schedule_set_id = Column(Integer, ForeignKey("ma_schedule_sets.id"), nullable=True)
    weekday = Column(Integer, nullable=False)  # 0=Mo, 1=Di, 2=Mi, 3=Do, 4=Fr
    vm_pct = Column(Float, default=0.0)
    vm_standort = Column(String, nullable=True)
    nm_pct = Column(Float, default=0.0)
    nm_standort = Column(String, nullable=True)
    schedule_set = relationship("MAScheduleSet", back_populates="entries")

class Feiertag(Base):
    __tablename__ = "feiertage"
    id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False)
    date_str = Column(String, nullable=False)  # YYYY-MM-DD
    name = Column(String, nullable=False)
    faktor = Column(Float, default=1.0)  # 1.0=ganzer Tag, 0.5=halber Tag


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    type = Column(String, nullable=False)      # "new_ma", "missing_schedule" etc.
    message = Column(String, nullable=False)
    detail = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class BilatData(Base):
    __tablename__ = "bilat_data"
    id = Column(Integer, primary_key=True)
    ma_name = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    period_label = Column(String, nullable=True)  # e.g. "HJ1 2026"
    half = Column(Integer, nullable=True)  # legacy fallback: 1 or 2
    # Kategorie A-D ratings (self + FK)
    kat_a_self = Column(Integer, nullable=True)
    kat_a_fk = Column(Integer, nullable=True)
    kat_a_comment = Column(Text, nullable=True)
    kat_b_self = Column(Integer, nullable=True)
    kat_b_fk = Column(Integer, nullable=True)
    kat_b_comment = Column(Text, nullable=True)
    kat_c_self = Column(Integer, nullable=True)
    kat_c_fk = Column(Integer, nullable=True)
    kat_c_comment = Column(Text, nullable=True)
    kat_d_self = Column(Integer, nullable=True)
    kat_d_fk = Column(Integer, nullable=True)
    kat_d_comment = Column(Text, nullable=True)
    kat_e_self = Column(Integer, nullable=True)
    kat_e_fk = Column(Integer, nullable=True)
    kat_e_comment = Column(Text, nullable=True)
    kat_f_self = Column(Integer, nullable=True)
    kat_f_fk = Column(Integer, nullable=True)
    kat_f_comment = Column(Text, nullable=True)
    # Vereinbarungen (JSON string)
    vereinbarungen = Column(Text, nullable=True)
    # Gesprächsnotizen
    themen_ma = Column(Text, nullable=True)
    gespraechseindruck = Column(String, nullable=True)
    naechstes_bilat = Column(String, nullable=True)
    flow_phase = Column(String, default="fk_prep")  # fk_prep | ma_self | reveal | done
    updated_at = Column(DateTime, default=datetime.utcnow)
    updated_by = Column(String, nullable=True)


class QualGoal(Base):
    """Qualitative Ziele / Qualitätsthemen für Bilaterals (Management-Input)."""
    __tablename__ = "qual_goals"
    id = Column(Integer, primary_key=True)
    ma_name = Column(String, nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    period_label = Column(String, nullable=False, index=True)  # z.B. HJ1 2026
    sort_order = Column(Integer, default=0)
    name = Column(String, nullable=False)
    result = Column(String, nullable=True)  # z.B. 91.7%
    status = Column(String, nullable=True)  # offen / läuft / gut / …
    detail = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
    updated_by = Column(String, nullable=True)


class MaDocument(Base):
    """Datei-Ablage pro MA (unterzeichnete Quali-PDFs, Uploads)."""
    __tablename__ = "ma_documents"
    id = Column(Integer, primary_key=True)
    ma_name = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    doc_type = Column(String, nullable=False, default="upload")  # qual_signed | upload
    year = Column(Integer, nullable=True, index=True)
    period_label = Column(String, nullable=True, index=True)
    filename = Column(String, nullable=False)
    relative_path = Column(String, nullable=False)  # optional Cache-Pfad; Inhalt primär in content
    mime_type = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    content = Column(LargeBinary, nullable=True)  # persistent in Postgres Free (ohne Disk)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=True)


class QualSignature(Base):
    """Digitale Bestätigung der Quali-Ziele (FK + MA) mit Zeitstempel."""
    __tablename__ = "qual_signatures"
    id = Column(Integer, primary_key=True)
    ma_name = Column(String, nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    period_label = Column(String, nullable=False, index=True)
    status = Column(String, default="signed")  # signed
    goals_snapshot = Column(Text, nullable=True)  # JSON
    vereinbarungen = Column(Text, nullable=True)
    fk_display_name = Column(String, nullable=True)
    fk_username = Column(String, nullable=True)
    fk_confirmed_at = Column(DateTime, nullable=True)
    ma_display_name = Column(String, nullable=True)
    ma_confirmed_at = Column(DateTime, nullable=True)
    document_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_storage_info() -> dict:
    on_render = bool(os.environ.get("RENDER"))
    if IS_SQLITE:
        db_path = os.path.join(DATA_DIR, "kineo.db")
        exists = os.path.isfile(db_path)
        return {
            "backend": "sqlite",
            "persistent": False,
            "data_dir": DATA_DIR,
            "database_exists": exists,
            "database_size_kb": round(os.path.getsize(db_path) / 1024, 1) if exists else 0,
            "on_render": on_render,
            "disk_configured": DATA_DIR.rstrip("/") == "/app/data",
        }
    return {
        "backend": "postgresql",
        "persistent": True,
        "on_render": on_render,
        "documents_in_db": True,
        "note": "Quali-PDFs liegen in Postgres (Free ohne Disk).",
    }


def _ensure_migrations_table():
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if inspector.has_table("app_migrations"):
        return
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE app_migrations ("
            "key VARCHAR PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        ))


def _migration_done(key: str) -> bool:
    from sqlalchemy import text

    _ensure_migrations_table()
    with engine.begin() as conn:
        row = conn.execute(text("SELECT 1 FROM app_migrations WHERE key = :k"), {"k": key}).fetchone()
    return row is not None


def run_migration_once(key: str, fn) -> None:
    """Einmalige Datenmigration — überschreibt Admin-Änderungen nicht bei jedem Deploy."""
    if _migration_done(key):
        return
    fn()
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app_migrations (key) VALUES (:k)"), {"k": key})


def _backfill_ma_teams():
    """Korrigiert bekannte falsche FK-Heimatstandorte in Stammdaten."""
    from ma_access import CANONICAL_MA_TEAMS

    db = SessionLocal()
    try:
        changed = False
        for ma_name, team in CANONICAL_MA_TEAMS.items():
            ma = db.query(MAStammdaten).filter_by(name=ma_name).first()
            if ma and ma.team != team:
                ma.team = team
                changed = True
        if changed:
            db.commit()
    finally:
        db.close()


def _migrate_ma_fk_columns():
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if inspector.has_table("ma_stammdaten"):
        cols = {c["name"] for c in inspector.get_columns("ma_stammdaten")}
        if "fk_username" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE ma_stammdaten ADD COLUMN fk_username VARCHAR"))
    if inspector.has_table("users"):
        cols = {c["name"] for c in inspector.get_columns("users")}
        if "linked_ma_name" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN linked_ma_name VARCHAR"))


def _backfill_user_linked_ma():
    links = {
        "clara": "Clara.B",
        "hanna": "Hanna.R",
        "raphael": "Raphael.H",
        "helen": "Helen.S",
        "pamela": "Pamela.P",
    }
    db = SessionLocal()
    try:
        changed = False
        for username, ma_name in links.items():
            user = db.query(User).filter_by(username=username).first()
            if user and not user.linked_ma_name:
                user.linked_ma_name = ma_name
                changed = True
        if changed:
            db.commit()
    finally:
        db.close()


def _backfill_standortlead_user_roles():
    """Raphael und Helen sind Standortleads (sl), keine Teamleads."""
    db = SessionLocal()
    try:
        changed = False
        for username in ("raphael", "helen"):
            user = db.query(User).filter_by(username=username).first()
            if user and user.role == "teamlead":
                user.role = "sl"
                changed = True
        if changed:
            db.commit()
    finally:
        db.close()


def _backfill_ma_fk_usernames():
    """Initiale FK-Zuordnung: Teamlead pro Standort-Team."""
    db = SessionLocal()
    try:
        teamleads = {
            u.team: u.username
            for u in db.query(User).filter(User.role == "teamlead", User.team.isnot(None)).all()
        }
        changed = False
        for ma in db.query(MAStammdaten).all():
            if ma.fk_username:
                continue
            fk = teamleads.get(ma.team)
            if fk:
                ma.fk_username = fk
                changed = True
        if changed:
            db.commit()
    finally:
        db.close()


def _seed_cc_team_pamela():
    """Pamela Possamai (CC-Leitung) + Team Nina/Marc/Ilaria/Susanne/Larissa."""
    from auth import hash_password

    db = SessionLocal()
    try:
        changed = False
        pamela = db.query(User).filter_by(username="pamela").first()
        if not pamela:
            db.add(User(
                username="pamela",
                full_name="Pamela Possamai",
                role="teamlead",
                team="CC",
                email="pamela.possamai@kineo.swiss",
                linked_ma_name="Pamela.P",
                hashed_password=hash_password("kineo2026"),
            ))
            changed = True
        else:
            if pamela.role != "teamlead":
                pamela.role = "teamlead"
                changed = True
            if pamela.team != "CC":
                pamela.team = "CC"
                changed = True
            if not pamela.linked_ma_name:
                pamela.linked_ma_name = "Pamela.P"
                changed = True
            if not pamela.email:
                pamela.email = "pamela.possamai@kineo.swiss"
                changed = True

        cc_mas = [
            # name, display, role, bg_pct
            # KPI: Nina+Marc = Umsatz; Ilaria = Mitgliederzahlen; Susanne/Larissa = keines
            ("Pamela.P", "Pamela Possamai", "teamlead", 1.0),
            ("Nina.S", "Nina Schulte", "therapeut", 1.0),
            ("Marc.W", "Marc Walser", "therapeut", 1.0),
            ("Ilaria.F", "Ilaria Ferrante", "therapeut", 1.0),
            ("Susanne.K", "Susanne K.", "therapeut", 1.0),
            ("Larissa.S", "Larissa S.", "therapeut", 1.0),
        ]
        # Pamela herself reports to COO
        fk_for = {
            "Pamela.P": "sereina",
            "Nina.S": "pamela",
            "Marc.W": "pamela",
            "Ilaria.F": "pamela",
            "Susanne.K": "pamela",
            "Larissa.S": "pamela",
        }
        for name, display, role, bg in cc_mas:
            ma = db.query(MAStammdaten).filter_by(name=name).first()
            if not ma:
                db.add(MAStammdaten(
                    name=name,
                    display_name=display,
                    team="CC",
                    role=role,
                    bg_pct=bg,
                    eintritt="2026-01-01",
                    is_active=True,
                    fk_username=fk_for[name],
                ))
                changed = True
            else:
                if ma.team != "CC":
                    ma.team = "CC"
                    changed = True
                if ma.display_name != display:
                    ma.display_name = display
                    changed = True
                if ma.fk_username != fk_for[name]:
                    ma.fk_username = fk_for[name]
                    changed = True
                if not ma.is_active:
                    ma.is_active = True
                    changed = True
        if changed:
            db.commit()
    finally:
        db.close()


def _migrate_bilat_flow_phase():
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if not inspector.has_table("bilat_data"):
        return
    cols = {c["name"] for c in inspector.get_columns("bilat_data")}
    if "flow_phase" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE bilat_data ADD COLUMN flow_phase VARCHAR DEFAULT 'fk_prep'"))
            conn.execute(text("UPDATE bilat_data SET flow_phase = 'done' WHERE flow_phase IS NULL AND kat_a_fk IS NOT NULL AND kat_a_self IS NOT NULL"))


def _migrate_bilat_kat_ef():
    """Optionale Kategorien E/F für digitale Bilats."""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if not inspector.has_table("bilat_data"):
        return
    cols = {c["name"] for c in inspector.get_columns("bilat_data")}
    needed = [
        "kat_e_self", "kat_e_fk", "kat_e_comment",
        "kat_f_self", "kat_f_fk", "kat_f_comment",
    ]
    missing = [c for c in needed if c not in cols]
    if not missing:
        return
    with engine.begin() as conn:
        for col in missing:
            typ = "TEXT" if col.endswith("_comment") else "INTEGER"
            # IF NOT EXISTS ist Postgres 9.1+ nicht überall — try/except
            try:
                conn.execute(text(f"ALTER TABLE bilat_data ADD COLUMN {col} {typ}"))
            except Exception:
                pass
    try:
        inspect(engine).clear_cache()
    except Exception:
        pass
    # Connection-Pool neu, damit nächste Queries die Spalten sehen
    try:
        engine.dispose()
    except Exception:
        pass


def ensure_bilat_ef_columns() -> None:
    """Öffentlich: vor Bilat-Save/Load aufrufen (Render Free / bestehende DBs)."""
    _migrate_bilat_kat_ef()


def _migrate_ma_documents_content():
    """BYTEA/BLOB für Ablage-Dateien — Free-Tier ohne Persistent Disk."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if not inspector.has_table("ma_documents"):
        return
    cols = {c["name"] for c in inspector.get_columns("ma_documents")}
    if "content" in cols:
        return
    with engine.begin() as conn:
        if IS_SQLITE:
            conn.execute(text("ALTER TABLE ma_documents ADD COLUMN content BLOB"))
        else:
            conn.execute(text("ALTER TABLE ma_documents ADD COLUMN content BYTEA"))


def _migrate_monthly_input_bd_h():
    """Business-Development-Stunden in monthly_inputs."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if not inspector.has_table("monthly_inputs"):
        return
    cols = {c["name"] for c in inspector.get_columns("monthly_inputs")}
    if "bd_h" in cols:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE monthly_inputs ADD COLUMN bd_h FLOAT DEFAULT 0"))


def migrate_schema():
    """Lightweight schema migrations (Spalten/Tabellen) — ohne Stammdaten zu überschreiben."""
    _migrate_bilat_flow_phase()
    _migrate_bilat_kat_ef()
    _migrate_ma_fk_columns()
    _migrate_ma_documents_content()
    _migrate_monthly_input_bd_h()
    if not IS_SQLITE:
        migrate_legacy_schedule_sets()
        _backfill_user_emails()
        _backfill_sereina_coo()
        return

    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if inspector.has_table("bilat_data"):
        cols = {c["name"] for c in inspector.get_columns("bilat_data")}
        with engine.begin() as conn:
            if "period_label" not in cols:
                conn.execute(text("ALTER TABLE bilat_data ADD COLUMN period_label VARCHAR"))
            if "half" in cols:
                conn.execute(text("""
                    UPDATE bilat_data
                    SET period_label = CASE
                        WHEN half = 1 THEN 'HJ1 ' || year
                        WHEN half = 2 THEN 'HJ2 ' || year
                        ELSE NULL
                    END
                    WHERE period_label IS NULL AND half IS NOT NULL
                """))
    if inspector.has_table("ma_schedule"):
        cols = {c["name"] for c in inspector.get_columns("ma_schedule")}
        with engine.begin() as conn:
            if "schedule_set_id" not in cols:
                conn.execute(text("ALTER TABLE ma_schedule ADD COLUMN schedule_set_id INTEGER"))
    if inspector.has_table("ma_schedule_sets"):
        cols = {c["name"] for c in inspector.get_columns("ma_schedule_sets")}
        with engine.begin() as conn:
            if "override_year" not in cols:
                conn.execute(text("ALTER TABLE ma_schedule_sets ADD COLUMN override_year INTEGER"))
            if "override_month" not in cols:
                conn.execute(text("ALTER TABLE ma_schedule_sets ADD COLUMN override_month INTEGER"))
    migrate_legacy_schedule_sets()
    if inspector.has_table("users"):
        cols = {c["name"] for c in inspector.get_columns("users")}
        with engine.begin() as conn:
            if "email" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR"))
            if "reset_token" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN reset_token VARCHAR"))
            if "reset_token_expires" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN reset_token_expires DATETIME"))
    _backfill_user_emails()
    _backfill_sereina_coo()

def _backfill_user_emails():
    """Bekannte Kineo-E-Mails für Passwort-Reset nachtragen."""
    defaults = {
        "ali": "ali.peters@kineo.swiss",
        "sereina": "sereina.urech@kineo.swiss",
        "martino": "martino.crivelli@kineo.swiss",
        "clara": "clara.benning@kineo.swiss",
        "hanna": "hanna.raffeiner@kineo.swiss",
        "raphael": "raphael.hahner@kineo.swiss",
        "helen": "helen.schwank@kineo.swiss",
    }
    db = SessionLocal()
    try:
        for username, email in defaults.items():
            user = db.query(User).filter_by(username=username).first()
            if user and not user.email:
                user.email = email
        db.commit()
    finally:
        db.close()


def _backfill_sereina_coo():
    """Sereina Urech ist COO (nicht CEO)."""
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(username="sereina").first()
        if user and user.role == "ceo":
            user.role = "coo"
            db.commit()
    finally:
        db.close()

DEPARTED_MAS = [
    {"name": "Andreas.N", "display_name": "Andreas N.", "team": "Wipkingen", "austritt": "2026-05-31"},
    {"name": "Annika.H", "display_name": "Annika H.", "team": "Seefeld", "austritt": "2026-05-31"},
    {"name": "Theresa.B", "display_name": "Theresa B.", "team": "Thalwil", "austritt": "2026-05-31"},
    {"name": "Elisabeth.M", "display_name": "Elisabeth M.", "team": "Seefeld", "austritt": "2026-02-28"},
    {"name": "Eva-Maria.Z", "display_name": "Eva-Maria Z.", "team": "Seefeld", "austritt": "2026-02-28"},
    {"name": "Felica K.", "display_name": "Felica K.", "team": "Wipkingen", "austritt": "2026-03-31"},
    {"name": "Eve.S", "display_name": "Eve S.", "team": "Stauffacher", "austritt": "2026-06-30"},
]


def _backfill_departed_mas():
    """Ausgetretene MA aus CSV — für Jan–Mai Umsätze im Dashboard."""
    from schedule_utils import seed_default_schedule_for_ma

    db = SessionLocal()
    try:
        for spec in DEPARTED_MAS:
            ma = db.query(MAStammdaten).filter_by(name=spec["name"]).first()
            if ma:
                if ma.is_active:
                    continue  # manuell reaktiviert — nicht zurücksetzen
                ma.austritt = spec["austritt"]
                ma.is_active = False
                if not ma.eintritt:
                    ma.eintritt = "2026-01-01"
            else:
                ma = MAStammdaten(
                    name=spec["name"],
                    display_name=spec["display_name"],
                    team=spec.get("team"),
                    role="therapeut",
                    bg_pct=1.0,
                    eintritt="2026-01-01",
                    austritt=spec["austritt"],
                    is_active=False,
                )
                db.add(ma)
                db.flush()
            seed_default_schedule_for_ma(db, ma, "2026-01")
        db.commit()
    finally:
        db.close()


def _backfill_missing_schedules():
    """Für alle MA ohne Arbeitsplan: Standard aus MA_PATTERNS + Team-Standort."""
    from schedule_utils import seed_default_schedule_for_ma

    db = SessionLocal()
    try:
        for ma in db.query(MAStammdaten).all():
            seed_default_schedule_for_ma(db, ma, "2026-01")
        db.commit()
    finally:
        db.close()

def migrate_legacy_schedule_sets():
    """Bestehende ma_schedule-Einträge → Version «gültig ab 2026-01»."""
    db = SessionLocal()
    try:
        from schedule_utils import create_schedule_set
        ma_names = {r[0] for r in db.query(MAScheduleEntry.ma_name).filter(MAScheduleEntry.schedule_set_id.is_(None)).distinct()}
        for ma_name in ma_names:
            if db.query(MAScheduleSet).filter_by(ma_name=ma_name).first():
                continue
            legacy = db.query(MAScheduleEntry).filter_by(ma_name=ma_name, schedule_set_id=None).all()
            if not legacy:
                continue
            days = [{
                "weekday": e.weekday, "vm_pct": e.vm_pct, "vm_standort": e.vm_standort,
                "nm_pct": e.nm_pct, "nm_standort": e.nm_standort,
            } for e in legacy]
            create_schedule_set(db, ma_name, "2026-01", days)
            for e in legacy:
                db.delete(e)
        db.commit()
    finally:
        db.close()

def seed_schedules_from_excel():
    """Arbeitspläne aus Standort-Übersicht 2026 (Excel) — nur wenn noch keine Version existiert."""
    from schedule_seed import load_excel_schedules
    from schedule_utils import create_schedule_set

    schedules = load_excel_schedules()
    if not schedules:
        seed_all_ma_schedules_fallback()
        return

    db = SessionLocal()
    for ma_name, days in schedules.items():
        if db.query(MAScheduleSet).filter_by(ma_name=ma_name).first():
            continue
        create_schedule_set(db, ma_name, "2026-01", days)
    db.commit()
    db.close()


def seed_all_ma_schedules_fallback():
    """Fallback wenn Excel fehlt: MA_PATTERNS + Haupt-Team als Standort."""
    from schedule_utils import seed_default_schedule_for_ma

    db = SessionLocal()
    for ma in db.query(MAStammdaten).all():
        seed_default_schedule_for_ma(db, ma, "2026-01")
    db.commit()
    db.close()

def migrate_schedule_halbtag_units():
    """Alte Einträge hatten 0.20 pro Halbtag — korrekt ist 0.10 (= 10 % der Woche)."""
    db = SessionLocal()
    changed = False
    for e in db.query(MAScheduleEntry).all():
        if (e.vm_pct or 0) >= 0.15:
            e.vm_pct = round((e.vm_pct or 0) / 2, 2)
            changed = True
        if (e.nm_pct or 0) >= 0.15:
            e.nm_pct = round((e.nm_pct or 0) / 2, 2)
            changed = True
    if changed:
        db.commit()
    db.close()

def _fix_pamela_fk_sereina():
    """Pamela Possamai (CC) berichtet an Sereina — erzwingen falls abweichend."""
    db = SessionLocal()
    try:
        ma = db.query(MAStammdaten).filter_by(name="Pamela.P").first()
        if not ma:
            return
        changed = False
        if ma.fk_username != "sereina":
            ma.fk_username = "sereina"
            changed = True
        if ma.team != "CC":
            ma.team = "CC"
            changed = True
        if changed:
            db.commit()
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    migrate_schema()
    seed_initial_data()
    seed_schedules_from_excel()
    _backfill_missing_schedules()
    run_migration_once("schedule_halbtag_units_v1", migrate_schedule_halbtag_units)
    run_migration_once("ma_teams_canonical_v1", _backfill_ma_teams)
    run_migration_once("departed_mas_v1", _backfill_departed_mas)
    run_migration_once("user_linked_ma_v1", _backfill_user_linked_ma)
    run_migration_once("sl_user_roles_v1", _backfill_standortlead_user_roles)
    run_migration_once("ma_fk_usernames_v1", _backfill_ma_fk_usernames)
    run_migration_once("cc_team_pamela_v1", _seed_cc_team_pamela)
    run_migration_once("cc_pamela_fk_sereina_v2", _fix_pamela_fk_sereina)
    _backfill_sereina_coo()
    # Idempotent: FK Pam → Sereina bei jedem Start absichern
    _fix_pamela_fk_sereina()

def seed_initial_data():
    """Seed users and MA Stammdaten on first run"""
    from auth import hash_password
    db = SessionLocal()

    # Seed users if empty
    if db.query(User).count() == 0:
        users = [
            User(username="ali", full_name="Ali Peters", role="ceo", email="ali.peters@kineo.swiss",
                 hashed_password=hash_password("kineo2026")),
            User(username="martino", full_name="Martino Crivelli", role="bd", email="martino.crivelli@kineo.swiss",
                 hashed_password=hash_password("kineo2026")),
            User(username="sereina", full_name="Sereina Urech", role="coo", email="sereina.urech@kineo.swiss",
                 hashed_password=hash_password("kineo2026")),
            User(username="clara", full_name="Clara Benning", role="teamlead", team="Escher Wyss",
                 email="clara.benning@kineo.swiss", hashed_password=hash_password("kineo2026")),
            User(username="hanna", full_name="Hanna Raffeiner", role="teamlead", team="Thalwil",
                 email="hanna.raffeiner@kineo.swiss", hashed_password=hash_password("kineo2026")),
            User(username="raphael", full_name="Raphael H.", role="sl", team="Wipkingen",
                 email="raphael.hahner@kineo.swiss", hashed_password=hash_password("kineo2026")),
            User(username="helen", full_name="Helen S.", role="sl", team="Zollikon",
                 email="helen.schwank@kineo.swiss", hashed_password=hash_password("kineo2026")),
            User(username="pamela", full_name="Pamela Possamai", role="teamlead", team="CC",
                 email="pamela.possamai@kineo.swiss", linked_ma_name="Pamela.P",
                 hashed_password=hash_password("kineo2026")),
        ]
        db.add_all(users)

    # Seed MA Stammdaten if empty
    if db.query(MAStammdaten).count() == 0:
        mas = [
            MAStammdaten(name="Andrina.K", display_name="Andrina K.", team="Seefeld", role="sl", bg_pct=0.9, eintritt="2026-01-01"),
            MAStammdaten(name="Barbara.V", display_name="Barbara V.", team="Wipkingen", role="therapeut", bg_pct=0.8, eintritt="2026-01-01"),
            MAStammdaten(name="Carmen.W", display_name="Carmen W.", team="Stauffacher", role="sl", bg_pct=0.4, eintritt="2026-01-01"),
            MAStammdaten(name="Clara.B", display_name="Clara B.", team="Escher Wyss", role="teamlead", bg_pct=0.8, eintritt="2026-01-01"),
            MAStammdaten(name="Emma.L", display_name="Emma L.", team="Wipkingen", role="therapeut", bg_pct=1.0, eintritt="2026-01-01"),
            MAStammdaten(name="Eva.D", display_name="Eva D.", team="Seefeld", role="therapeut", bg_pct=1.0, eintritt="2026-01-01"),
            MAStammdaten(name="Hanna.R", display_name="Hanna R.", team="Thalwil", role="teamlead", bg_pct=1.0, eintritt="2026-01-01"),
            MAStammdaten(name="Helen.S", display_name="Helen S.", team="Zollikon", role="sl", bg_pct=0.8, eintritt="2026-03-01"),
            MAStammdaten(name="Joëlle.R", display_name="Joëlle R.", team="Stauffacher", role="therapeut", bg_pct=0.9, eintritt="2026-01-01"),
            MAStammdaten(name="Lucrecia.G", display_name="Lucrecia G.", team="Wipkingen", role="therapeut", bg_pct=0.8, eintritt="2026-06-01"),
            MAStammdaten(name="Martino.C", display_name="Martino C.", team="Management", role="bd", bg_pct=1.0, eintritt="2026-01-01"),
            MAStammdaten(name="Meike.V", display_name="Meike V.", team="Seefeld", role="therapeut", bg_pct=0.8, eintritt="2026-01-01"),
            MAStammdaten(name="Noah.S", display_name="Noah S.", team="Seefeld", role="therapeut", bg_pct=0.6, eintritt="2026-01-01"),
            MAStammdaten(name="Pablo.G", display_name="Pablo G.", team="Seefeld", role="therapeut", bg_pct=0.8, eintritt="2026-06-01"),
            MAStammdaten(name="Pablo.M", display_name="Pablo M.", team="Stauffacher", role="therapeut", bg_pct=0.8, eintritt="2026-06-01"),
            MAStammdaten(name="Raphael.H", display_name="Raphael H.", team="Wipkingen", role="sl", bg_pct=0.8, eintritt="2026-03-01"),
            MAStammdaten(name="Sereina.U", display_name="Sereina U.", team="Management", role="management", bg_pct=0.9, eintritt="2026-01-01"),
            MAStammdaten(name="Sonia.M", display_name="Sonia M.", team="Thalwil", role="therapeut", bg_pct=1.0, eintritt="2026-01-01"),
            MAStammdaten(name="Valerio.S", display_name="Valerio S.", team="Escher Wyss", role="therapeut", bg_pct=0.6, eintritt="2026-05-01"),
        ]
        for spec in DEPARTED_MAS:
            mas.append(MAStammdaten(
                name=spec["name"], display_name=spec["display_name"], team=spec.get("team"),
                role="therapeut", bg_pct=1.0, eintritt="2026-01-01",
                austritt=spec["austritt"], is_active=False,
            ))
        db.add_all(mas)

    db.commit()
    db.close()
