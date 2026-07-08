from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
from typing import Optional, List
from jose import JWTError, jwt
from pydantic import BaseModel
import os, io, json

from database import get_db, init_db, get_storage_info, User, UmsatzData, MonthlyInput, MAStammdaten, MAScheduleEntry, MAScheduleSet, Feiertag, Notification, BilatData
from calc import (
    compute_zeg, compute_soll_tage, parse_csv_umsatz, parse_csv_umsatz_result,
    parse_csv_pivot_all_months_result,
    zeg_color, MONTH_NAMES_DE, MA_PATTERNS,
    is_employed_in_month,
)
from email_service import email_zeg_alarm, email_csv_reminder
from auth import has_full_access
from ma_access import filter_mas_for_user, months_for_period

def _require_full_access(user: User) -> None:
    if not has_full_access(user.role):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

# ── Config ────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", "kineo-secret-2026-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours
APP_BASE_URL = os.environ.get("APP_BASE_URL", "https://kineo-leadership.onrender.com").rstrip("/")

app = FastAPI(title="Kineo Umsatzanalyse", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Init DB on startup
@app.on_event("startup")
def startup():
    init_db()

# ── Auth ──────────────────────────────────────────────────────────────────
class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict

class LoginRequest(BaseModel):
    username: str
    password: str

def create_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(status_code=401, detail="Ungültige Anmeldedaten")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise credentials_exception
    return user

@app.post("/api/login", response_model=Token)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    from auth import verify_password
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Falscher Benutzername oder Passwort")
    token = create_token({"sub": user.username})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "team": user.team,
        }
    }

class ForgotPasswordRequest(BaseModel):
    identifier: str  # Benutzername oder E-Mail

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

@app.post("/api/auth/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Reset-Link per E-Mail — antwortet immer gleich (kein User-Enumeration)."""
    import secrets
    from email_service import email_password_reset

    ident = req.identifier.strip().lower()
    user = db.query(User).filter(
        (User.username == ident) | (User.email == ident)
    ).first()

    msg = "Falls ein Konto existiert, wurde ein Link an die hinterlegte E-Mail gesendet."
    if user and user.is_active and user.email:
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        db.commit()
        reset_url = f"{APP_BASE_URL}/?reset={token}"
        email_password_reset(user.email, reset_url, user.full_name or user.username)
    return {"message": msg}

@app.post("/api/auth/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    from auth import hash_password

    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Passwort muss mindestens 8 Zeichen haben")
    user = db.query(User).filter_by(reset_token=req.token).first()
    if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Link ungültig oder abgelaufen")
    user.hashed_password = hash_password(req.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()
    return {"message": "Passwort wurde gesetzt — du kannst dich jetzt anmelden."}

# ── MA Stammdaten ─────────────────────────────────────────────────────────
@app.get("/api/ma")
def get_ma_list(
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    all_mas = db.query(MAStammdaten).all()
    if year and month:
        mas = [
            m for m in all_mas
            if is_employed_in_month(m.eintritt, m.austritt, year, month, m.is_active)
        ]
    else:
        mas = [m for m in all_mas if m.is_active]
    mas = filter_mas_for_user(mas, current_user, db, year=year, months=[month] if year and month else None)
    return [{
        "name": m.name, "display_name": m.display_name, "team": m.team,
        "role": m.role, "bg_pct": m.bg_pct, "eintritt": m.eintritt,
        "austritt": m.austritt, "is_active": m.is_active,
    } for m in mas]

# ── CSV Upload ────────────────────────────────────────────────────────────
@app.post("/api/upload-csv")
async def upload_csv(
    file: UploadFile = File(...),
    year: int = Form(...),
    month: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not has_full_access(current_user.role):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    content = await file.read()
    try:
        text = content.decode('utf-8-sig')
    except:
        text = content.decode('latin-1')

    mas = db.query(MAStammdaten).all()
    from abwesenheiten_import import match_ma_name

    def resolve_umsatz_map(umsatz_map: dict) -> tuple[dict[str, float], list[str]]:
        resolved: dict[str, float] = {}
        unmatched: list[str] = []
        for csv_name, amount in umsatz_map.items():
            ma = next((m for m in mas if m.name == csv_name), None)
            ma_name = csv_name if ma else match_ma_name(csv_name, mas)
            if ma_name:
                resolved[ma_name] = resolved.get(ma_name, 0) + amount
            else:
                unmatched.append(csv_name)
        return resolved, unmatched

    pivot_all = parse_csv_pivot_all_months_result(text, year)
    if pivot_all:
        warnings = list(pivot_all.get("warnings") or [])
        months_imported: list[int] = []
        total_inserted = 0
        all_unmatched: list[str] = []
        preview_resolved: dict[str, float] = {}
        for m in pivot_all["months"]:
            resolved, unmatched = resolve_umsatz_map(pivot_all["by_month"][m])
            if not resolved:
                continue
            all_unmatched.extend(unmatched)
            db.query(UmsatzData).filter(
                UmsatzData.year == year,
                UmsatzData.month == m,
            ).delete()
            for name, amount in resolved.items():
                db.add(UmsatzData(
                    ma_name=name, year=year, month=m,
                    umsatz=amount, uploaded_by=current_user.username,
                ))
            total_inserted += len(resolved)
            months_imported.append(m)
            if m == month:
                preview_resolved = resolved

        if not months_imported:
            raise HTTPException(
                status_code=400,
                detail="Keine Mitarbeiter in der CSV erkannt — bestehende Werte wurden nicht gelöscht.",
            )

        db.commit()
        first, last = months_imported[0], months_imported[-1]
        range_label = (
            f"{MONTH_NAMES_DE[first]}–{MONTH_NAMES_DE[last]} {year}"
            if first != last else f"{MONTH_NAMES_DE[first]} {year}"
        )
        msg = f"{total_inserted} MA-Einträge für {len(months_imported)} Monate importiert ({range_label})"
        unmatched = sorted(set(all_unmatched))
        if unmatched:
            msg += f" — {len(unmatched)} nicht zugeordnet"
        return {
            "message": msg,
            "data": preview_resolved or resolve_umsatz_map(pivot_all["by_month"][months_imported[-1]])[0],
            "months_imported": months_imported,
            "unmatched": unmatched,
            "warnings": warnings,
            "total_umsatz": round(sum(preview_resolved.values()), 2) if preview_resolved else 0,
        }

    csv_result = parse_csv_umsatz_result(text, year=year, month=month)
    umsatz_map = csv_result["by_name"]
    if not umsatz_map:
        raise HTTPException(
            status_code=400,
            detail="CSV enthält keine Umsatzdaten — bestehende Werte wurden nicht gelöscht.",
        )

    # Plausibilität: Summe vs. Vormonate
    warnings = list(csv_result.get("warnings") or [])
    prev_rows = db.query(UmsatzData).filter(
        UmsatzData.year == year,
        UmsatzData.month < month,
    ).all()
    if prev_rows:
        from collections import defaultdict
        by_m = defaultdict(float)
        for r in prev_rows:
            by_m[r.month] += r.umsatz
        if by_m:
            med = sorted(by_m.values())[len(by_m) // 2]
            new_total = sum(umsatz_map.values())
            if med > 0 and new_total > med * 2.5:
                warnings.append(
                    f"Gesamtumsatz CHF {new_total:,.0f} ist ungewöhnlich hoch "
                    f"(Median Vormonate: CHF {med:,.0f}). Bitte Monatsexport prüfen."
                )

    resolved, unmatched = resolve_umsatz_map(umsatz_map)

    if not resolved:
        raise HTTPException(
            status_code=400,
            detail="Keine Mitarbeiter in der CSV erkannt — bestehende Werte wurden nicht gelöscht.",
        )

    # Delete existing entries for this month (nur nach erfolgreicher Validierung)
    db.query(UmsatzData).filter(
        UmsatzData.year == year,
        UmsatzData.month == month
    ).delete()

    inserted = 0
    for name, amount in resolved.items():
        db.add(UmsatzData(
            ma_name=name, year=year, month=month,
            umsatz=amount, uploaded_by=current_user.username
        ))
        inserted += 1

    db.commit()
    msg = f"{inserted} MA-Umsätze für {MONTH_NAMES_DE[month]} {year} importiert"
    if unmatched:
        msg += f" — {len(unmatched)} nicht zugeordnet"
    if warnings:
        msg += " — " + " ".join(warnings)
    return {
        "message": msg,
        "data": resolved,
        "months_imported": [month],
        "unmatched": unmatched,
        "warnings": warnings,
        "total_umsatz": round(sum(resolved.values()), 2),
    }

# ── Abwesenheiten Excel Upload ────────────────────────────────────────────
@app.post("/api/upload-abwesenheiten")
async def upload_abwesenheiten(
    file: UploadFile = File(...),
    year: int = Form(...),
    month: int = Form(...),
    all_months: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_full_access(current_user.role):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Bitte eine Excel-Datei (.xlsx) hochladen")

    content = await file.read()
    mas = db.query(MAStammdaten).all()
    from abwesenheiten_import import parse_abwesenheiten_xlsx, parse_abwesenheiten_xlsx_for_year

    try:
        if all_months:
            result = parse_abwesenheiten_xlsx_for_year(content, year, mas)
        else:
            single = parse_abwesenheiten_xlsx(content, year, month, mas)
            result = {
                "by_month": {month: single["by_ma"]} if single["by_ma"] else {},
                "months": [month] if single["by_ma"] else [],
                "details": single["details"],
                "unmatched": single["unmatched"],
                "skipped": single["skipped"],
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel konnte nicht gelesen werden: {e}")

    if not result["months"] and not result["unmatched"]:
        raise HTTPException(status_code=400, detail="Keine Abwesenheiten für dieses Jahr gefunden")

    now = datetime.utcnow()
    inputs_saved: dict[str, dict] = {}
    total_ma = 0

    def save_month(m: int, by_ma: dict):
        nonlocal total_ma
        for ma_name, vals in by_ma.items():
            existing = db.query(MonthlyInput).filter(
                MonthlyInput.ma_name == ma_name,
                MonthlyInput.year == year,
                MonthlyInput.month == m,
            ).first()
            if existing:
                existing.ferien_t = vals["ferien_t"]
                existing.krank_t = vals["krank_t"]
                existing.updated_at = now
                existing.updated_by = current_user.username
                row = existing
            else:
                row = MonthlyInput(
                    ma_name=ma_name, year=year, month=m,
                    ferien_t=vals["ferien_t"], krank_t=vals["krank_t"],
                    updated_at=now, updated_by=current_user.username,
                )
                db.add(row)
            total_ma += 1
            if m == month:
                inputs_saved[ma_name] = {
                    "ferien_t": vals["ferien_t"],
                    "krank_t": vals["krank_t"],
                    "kurs_h": row.kurs_h or 0,
                    "workshop_h": row.workshop_h or 0,
                    "marketing_h": row.marketing_h or 0,
                    "laufanalyse_h": row.laufanalyse_h or 0,
                    "notes": row.notes,
                }

    for m in result["months"]:
        save_month(m, result["by_month"][m])

    db.commit()

    months_imported = result["months"]
    if len(months_imported) > 1:
        range_label = (
            f"{MONTH_NAMES_DE[months_imported[0]]}–{MONTH_NAMES_DE[months_imported[-1]]} {year}"
        )
        msg = f"Ferien & Krank für {len(months_imported)} Monate importiert ({range_label})"
    elif months_imported:
        msg = f"{len(result['by_month'][months_imported[0]])} Mitarbeiter/innen — Ferien & Krank für {MONTH_NAMES_DE[months_imported[0]]} {year}"
    else:
        msg = "Keine passenden Abwesenheiten importiert"
    if result["unmatched"]:
        msg += f" — {len(result['unmatched'])} nicht zugeordnet"

    return {
        "message": msg,
        "data": result["by_month"].get(month, {}),
        "inputs": inputs_saved,
        "details": result["details"],
        "months_imported": months_imported,
        "unmatched": result["unmatched"],
        "skipped": result["skipped"],
    }

# ── Monthly Inputs ────────────────────────────────────────────────────────
class MonthlyInputData(BaseModel):
    ma_name: str
    year: int
    month: int
    ferien_t: float = 0
    kurs_h: float = 0
    workshop_h: float = 0
    marketing_h: float = 0
    laufanalyse_h: float = 0
    krank_t: float = 0
    notes: Optional[str] = None

@app.get("/api/inputs/{year}/{month}")
def get_inputs(
    year: int, month: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    inputs = db.query(MonthlyInput).filter(
        MonthlyInput.year == year,
        MonthlyInput.month == month
    ).all()
    return {i.ma_name: {
        "ferien_t": i.ferien_t, "kurs_h": i.kurs_h, "workshop_h": i.workshop_h,
        "marketing_h": i.marketing_h, "laufanalyse_h": i.laufanalyse_h,
        "krank_t": i.krank_t, "notes": i.notes
    } for i in inputs}

@app.post("/api/inputs")
def save_inputs(
    data: List[MonthlyInputData],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not has_full_access(current_user.role):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    for item in data:
        existing = db.query(MonthlyInput).filter(
            MonthlyInput.ma_name == item.ma_name,
            MonthlyInput.year == item.year,
            MonthlyInput.month == item.month,
        ).first()
        if existing:
            for field in ["ferien_t","kurs_h","workshop_h","marketing_h","laufanalyse_h","krank_t","notes"]:
                setattr(existing, field, getattr(item, field))
            existing.updated_at = datetime.utcnow()
            existing.updated_by = current_user.username
        else:
            db.add(MonthlyInput(
                **item.dict(),
                updated_at=datetime.utcnow(),
                updated_by=current_user.username
            ))
    db.commit()
    return {"message": f"{len(data)} Einträge gespeichert"}

# ── Dashboard / ZEG Data ──────────────────────────────────────────────────
@app.get("/api/dashboard/{year}/{month}")
def get_dashboard(
    year: int, month: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    all_mas = db.query(MAStammdaten).all()
    mas = [
        m for m in all_mas
        if is_employed_in_month(m.eintritt, m.austritt, year, month, m.is_active)
    ]
    mas = filter_mas_for_user(mas, current_user, db, year=year, months=[month])

    umsatz_rows = db.query(UmsatzData).filter(
        UmsatzData.year == year, UmsatzData.month == month
    ).all()
    umsatz_map = {r.ma_name: r.umsatz for r in umsatz_rows}

    input_rows = db.query(MonthlyInput).filter(
        MonthlyInput.year == year, MonthlyInput.month == month
    ).all()
    input_map = {r.ma_name: r for r in input_rows}

    results = []
    for ma in mas:
        name = ma.name
        umsatz = umsatz_map.get(name, 0)
        inp = input_map.get(name)
        zeg = compute_zeg(
            name, year, month, umsatz,
            ferien_t=inp.ferien_t if inp else 0,
            kurs_h=inp.kurs_h if inp else 0,
            workshop_h=inp.workshop_h if inp else 0,
            marketing_h=inp.marketing_h if inp else 0,
            laufanalyse_h=inp.laufanalyse_h if inp else 0,
            krank_t=inp.krank_t if inp else 0,
            db=db,
        )
        results.append({
            "name": name,
            "display_name": ma.display_name,
            "team": ma.team,
            "role": ma.role,
            "umsatz": umsatz,
            "color": zeg_color(zeg["zeg_b"]),
            **zeg,
        })

    # Load schedule for multi-standort splitting (pro Monat die gültige Version)
    schedule_map = {}
    for ma in mas:
        from schedule_utils import get_schedule_entries_for_month
        schedule_map[ma.name] = get_schedule_entries_for_month(ma.name, year, month, db)

    # Build multi-standort ma_data entries (ZEG-B + Umsatz pro Standort, inkl. Office)
    from standort_calc import expand_ma_standort_rows, aggregate_team_summary

    ma_data_expanded = []
    for r in results:
        schedule = schedule_map.get(r["name"])
        ma_bg = r.get("bg_pct") or next((m.bg_pct for m in mas if m.name == r["name"]), 1.0)
        ma_data_expanded.extend(expand_ma_standort_rows(r, ma_bg, r["team"], schedule))

    team_summary = aggregate_team_summary(ma_data_expanded)

    total_fte_all = round(sum(r["bg_pct"] for r in ma_data_expanded), 1)
    from umsatz_agg import sum_umsatz_for_month
    umsatz_map_all = {(r.ma_name, r.month): r.umsatz for r in umsatz_rows}
    total_umsatz = round(sum_umsatz_for_month(umsatz_map_all, mas, month))

    return {
        "year": year,
        "month": month,
        "month_name": MONTH_NAMES_DE[month],
        "ma_data": ma_data_expanded,
        "team_summary": team_summary,
        "total_umsatz": total_umsatz,
        "team_umsatz_sum": round(sum(v["umsatz"] for v in team_summary.values())),
        "total_fte": total_fte_all,
    }

# ── YTD Overview ──────────────────────────────────────────────────────────
@app.get("/api/ytd/{year}")
def get_ytd(
    year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from calc import (
        MONTH_NAMES_DE,
        _parse_ma_date,
        compute_soll_tage,
        compute_zeg,
        get_eintritt,
        get_feiertage_sets,
        get_pattern,
        is_employed_in_month,
        reporting_through_month,
        zeg_color,
    )
    from schedule_utils import build_schedule_cache

    through_month = reporting_through_month(year)
    all_mas = db.query(MAStammdaten).all()
    mas = [
        m for m in all_mas
        if any(is_employed_in_month(m.eintritt, m.austritt, year, mo, m.is_active) for mo in range(1, 13))
    ]
    mas = filter_mas_for_user(
        mas, current_user, db,
        year=year,
        months=list(range(1, through_month + 1)) if through_month else None,
    )
    inputs_all = db.query(MonthlyInput).filter(MonthlyInput.year == year).all()

    umsatz_map = {(r.ma_name, r.month): r.umsatz for r in umsatz_all}
    input_map = {(r.ma_name, r.month): r for r in inputs_all}

    from umsatz_agg import monthly_and_year_totals
    monthly_totals, year_total_umsatz = monthly_and_year_totals(
        umsatz_map, mas, year, through_month=through_month,
    )

    feiertage_sets = get_feiertage_sets(year, db=db)
    schedule_cache = build_schedule_cache(
        db, [m.name for m in mas], year, through_month,
    ) if through_month else {}

    results = []
    for ma in mas:
        name = ma.name
        monthly = []
        zeg_b_values = []
        total_umsatz = 0
        eintritt = _parse_ma_date(ma.eintritt)
        if eintritt is None:
            eintritt = get_eintritt(name, year, db=None)
        austritt = _parse_ma_date(ma.austritt)

        for m in range(1, 13):
            if m > through_month:
                monthly.append(None)
                continue
            if not is_employed_in_month(ma.eintritt, ma.austritt, year, m, ma.is_active):
                monthly.append(None)
                continue
            umsatz = umsatz_map.get((name, m), 0) or 0
            inp = input_map.get((name, m))
            sched = schedule_cache.get((name, m), [])
            pat = get_pattern(name, year, m, schedule_entries=sched)
            soll = compute_soll_tage(
                name, year, m,
                pattern=pat,
                feiertage_sets=feiertage_sets,
                eintritt=eintritt,
                austritt=austritt,
            )
            if umsatz == 0 and soll == 0 and not inp:
                monthly.append(None)
                continue
            if umsatz == 0:
                monthly.append({"umsatz": 0, "zeg_b": None, "color": "gray"})
                continue
            total_umsatz += umsatz
            zeg = compute_zeg(
                name, year, m, umsatz,
                ferien_t=inp.ferien_t if inp else 0,
                kurs_h=inp.kurs_h if inp else 0,
                workshop_h=inp.workshop_h if inp else 0,
                marketing_h=inp.marketing_h if inp else 0,
                laufanalyse_h=inp.laufanalyse_h if inp else 0,
                krank_t=inp.krank_t if inp else 0,
                pattern=pat,
                feiertage_sets=feiertage_sets,
                eintritt=eintritt,
                austritt=austritt,
            )
            monthly.append({
                "umsatz": round(umsatz),
                "zeg_b": zeg["zeg_b"],
                "color": zeg_color(zeg["zeg_b"])
            })
            if zeg["zeg_b"]:
                zeg_b_values.append(zeg["zeg_b"])

        avg_zeg_b = round(sum(zeg_b_values) / len(zeg_b_values), 3) if zeg_b_values else None
        results.append({
            "name": name,
            "display_name": ma.display_name,
            "team": ma.team,
            "role": ma.role,
            "bg_pct": ma.bg_pct,
            "monthly": monthly,
            "avg_zeg_b": avg_zeg_b,
            "color": zeg_color(avg_zeg_b),
            "total_umsatz": round(total_umsatz),
        })

    return {
        "year": year,
        "reporting_through_month": through_month,
        "reporting_through_label": (
            f"{MONTH_NAMES_DE[through_month]} {year}" if through_month else None
        ),
        "ma_data": results,
        "monthly_totals": monthly_totals,
        "year_total_umsatz": year_total_umsatz,
    }

# ── Excel Export ──────────────────────────────────────────────────────────
@app.get("/api/export/excel/{year}")
async def export_excel(
    year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_full_access(current_user)
    from excel_export import generate_excel
    path = generate_excel(year, db)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"Kineo_Umsatzanalyse_{year}.xlsx"
    )

# ── Bilat Export ──────────────────────────────────────────────────────────
@app.get("/api/export/bilats/{year}/{period_label}/{month}")
async def export_bilats(
    year: int, period_label: str, month: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_full_access(current_user)
    from bilat_export import generate_bilats_zip
    path = generate_bilats_zip(year, month, db, current_user, period_label=period_label)
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"Kineo_Bilats_{MONTH_NAMES_DE[month]}_{year}.zip"
    )

# ── Health ────────────────────────────────────────────────────────────────
@app.get("/api/export/bilat-single/{year}/{month}/{ma_name}")
async def export_bilat_single(
    year: int, month: int, ma_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from ma_access import TEAM_SCOPE_ROLES, ma_visible_to_user

    if current_user.role in TEAM_SCOPE_ROLES:
        ma = db.query(MAStammdaten).filter_by(name=ma_name).first()
        if not ma or not ma_visible_to_user(ma, current_user, db, year=year, months=list(range(1, month + 1))):
            raise HTTPException(status_code=403, detail="Keine Berechtigung")
    from bilat_export import generate_single_bilat
    path = generate_single_bilat(year, month, ma_name, db)
    safe = ma_name.replace(".", "_").replace(" ", "_")
    return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        filename=f"Bilat_{safe}_HJ1_{year}.docx")




# ── Password Change ───────────────────────────────────────────────────────
class PasswordChange(BaseModel):
    current_password: str
    new_password: str

@app.post("/api/profile/change-password")
def change_password(data: PasswordChange, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from auth import verify_password, hash_password
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Aktuelles Passwort falsch")
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Passwort muss mindestens 8 Zeichen haben")
    current_user.hashed_password = hash_password(data.new_password)
    db.commit()
    return {"message": "Passwort geändert"}

class ProfileUpdate(BaseModel):
    email: Optional[str] = None

@app.get("/api/profile")
def get_profile(current_user: User = Depends(get_current_user)):
    return {
        "username": current_user.username,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "role": current_user.role,
        "team": current_user.team,
    }

@app.patch("/api/profile")
def update_profile(data: ProfileUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if data.email is not None:
        email = data.email.strip().lower() or None
        if email and "@" not in email:
            raise HTTPException(status_code=400, detail="Ungültige E-Mail-Adresse")
        current_user.email = email
        db.commit()
    return {"message": "Profil aktualisiert", "email": current_user.email}

# ── Config / Years ────────────────────────────────────────────────────────
@app.get("/api/years")
def get_years(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from sqlalchemy import distinct
    current = date.today().year
    years = {current, current - 1, current + 1}
    for (y,) in db.query(distinct(UmsatzData.year)).all():
        if y:
            years.add(y)
    for (y,) in db.query(distinct(MonthlyInput.year)).all():
        if y:
            years.add(y)
    for (y,) in db.query(distinct(BilatData.year)).all():
        if y:
            years.add(y)
    return {"current": current, "years": sorted(years, reverse=True)}

@app.get("/api/import-status/{year}")
def get_import_status(
    year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Welche Monate haben CSV-Umsatz / Tätigkeiten — inkl. Zeitstempel."""
    umsatz_agg: dict[int, dict] = {}
    for row in db.query(UmsatzData).filter(UmsatzData.year == year).all():
        m = row.month
        if m not in umsatz_agg:
            umsatz_agg[m] = {"ma_count": 0, "total": 0.0, "uploaded_at": None, "uploaded_by": None}
        umsatz_agg[m]["ma_count"] += 1
        umsatz_agg[m]["total"] += row.umsatz or 0
        if row.uploaded_at and (
            umsatz_agg[m]["uploaded_at"] is None or row.uploaded_at > umsatz_agg[m]["uploaded_at"]
        ):
            umsatz_agg[m]["uploaded_at"] = row.uploaded_at
            umsatz_agg[m]["uploaded_by"] = row.uploaded_by

    input_agg: dict[int, dict] = {}
    for row in db.query(MonthlyInput).filter(MonthlyInput.year == year).all():
        has_activity = any([
            row.ferien_t, row.kurs_h, row.workshop_h, row.marketing_h, row.laufanalyse_h, row.krank_t,
        ])
        if not has_activity:
            continue
        m = row.month
        if m not in input_agg:
            input_agg[m] = {"ma_count": 0, "updated_at": None, "updated_by": None}
        input_agg[m]["ma_count"] += 1
        if row.updated_at and (
            input_agg[m]["updated_at"] is None or row.updated_at > input_agg[m]["updated_at"]
        ):
            input_agg[m]["updated_at"] = row.updated_at
            input_agg[m]["updated_by"] = row.updated_by

    months_out = []
    for m in range(1, 13):
        u = umsatz_agg.get(m, {})
        inp = input_agg.get(m, {})
        uploaded_at = u.get("uploaded_at")
        updated_at = inp.get("updated_at")
        months_out.append({
            "month": m,
            "month_name": MONTH_NAMES_DE[m],
            "umsatz": {
                "imported": bool(u.get("ma_count")),
                "ma_count": u.get("ma_count", 0),
                "total": round(u.get("total", 0), 2),
                "uploaded_at": uploaded_at.isoformat() if uploaded_at else None,
                "uploaded_by": u.get("uploaded_by"),
            },
            "inputs": {
                "saved": bool(inp.get("ma_count")),
                "ma_count": inp.get("ma_count", 0),
                "updated_at": updated_at.isoformat() if updated_at else None,
                "updated_by": inp.get("updated_by"),
            },
        })

    storage = None
    if has_full_access(current_user.role):
        storage = get_storage_info()

    return {"year": year, "months": months_out, "storage": storage}

# ── ZEG-B Trend Alarm ────────────────────────────────────────────────────
@app.post("/api/admin/check-trends")
def check_zeg_trends(
    year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_full_access(current_user)
    year = year or date.today().year
    mas = db.query(MAStammdaten).filter_by(is_active=True).all()
    umsatz_all = {(r.ma_name, r.month): r.umsatz for r in db.query(UmsatzData).filter_by(year=year).all()}
    input_all = {(r.ma_name, r.month): r for r in db.query(MonthlyInput).filter_by(year=year).all()}

    pending = []
    for ma in mas:
        below = []
        zeg_values = []
        for m in range(1, 13):
            u = umsatz_all.get((ma.name, m), 0)
            if u == 0:
                continue
            inp = input_all.get((ma.name, m))
            zeg = compute_zeg(
                ma.name, year, m, u,
                ferien_t=inp.ferien_t if inp else 0,
                kurs_h=inp.kurs_h if inp else 0,
                workshop_h=inp.workshop_h if inp else 0,
                marketing_h=inp.marketing_h if inp else 0,
                laufanalyse_h=inp.laufanalyse_h if inp else 0,
                krank_t=inp.krank_t if inp else 0,
                db=db,
            )
            if zeg["zeg_b"] and zeg["zeg_b"] < 0.85:
                below.append(m)
                zeg_values.append(zeg["zeg_b"])
            else:
                below = []
                zeg_values = []
            if len(below) >= 2:
                pending.append((ma, below, zeg_values))
                break

    alerts = []
    alert_objs = []
    for ma, below, zeg_values in pending:
        msg = f"ZEG-B Alarm: {ma.display_name} — {len(below)} Monate unter 85% (seit {MONTH_NAMES_DE[below[0]]})"
        exists = db.query(Notification).filter_by(type="zeg_alarm", detail=ma.name, is_read=False).first()
        if not exists:
            db.add(Notification(type="zeg_alarm", message=msg, detail=ma.name))
            alerts.append(msg)
        alert_objs.append({
            "name": ma.display_name,
            "months": len(below),
            "avg_zeg": sum(zeg_values) / len(zeg_values) * 100,
        })

    db.commit()
    if alert_objs:
        email_zeg_alarm(alert_objs)
    return {"alerts": alerts, "count": len(alerts), "year": year}

# ── Monthly Reminder Check ────────────────────────────────────────────────
@app.post("/api/admin/check-reminders")
def check_reminders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_full_access(current_user)
    from datetime import date
    today = date.today()
    if today.day < 5:
        return {"message": "Zu früh im Monat"}
    # Check if last month has data
    last_month = today.month - 1 if today.month > 1 else 12
    last_year = today.year if today.month > 1 else today.year - 1
    count = db.query(UmsatzData).filter_by(year=last_year, month=last_month).count()
    if count == 0:
        msg = f"CSV fuer {MONTH_NAMES_DE[last_month]} {last_year} noch nicht hochgeladen!"
        exists = db.query(Notification).filter(
            Notification.type=="csv_reminder",
            Notification.message.contains(str(last_month)),
            Notification.is_read==False
        ).first()
        if not exists:
            db.add(Notification(type="csv_reminder", message=msg, detail=f"{last_year}-{last_month:02d}"))
            db.commit()
            email_csv_reminder(MONTH_NAMES_DE[last_month], last_year)
        return {"reminder": msg}
    return {"message": "CSV vorhanden"}

# ── Bilat Data ────────────────────────────────────────────────────────────
class BilatInput(BaseModel):
    kat_a_self: Optional[int] = None
    kat_a_fk: Optional[int] = None
    kat_a_comment: Optional[str] = None
    kat_b_self: Optional[int] = None
    kat_b_fk: Optional[int] = None
    kat_b_comment: Optional[str] = None
    kat_c_self: Optional[int] = None
    kat_c_fk: Optional[int] = None
    kat_c_comment: Optional[str] = None
    kat_d_self: Optional[int] = None
    kat_d_fk: Optional[int] = None
    kat_d_comment: Optional[str] = None
    vereinbarungen: Optional[str] = None
    themen_ma: Optional[str] = None
    gespraechseindruck: Optional[str] = None
    naechstes_bilat: Optional[str] = None


class BilatSaveRequest(BaseModel):
    data: BilatInput
    flow_action: Optional[str] = None  # submit_fk | submit_self | complete_reveal


def _bilat_response(b: BilatData | None) -> dict:
    from bilat_flow import (
        PHASE_DONE, PHASE_FK_PREP, PHASE_MA_SELF, PHASE_REVEAL,
        compute_deviations, fk_hint, mild_summary,
    )
    if not b:
        return {
            "flow_phase": PHASE_FK_PREP,
            "deviations": {"categories": [], "has_grave": False, "all_mild": False, "ready": False},
            "fk_hints": [],
            "mild_summaries": [],
        }
    phase = b.flow_phase or PHASE_FK_PREP
    payload = {k: getattr(b, k) for k in BilatInput.model_fields}
    payload["flow_phase"] = phase
    if phase in (PHASE_REVEAL, PHASE_DONE):
        dev = compute_deviations(b)
        payload["deviations"] = dev
        payload["fk_hints"] = [fk_hint(c) for c in dev["categories"] if c["grave"]]
        payload["mild_summaries"] = [mild_summary(c) for c in dev["categories"]] if dev["all_mild"] else []
    else:
        payload["deviations"] = {"categories": [], "has_grave": False, "all_mild": False, "ready": False}
        payload["fk_hints"] = []
        payload["mild_summaries"] = []
    return payload


def _apply_bilat_fields(b: BilatData, data: BilatInput, phase: str) -> None:
    from bilat_flow import PHASE_FK_PREP, PHASE_MA_SELF
    dump = data.model_dump()
    if phase == PHASE_FK_PREP:
        allowed = {k for k in dump if k.endswith("_fk") or k.endswith("_comment")}
    elif phase == PHASE_MA_SELF:
        allowed = {k for k in dump if k.endswith("_self") or k == "themen_ma"}
    else:
        allowed = set(dump.keys())
    for k, v in dump.items():
        if k in allowed:
            setattr(b, k, v)

@app.get("/api/bilat-periods")
def get_bilat_periods(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return all existing period_labels for dropdown"""
    from sqlalchemy import distinct
    rows = db.query(distinct(BilatData.period_label)).filter(BilatData.period_label != None).order_by(BilatData.period_label.desc()).all()
    periods = [r[0] for r in rows if r[0]]
    # Add current default if not present
    import datetime as dt
    year = dt.date.today().year
    half = "HJ1" if dt.date.today().month <= 6 else "HJ2"
    default = f"{half} {year}"
    if default not in periods:
        periods.insert(0, default)
    return periods

@app.get("/api/bilat/{ma_name}/{year}/{period_label}")
def get_bilat(ma_name: str, year: int, period_label: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    b = db.query(BilatData).filter_by(ma_name=ma_name, year=year, period_label=period_label).first()
    if not b:
        return _bilat_response(None)
    return _bilat_response(b)

@app.post("/api/bilat/{ma_name}/{year}/{period_label}")
def save_bilat(ma_name: str, year: int, period_label: str, body: BilatSaveRequest,
               db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from bilat_flow import PHASE_FK_PREP, advance_phase
    b = db.query(BilatData).filter_by(ma_name=ma_name, year=year, period_label=period_label).first()
    if not b:
        half = 1 if period_label.upper().startswith("HJ1") else 2
        b = BilatData(ma_name=ma_name, year=year, period_label=period_label, half=half, flow_phase=PHASE_FK_PREP)
        db.add(b)
    phase = b.flow_phase or PHASE_FK_PREP
    _apply_bilat_fields(b, body.data, phase)
    if body.flow_action:
        advance_phase(b, body.flow_action)
    b.updated_at = datetime.utcnow()
    b.updated_by = current_user.username
    db.commit()
    db.refresh(b)
    return _bilat_response(b)

@app.get("/api/bilat-overview/{year}/{period_label}")
def get_bilat_overview(year: int, period_label: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    mas = db.query(MAStammdaten).filter_by(is_active=True).all()
    mas = filter_mas_for_user(mas, current_user, db, year=year, months=months_for_period(period_label))
    bilats = {b.ma_name: b for b in db.query(BilatData).filter_by(year=year, period_label=period_label).all()}
    return [{
        "name": m.name, "display_name": m.display_name, "team": m.team,
        "has_data": m.name in bilats,
        "flow_phase": bilats[m.name].flow_phase if m.name in bilats else "fk_prep",
        "kat_a_fk": bilats[m.name].kat_a_fk if m.name in bilats else None,
        "kat_b_fk": bilats[m.name].kat_b_fk if m.name in bilats else None,
        "kat_c_fk": bilats[m.name].kat_c_fk if m.name in bilats else None,
        "kat_d_fk": bilats[m.name].kat_d_fk if m.name in bilats else None,
    } for m in mas]

# ── Notifications ─────────────────────────────────────────────────────────
@app.get("/api/notifications")
def get_notifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not has_full_access(current_user.role):
        return []
    notifs = db.query(Notification).filter_by(is_read=False).order_by(Notification.created_at.desc()).all()
    return [{"id":n.id,"type":n.type,"message":n.message,"detail":n.detail,
             "created_at":n.created_at.isoformat()} for n in notifs]

@app.patch("/api/notifications/{notif_id}/read")
def mark_read(notif_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    n = db.query(Notification).filter_by(id=notif_id).first()
    if n: n.is_read = True; db.commit()
    return {"message": "Gelesen"}

@app.patch("/api/notifications/read-all")
def mark_all_read(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db.query(Notification).filter_by(is_read=False).update({"is_read": True})
    db.commit()
    return {"message": "Alle gelesen"}

# ── Admin: MA Stammdaten ──────────────────────────────────────────────────
class MACreate(BaseModel):
    name: str
    display_name: str
    team: str
    role: str = "therapeut"
    bg_pct: float = 1.0
    eintritt: Optional[str] = None
    austritt: Optional[str] = None

@app.get("/api/admin/ma")
def admin_get_ma(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_full_access(current_user)
    mas = db.query(MAStammdaten).order_by(MAStammdaten.name).all()
    return [{"id": m.id, "name": m.name, "display_name": m.display_name, "team": m.team,
             "role": m.role, "bg_pct": m.bg_pct, "is_active": m.is_active,
             "eintritt": m.eintritt, "austritt": m.austritt} for m in mas]

@app.post("/api/admin/ma")
def admin_create_ma(data: MACreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_full_access(current_user)
    ma = MAStammdaten(**data.dict())
    db.add(ma); db.commit(); db.refresh(ma)
    return {"id": ma.id, "message": f"{ma.name} erstellt"}

@app.put("/api/admin/ma/{ma_name:path}")
def admin_update_ma(ma_name: str, data: MACreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_full_access(current_user)
    ma = db.query(MAStammdaten).filter_by(name=ma_name).first()
    if not ma: raise HTTPException(status_code=404, detail="MA nicht gefunden")
    for k,v in data.dict().items(): setattr(ma, k, v)
    db.commit()
    return {"message": f"{ma_name} aktualisiert"}

@app.patch("/api/admin/ma/{ma_name:path}/toggle")
def admin_toggle_ma(ma_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_full_access(current_user)
    ma = db.query(MAStammdaten).filter_by(name=ma_name).first()
    if not ma: raise HTTPException(status_code=404, detail="MA nicht gefunden")
    ma.is_active = not ma.is_active
    db.commit()
    return {"message": f"{ma_name} {'aktiviert' if ma.is_active else 'deaktiviert'}", "is_active": ma.is_active}

# ── Admin: Schedule ───────────────────────────────────────────────────────
class ScheduleDay(BaseModel):
    weekday: int
    vm_pct: float = 0.0
    vm_standort: Optional[str] = None
    nm_pct: float = 0.0
    nm_standort: Optional[str] = None

class ScheduleSave(BaseModel):
    valid_from: str  # YYYY-MM (bei scope=from)
    days: List[ScheduleDay]
    scope: str = "from"  # "from" | "month"
    year: Optional[int] = None
    month: Optional[int] = None

@app.get("/api/admin/schedule/{ma_name:path}")
def get_schedule(
    ma_name: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_full_access(current_user)
    from schedule_utils import (
        format_valid_from_label, get_schedule_entries_for_month, list_schedule_versions,
    )

    versions = list_schedule_versions(db, ma_name)
    scope = "from"
    valid_from = f"{date.today().year}-{date.today().month:02d}"

    if year and month:
        entries = get_schedule_entries_for_month(ma_name, year, month, db)
        override = db.query(MAScheduleSet).filter_by(
            ma_name=ma_name, override_year=year, override_month=month,
        ).first()
        scope = "month" if override else "from"
        valid_from = f"{year}-{month:02d}"
        if entries:
            return {
                "days": [{"weekday": e.weekday, "vm_pct": e.vm_pct, "vm_standort": e.vm_standort,
                          "nm_pct": e.nm_pct, "nm_standort": e.nm_standort} for e in entries],
                "valid_from": valid_from,
                "scope": scope,
                "year": year,
                "month": month,
                "versions": versions,
            }

    latest = (
        db.query(MAScheduleSet)
        .filter_by(ma_name=ma_name)
        .filter(MAScheduleSet.override_year.is_(None))
        .order_by(MAScheduleSet.valid_from.desc())
        .first()
    )
    if latest:
        entries = db.query(MAScheduleEntry).filter_by(schedule_set_id=latest.id).order_by(MAScheduleEntry.weekday).all()
        return {
            "days": [{"weekday": e.weekday, "vm_pct": e.vm_pct, "vm_standort": e.vm_standort,
                      "nm_pct": e.nm_pct, "nm_standort": e.nm_standort} for e in entries],
            "valid_from": latest.valid_from[:7],
            "scope": "from",
            "versions": versions,
        }
    # Return defaults from calc.py
    from calc import MA_PATTERNS, day_pct_to_halves
    pat = MA_PATTERNS.get(ma_name, {})
    days = []
    for wd in range(5):
        day_map = {0: "mo", 1: "di", 2: "mi", 3: "do", 4: "fr"}
        vm, nm = day_pct_to_halves(pat.get(day_map[wd], 0) or 0)
        days.append({"weekday": wd, "vm_pct": vm, "vm_standort": None, "nm_pct": nm, "nm_standort": None})
    return {"days": days, "valid_from": valid_from, "scope": "from", "versions": versions}

@app.post("/api/admin/schedule/{ma_name:path}")
def save_schedule(ma_name: str, payload: ScheduleSave, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_full_access(current_user)
    from schedule_utils import (
        create_month_schedule_override, create_schedule_set,
        format_valid_from_label, normalize_valid_from,
    )
    days = [d.dict() for d in payload.days]

    if payload.scope == "month":
        if not payload.year or not payload.month:
            raise HTTPException(status_code=400, detail="Jahr und Monat erforderlich für Monats-Override")
        create_month_schedule_override(db, ma_name, payload.year, payload.month, days)
        db.commit()
        from calc import MONTH_NAMES_DE
        label = f"{MONTH_NAMES_DE[payload.month]} {payload.year}"
        return {"message": f"Monats-Arbeitsplan gespeichert — gilt nur für {label}"}

    try:
        valid_from = normalize_valid_from(payload.valid_from)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    create_schedule_set(db, ma_name, valid_from, days)
    db.commit()
    label = format_valid_from_label(valid_from)
    return {"message": f"Arbeitstag-Muster gespeichert — gilt ab {label}"}

# ── Admin: Feiertage ──────────────────────────────────────────────────────
class FeiertageEntry(BaseModel):
    date_str: str
    name: str
    faktor: float = 1.0

@app.get("/api/admin/feiertage/{year}")
def get_feiertage(year: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_full_access(current_user)
    entries = db.query(Feiertag).filter_by(year=year).order_by(Feiertag.date_str).all()
    if not entries:
        # Return defaults from calc.py
        from calc import default_feiertage_entries
        return default_feiertage_entries(year)
    return [{"id":e.id,"date_str":e.date_str,"name":e.name,"faktor":e.faktor} for e in entries]

@app.post("/api/admin/feiertage/{year}")
def save_feiertage(year: int, data: List[FeiertageEntry], db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_full_access(current_user)
    db.query(Feiertag).filter_by(year=year).delete()
    for f in data:
        db.add(Feiertag(year=year, **f.model_dump()))
    db.commit()
    return {"message": f"{len(data)} Feiertage für {year} gespeichert"}

@app.delete("/api/admin/feiertage/{year}/{date_str}")
def delete_feiertag(year: int, date_str: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_full_access(current_user)
    db.query(Feiertag).filter_by(year=year, date_str=date_str).delete()
    db.commit()
    return {"message": "Gelöscht"}

@app.get("/api/health")
def health():
    storage = get_storage_info()
    return {
        "status": "ok",
        "app": "Kineo Umsatzanalyse",
        "version": "1.0.0",
        "storage": storage,
    }
