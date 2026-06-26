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


class MAScheduleEntry(Base):
    __tablename__ = "ma_schedule"
    id = Column(Integer, primary_key=True)
    ma_name = Column(String, nullable=False)
    weekday = Column(Integer, nullable=False)  # 0=Mo, 1=Di, 2=Mi, 3=Do, 4=Fr
    vm_pct = Column(Float, default=0.0)
    vm_standort = Column(String, nullable=True)
    nm_pct = Column(Float, default=0.0)
    nm_standort = Column(String, nullable=True)

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
    half = Column(Integer, nullable=False)  # 1 or 2
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

def init_db():
    Base.metadata.create_all(bind=engine)
    seed_initial_data()

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
            MAStammdaten(name="Meike.V", display_name="Meike V.", team="Thalwil", role="therapeut", bg_pct=0.8, eintritt="2026-01-01"),
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
