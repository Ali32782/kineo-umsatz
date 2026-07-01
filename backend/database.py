from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "../data"))
os.makedirs(DATA_DIR, exist_ok=True)
DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'kineo.db')}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    full_name = Column(String)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="teamlead")  # ceo, bd, teamlead
    team = Column(String, nullable=True)        # z.B. "Seefeld", "Wipkingen"
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

class UmsatzData(Base):
    __tablename__ = "umsatz_data"
    id = Column(Integer, primary_key=True)
    ma_name = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    umsatz = Column(Float, default=0.0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    uploaded_by = Column(String)

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
    """Versionierter Wochen-Arbeitsplan — gilt ab valid_from (YYYY-MM-01) für alle folgenden Monate."""
    __tablename__ = "ma_schedule_sets"
    id = Column(Integer, primary_key=True)
    ma_name = Column(String, nullable=False, index=True)
    valid_from = Column(String, nullable=False)  # YYYY-MM-01
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
    # Vereinbarungen (JSON string)
    vereinbarungen = Column(Text, nullable=True)
    # Gesprächsnotizen
    themen_ma = Column(Text, nullable=True)
    gespraechseindruck = Column(String, nullable=True)
    naechstes_bilat = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
    updated_by = Column(String, nullable=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def migrate_schema():
    """Lightweight SQLite migrations for existing databases."""
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
    migrate_legacy_schedule_sets()

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
    meike = db.query(MAStammdaten).filter_by(name="Meike.V").first()
    if meike and meike.team == "Thalwil":
        meike.team = "Seefeld"
    db.commit()
    db.close()


def seed_all_ma_schedules_fallback():
    """Fallback wenn Excel fehlt: MA_PATTERNS + Haupt-Team als Standort."""
    from calc import MA_PATTERNS, day_pct_to_halves
    from schedule_utils import create_schedule_set
    db = SessionLocal()
    day_keys = {0: "mo", 1: "di", 2: "mi", 3: "do", 4: "fr"}
    mas = db.query(MAStammdaten).filter_by(is_active=True).all()
    for ma in mas:
        if db.query(MAScheduleSet).filter_by(ma_name=ma.name).first():
            continue
        pat = MA_PATTERNS.get(ma.name, {})
        standort = ma.team if ma.team not in ("Management", "Office") else None
        days = []
        for wd, key in day_keys.items():
            vm, nm = day_pct_to_halves(pat.get(key, 0) or 0)
            if vm or nm:
                days.append({
                    "weekday": wd, "vm_pct": vm, "vm_standort": standort if vm else None,
                    "nm_pct": nm, "nm_standort": standort if nm else None,
                })
        if days:
            create_schedule_set(db, ma.name, "2026-01", days)
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

def init_db():
    Base.metadata.create_all(bind=engine)
    migrate_schema()
    migrate_schedule_halbtag_units()
    seed_initial_data()
    seed_schedules_from_excel()

def seed_initial_data():
    """Seed users and MA Stammdaten on first run"""
    from auth import hash_password
    db = SessionLocal()

    # Seed users if empty
    if db.query(User).count() == 0:
        users = [
            User(username="ali", full_name="Ali Peters", role="ceo",
                 hashed_password=hash_password("kineo2026")),
            User(username="martino", full_name="Martino Crivelli", role="bd",
                 hashed_password=hash_password("kineo2026")),
            User(username="sereina", full_name="Sereina Urech", role="ceo",
                 hashed_password=hash_password("kineo2026")),
            User(username="clara", full_name="Clara Benning", role="teamlead", team="Escher Wyss",
                 hashed_password=hash_password("kineo2026")),
            User(username="hanna", full_name="Hanna Raffeiner", role="teamlead", team="Thalwil",
                 hashed_password=hash_password("kineo2026")),
            User(username="raphael", full_name="Raphael H.", role="teamlead", team="Wipkingen",
                 hashed_password=hash_password("kineo2026")),
            User(username="helen", full_name="Helen S.", role="teamlead", team="Zollikon",
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
        db.add_all(mas)

    db.commit()
    db.close()
