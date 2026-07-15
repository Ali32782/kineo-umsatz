from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
from typing import Optional, List
from jose import JWTError, jwt
from pydantic import BaseModel
import os, io, json
from urllib.parse import quote

from database import get_db, init_db, get_storage_info, User, UmsatzData, MonthlyInput, MAStammdaten, MAScheduleEntry, MAScheduleSet, Feiertag, Notification, BilatData, QualGoal, MaDocument, QualSignature, MitgliederData
from calc import (
    compute_zeg, compute_soll_tage, parse_csv_umsatz, parse_csv_umsatz_result,
    parse_csv_pivot_all_months_result,
    zeg_color, MONTH_NAMES_DE, MA_PATTERNS,
    is_employed_in_month,
)
from email_service import email_zeg_alarm, email_csv_reminder
from auth import has_full_access, needs_rehash, hash_password
from ma_access import (
    filter_mas_for_user,
    months_for_period,
    CC_KPI_TYPE,
    cc_kpi_label,
    is_zeg_overview_excluded,
)
from rate_limit import client_ip, rate_limit

def _require_full_access(user: User) -> None:
    if not has_full_access(user.role):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

# ── Config ────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", "kineo-secret-2026-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours
APP_BASE_URL = os.environ.get("APP_BASE_URL", "https://kineo-leadership.onrender.com").rstrip("/")
CRON_SECRET = os.environ.get("CRON_SECRET", "").strip()
_cors_extra = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
CORS_ORIGINS = list(dict.fromkeys([
    APP_BASE_URL,
    "https://kineo-leadership.onrender.com",
    "https://kineo-umsatz.onrender.com",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://localhost:3000",
    *_cors_extra,
]))

app = FastAPI(title="Kineo Umsatzanalyse", version="1.0.3")

# WICHTIG: allow_credentials=False — sonst blockiert der Browser bei ACAO "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Length"],
)


@app.middleware("http")
async def cors_fix_headers(request: Request, call_next):
    """Erzwingt CORS ohne credentials — unabhängig von Starlette/Cloudflare-Eigenheiten."""
    response = await call_next(request)
    origin = request.headers.get("origin")
    # Credentials-Header darf nicht zusammen mit * stehen
    if "access-control-allow-credentials" in response.headers:
        del response.headers["access-control-allow-credentials"]
    response.headers["access-control-allow-origin"] = origin or "*"
    if origin:
        vary = response.headers.get("vary", "")
        if "Origin" not in vary:
            response.headers["vary"] = f"{vary}, Origin".strip(", ")
    response.headers.setdefault(
        "access-control-expose-headers",
        "Content-Disposition, Content-Length",
    )
    return response


def _download_response(path: str, *, media_type: str, filename: str) -> Response:
    """Bytes-Response statt FileResponse — CORS-Header bleiben korrekt (kein ACAO *)."""
    with open(path, "rb") as f:
        data = f.read()
    try:
        os.remove(path)
    except OSError:
        pass
    # RFC 5987 für Umlaute in Dateinamen
    safe_ascii = filename.encode("ascii", "ignore").decode("ascii") or "download.bin"
    disp = f"attachment; filename=\"{safe_ascii}\"; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Disposition": disp,
            "Content-Length": str(len(data)),
            "Cache-Control": "no-store",
        },
    )

# Init DB on startup
@app.on_event("startup")
def startup():
    init_db()
    from database import ensure_bilat_ef_columns
    ensure_bilat_ef_columns()

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

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
_http_bearer = HTTPBearer(auto_error=False)


def _user_from_jwt(token: str, db: Session) -> User:
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


async def get_current_user(
    db: Session = Depends(get_db),
    bearer: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    if not bearer or not bearer.credentials:
        raise HTTPException(status_code=401, detail="Ungültige Anmeldedaten")
    return _user_from_jwt(bearer.credentials, db)


async def get_current_user_download(
    request: Request,
    db: Session = Depends(get_db),
    bearer: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
):
    """Auth via Header oder ?token= — für Downloads per Browser-Navigation (kein CORS)."""
    raw = bearer.credentials if bearer and bearer.credentials else request.query_params.get("token")
    if not raw:
        raise HTTPException(status_code=401, detail="Ungültige Anmeldedaten")
    return _user_from_jwt(raw, db)

@app.post("/api/login", response_model=Token)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    rate_limit(f"login:{client_ip(request)}", limit=20, window_seconds=300)
    rate_limit(f"login-user:{(req.username or '').lower()}", limit=10, window_seconds=300)
    user = db.query(User).filter(User.username == req.username).first()
    from auth import verify_password
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Falscher Benutzername oder Passwort")
    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(req.password)
        db.commit()
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
def forgot_password(req: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Reset-Link per E-Mail — antwortet immer gleich (kein User-Enumeration)."""
    import secrets
    from email_service import email_password_reset

    rate_limit(f"forgot:{client_ip(request)}", limit=8, window_seconds=600)
    ident = req.identifier.strip().lower()
    rate_limit(f"forgot-id:{ident}", limit=5, window_seconds=600)
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


# ── Mitgliederzahlen (CC / Ilaria) ─────────────────────────────────────────
class MitgliederItem(BaseModel):
    ma_name: str
    year: int
    month: int
    count: float
    notes: Optional[str] = None


@app.get("/api/mitglieder/{year}")
def get_mitglieder_year(
    year: int,
    month: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from mitglieder import list_mitglieder, mitglieder_as_dict
    rows = list_mitglieder(db, year, month)
    allowed = {
        m.name
        for m in filter_mas_for_user(db.query(MAStammdaten).all(), current_user, db, year=year, months=[month] if month else None)
    }
    return {
        "year": year,
        "month": month,
        "items": [mitglieder_as_dict(r) for r in rows if r.ma_name in allowed],
    }


@app.post("/api/mitglieder")
def save_mitglieder(
    items: List[MitgliederItem],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_full_access(current_user)
    from mitglieder import upsert_mitglieder, mitglieder_as_dict
    saved = []
    for it in items:
        if it.month < 1 or it.month > 12:
            raise HTTPException(status_code=400, detail=f"Ungültiger Monat: {it.month}")
        row = upsert_mitglieder(
            db,
            ma_name=it.ma_name,
            year=it.year,
            month=it.month,
            count=it.count,
            notes=it.notes,
            updated_by=current_user.username,
        )
        saved.append(mitglieder_as_dict(row))
    return {"message": f"{len(saved)} Mitgliederzahlen gespeichert", "items": saved}


@app.post("/api/mitglieder/upload-csv")
async def upload_mitglieder_csv(
    file: UploadFile = File(...),
    year: int = Form(...),
    ma_name: str = Form("Ilaria.F"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_full_access(current_user)
    from mitglieder import parse_mitglieder_csv, upsert_mitglieder, mitglieder_as_dict
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except Exception:
        text = content.decode("latin-1")
    parsed = parse_mitglieder_csv(text)
    if not parsed:
        raise HTTPException(status_code=400, detail="Keine gültigen Zeilen (ma_name,month,count)")
    saved = []
    for p in parsed:
        name = p.get("ma_name") or ma_name
        row = upsert_mitglieder(
            db,
            ma_name=name,
            year=year,
            month=p["month"],
            count=p["count"],
            notes=p.get("notes"),
            updated_by=current_user.username,
        )
        saved.append(mitglieder_as_dict(row))
    return {"message": f"{len(saved)} Monate importiert", "items": saved}


@app.post("/api/mitglieder/upload-excel")
async def upload_mitglieder_excel(
    file: UploadFile = File(...),
    ma_name: str = Form("Ilaria.F"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fitness-Abo Excel (KW → Monat, letzter KW-Wert) für Ilaria / CC."""
    _require_full_access(current_user)
    from fitness_abo_import import parse_fitness_abo_excel
    from mitglieder import upsert_mitglieder, mitglieder_as_dict

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Leere Datei")
    try:
        parsed = parse_fitness_abo_excel(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel konnte nicht gelesen werden: {e}") from e
    if not parsed:
        raise HTTPException(status_code=400, detail="Keine Mitglieder-Gesamt-Werte in der Excel gefunden")

    saved = []
    years = sorted({p["year"] for p in parsed})
    for p in parsed:
        row = upsert_mitglieder(
            db,
            ma_name=ma_name,
            year=p["year"],
            month=p["month"],
            count=p["count"],
            notes="Fitness-Abo Excel",
            updated_by=current_user.username,
        )
        saved.append(mitglieder_as_dict(row))
    return {
        "message": f"{len(saved)} Monate für {ma_name} importiert ({', '.join(str(y) for y in years)})",
        "items": saved,
        "years": years,
    }


@app.post("/api/upload-runnerslab")
async def upload_runnerslab(
    file: UploadFile = File(...),
    ma_name: str = Form("Marc.W"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Runnerslab/Shop-Excel → Selbstzahler Shop (+ optional UmsatzData Marc)."""
    _require_full_access(current_user)
    from runnerslab_import import parse_runnerslab_excel
    from selbstzahler import upsert_selbstzahler_umsatz

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Leere Datei")
    try:
        parsed = parse_runnerslab_excel(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel konnte nicht gelesen werden: {e}") from e
    if not parsed:
        raise HTTPException(status_code=400, detail="Keine Total-Umsätze in der Excel gefunden")

    ma = db.query(MAStammdaten).filter_by(name=ma_name).first()
    if not ma:
        raise HTTPException(status_code=400, detail=f"MA {ma_name} nicht in Stammdaten")

    saved = []
    for p in parsed:
        upsert_selbstzahler_umsatz(
            db,
            unit="shop",
            year=p["year"],
            month=p["month"],
            umsatz=p["umsatz"],
            updated_by=current_user.username,
            notes="Shop / Runnerslab Excel",
        )
        # Legacy: auch unter Marc.W für Bilat/CC-Anzeige
        row = (
            db.query(UmsatzData)
            .filter_by(ma_name=ma_name, year=p["year"], month=p["month"])
            .first()
        )
        if row:
            row.umsatz = p["umsatz"]
            row.uploaded_by = current_user.username
            row.uploaded_at = datetime.utcnow()
        else:
            row = UmsatzData(
                ma_name=ma_name,
                year=p["year"],
                month=p["month"],
                umsatz=p["umsatz"],
                uploaded_by=current_user.username,
            )
            db.add(row)
        saved.append({"ma_name": ma_name, "unit": "shop", "year": p["year"], "month": p["month"], "umsatz": p["umsatz"]})
    db.commit()
    years = sorted({p["year"] for p in parsed})
    return {
        "message": f"{len(saved)} Monate Shop-Umsatz (Marc) importiert ({', '.join(str(y) for y in years)})",
        "items": saved,
        "years": years,
        "total": round(sum(p["umsatz"] for p in parsed), 2),
    }


@app.post("/api/upload-hyrox")
async def upload_hyrox(
    file: UploadFile = File(...),
    ma_name: str = Form("Nina.S"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Training-Club Rechnungen → Selbstzahler HYROX (Stunde Hyrox, bezahlt)."""
    _require_full_access(current_user)
    from hyrox_import import parse_hyrox_invoices_excel
    from selbstzahler import upsert_selbstzahler_umsatz

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Leere Datei")
    try:
        parsed = parse_hyrox_invoices_excel(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel konnte nicht gelesen werden: {e}") from e
    if not parsed:
        raise HTTPException(status_code=400, detail="Keine bezahlten HYROX-Rechnungen gefunden")

    ma = db.query(MAStammdaten).filter_by(name=ma_name).first()
    if not ma:
        raise HTTPException(status_code=400, detail=f"MA {ma_name} nicht in Stammdaten")

    saved = []
    for p in parsed:
        upsert_selbstzahler_umsatz(
            db,
            unit="hyrox",
            year=p["year"],
            month=p["month"],
            umsatz=p["umsatz"],
            updated_by=current_user.username,
            notes=f"HYROX Rechnungen ({p.get('count', 0)}×)",
        )
        row = (
            db.query(UmsatzData)
            .filter_by(ma_name=ma_name, year=p["year"], month=p["month"])
            .first()
        )
        if row:
            row.umsatz = p["umsatz"]
            row.uploaded_by = current_user.username
            row.uploaded_at = datetime.utcnow()
        else:
            row = UmsatzData(
                ma_name=ma_name,
                year=p["year"],
                month=p["month"],
                umsatz=p["umsatz"],
                uploaded_by=current_user.username,
            )
            db.add(row)
        saved.append({
            "ma_name": ma_name,
            "unit": "hyrox",
            "year": p["year"],
            "month": p["month"],
            "umsatz": p["umsatz"],
            "count": p.get("count"),
        })
    db.commit()
    years = sorted({p["year"] for p in parsed})
    return {
        "message": (
            f"{len(saved)} Monate HYROX-Umsatz (Nina) importiert "
            f"({', '.join(str(y) for y in years)}) — Total CHF {round(sum(p['umsatz'] for p in parsed), 2):,.2f}"
        ).replace(",", "'"),
        "items": saved,
        "years": years,
        "total": round(sum(p["umsatz"] for p in parsed), 2),
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
                    "bd_h": row.bd_h or 0,
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
    bd_h: float = 0
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
    allowed = {
        m.name
        for m in filter_mas_for_user(
            db.query(MAStammdaten).all(),
            current_user,
            db,
            year=year,
            months=[month],
        )
    }
    return {i.ma_name: {
        "ferien_t": i.ferien_t, "kurs_h": i.kurs_h, "workshop_h": i.workshop_h,
        "marketing_h": i.marketing_h, "laufanalyse_h": i.laufanalyse_h,
        "bd_h": i.bd_h or 0,
        "krank_t": i.krank_t, "notes": i.notes
    } for i in inputs if i.ma_name in allowed}

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
            for field in ["ferien_t","kurs_h","workshop_h","marketing_h","laufanalyse_h","bd_h","krank_t","notes"]:
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
            bd_h=(inp.bd_h if inp else 0) or 0,
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

    # Build multi-standort ma_data entries (ZEG-B + Umsatz pro Standort)
    from standort_calc import expand_ma_standort_rows, aggregate_team_summary, revenue_fte_total

    ma_data_expanded = []
    for r in results:
        schedule = schedule_map.get(r["name"])
        ma_bg = r.get("bg_pct") or next((m.bg_pct for m in mas if m.name == r["name"]), 1.0)
        ma_data_expanded.extend(expand_ma_standort_rows(r, ma_bg, r["team"], schedule))

    # FTE/Mitarbeiter-Karten: nur Umsatz-Standorte (ohne Management & CC)
    team_summary = aggregate_team_summary(ma_data_expanded, revenue_only=True)
    total_fte_all = revenue_fte_total(ma_data_expanded)
    from umsatz_agg import sum_umsatz_for_month
    umsatz_map_all = {(r.ma_name, r.month): r.umsatz for r in umsatz_rows}
    total_umsatz = round(sum_umsatz_for_month(umsatz_map_all, mas, month))

    # Anzeige-Daten: Management/CC-Zeilen nicht in den Standort-Karten
    ma_data_revenue = [
        r for r in ma_data_expanded
        if r.get("counts_for_fte") is not False
        and r.get("team") in team_summary
    ]

    # Selbstzahler: Shop / Fitness / HYROX / Performance Lab
    from selbstzahler import dashboard_units
    selbstzahler = dashboard_units(db, year, month)

    return {
        "year": year,
        "month": month,
        "month_name": MONTH_NAMES_DE[month],
        "ma_data": ma_data_revenue,
        "team_summary": team_summary,
        "total_umsatz": total_umsatz,
        "team_umsatz_sum": round(sum(v["umsatz"] for v in team_summary.values())),
        "total_fte": total_fte_all,
        "selbstzahler": selbstzahler,
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
    from schedule_utils import build_schedule_cache, collect_ma_standorte_for_year
    from ma_access import list_assignable_fk_users, resolve_ma_fk_user, build_team_fk_index

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
    # ZEG-B-Jahresübersicht: ohne CC-Team
    mas = [m for m in mas if not is_zeg_overview_excluded(m.name, m.team)]
    fk_names = {m.fk_username for m in mas if m.fk_username}
    fk_users = {}
    if fk_names:
        fk_users = {
            u.username: u
            for u in db.query(User).filter(User.username.in_(fk_names)).all()
        }
    team_fk_by_team = build_team_fk_index(db)
    fk_filter_options = list_assignable_fk_users(db)
    umsatz_all = db.query(UmsatzData).filter(UmsatzData.year == year).all()
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
            ferien_t = inp.ferien_t if inp else 0
            krank_t = inp.krank_t if inp else 0
            if umsatz == 0 and soll == 0 and not inp:
                monthly.append(None)
                continue
            if umsatz == 0:
                monthly.append({
                    "umsatz": 0,
                    "zeg_b": None,
                    "color": "gray",
                    "soll_tage": round(soll, 2),
                    "prod_b": None,
                    "ferien_t": ferien_t,
                    "krank_t": krank_t,
                })
                continue
            total_umsatz += umsatz
            zeg = compute_zeg(
                name, year, m, umsatz,
                ferien_t=ferien_t,
                kurs_h=inp.kurs_h if inp else 0,
                workshop_h=inp.workshop_h if inp else 0,
                marketing_h=inp.marketing_h if inp else 0,
                laufanalyse_h=inp.laufanalyse_h if inp else 0,
                bd_h=(inp.bd_h if inp else 0) or 0,
                krank_t=krank_t,
                pattern=pat,
                feiertage_sets=feiertage_sets,
                eintritt=eintritt,
                austritt=austritt,
            )
            monthly.append({
                "umsatz": round(umsatz),
                "zeg_b": zeg["zeg_b"],
                "color": zeg_color(zeg["zeg_b"]),
                "soll_tage": zeg["soll_tage"],
                "prod_b": zeg["prod_b"],
                "ferien_t": ferien_t,
                "krank_t": krank_t,
            })
            if zeg["zeg_b"]:
                zeg_b_values.append(zeg["zeg_b"])

        avg_zeg_b = round(sum(zeg_b_values) / len(zeg_b_values), 3) if zeg_b_values else None
        fk = resolve_ma_fk_user(
            ma, db, fk_users_by_name=fk_users, team_fk_by_team=team_fk_by_team,
        )
        standorte = collect_ma_standorte_for_year(
            name, schedule_cache, through_month, ma.team,
            db=db, year=year,
        ) if through_month else []
        results.append({
            "name": name,
            "display_name": ma.display_name,
            "team": ma.team,
            "standorte": standorte,
            "role": ma.role,
            "bg_pct": ma.bg_pct,
            "is_active": ma.is_active,
            "austritt": ma.austritt,
            "fk_username": fk.username if fk else None,
            "fk_display_name": (fk.full_name or fk.username) if fk else None,
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
        "fk_filter_options": fk_filter_options,
    }

# ── Excel Export ──────────────────────────────────────────────────────────
@app.get("/api/export/excel/{year}")
async def export_excel(
    year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_download)
):
    _require_full_access(current_user)
    from excel_export import generate_excel
    try:
        path = generate_excel(year, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Excel-Export fehlgeschlagen: {e}") from e
    return _download_response(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"Kineo_Umsatzanalyse_{year}.xlsx",
    )

# ── Bilat Export ──────────────────────────────────────────────────────────
@app.get("/api/export/bilats/{year}/{period_label}/{month}")
async def export_bilats(
    year: int, period_label: str, month: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_download)
):
    _require_full_access(current_user)
    from bilat_export import generate_bilats_zip
    try:
        path = generate_bilats_zip(year, month, db, current_user, period_label=period_label)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ZIP-Export fehlgeschlagen: {e}") from e
    return _download_response(
        path,
        media_type="application/zip",
        filename=f"Kineo_Bilats_{MONTH_NAMES_DE[month]}_{year}.zip",
    )


@app.get("/api/export/bilat-single/{year}/{month}/{ma_name}")
async def export_bilat_single(
    year: int, month: int, ma_name: str,
    period_label: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_download)
):
    from bilat_hj1_export import canonical_period_label
    from ma_access import TEAM_SCOPE_ROLES, ma_visible_to_user

    period = canonical_period_label(period_label, year, month)
    ma = db.query(MAStammdaten).filter_by(name=ma_name).first()
    if not ma:
        raise HTTPException(status_code=404, detail="MA nicht gefunden")
    if current_user.role in TEAM_SCOPE_ROLES:
        if not ma_visible_to_user(ma, current_user, db, year=year, months=list(range(1, month + 1))):
            raise HTTPException(status_code=403, detail="Keine Berechtigung")
    elif not has_full_access(current_user.role):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    from bilat_export import generate_single_bilat
    try:
        path = generate_single_bilat(year, month, ma_name, db, period_label=period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Keine Word-Vorlage: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Word-Export fehlgeschlagen: {e}") from e

    safe = ma_name.replace(".", "_").replace(" ", "_")
    half = "HJ1" if period.upper().startswith("HJ1") else "HJ2"
    return _download_response(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"Bilat_{safe}_{half}_{year}.docx",
    )




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
            row.ferien_t, row.kurs_h, row.workshop_h, row.marketing_h, row.laufanalyse_h, row.bd_h, row.krank_t,
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
                bd_h=(inp.bd_h if inp else 0) or 0,
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
def _run_csv_reminder_check(db: Session) -> dict:
    today = date.today()
    if today.day < 5:
        return {"message": "Zu früh im Monat"}
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


@app.post("/api/admin/check-reminders")
def check_reminders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_full_access(current_user)
    return _run_csv_reminder_check(db)


@app.post("/api/cron/check-reminders")
def cron_check_reminders(request: Request, db: Session = Depends(get_db)):
    """Render Cron Job — Header X-Cron-Secret muss zu CRON_SECRET passen."""
    if not CRON_SECRET:
        raise HTTPException(status_code=503, detail="CRON_SECRET nicht konfiguriert")
    provided = (request.headers.get("x-cron-secret") or "").strip()
    if not provided or provided != CRON_SECRET:
        raise HTTPException(status_code=401, detail="Ungültiger Cron-Secret")
    return _run_csv_reminder_check(db)

# ── Bilat Data ────────────────────────────────────────────────────────────
class BilatInput(BaseModel):
    kat_a_self: Optional[int] = None
    kat_a_fk: Optional[int] = None
    kat_a_comment: Optional[str] = None
    kat_a_talk_notes: Optional[str] = None
    kat_b_self: Optional[int] = None
    kat_b_fk: Optional[int] = None
    kat_b_comment: Optional[str] = None
    kat_b_talk_notes: Optional[str] = None
    kat_c_self: Optional[int] = None
    kat_c_fk: Optional[int] = None
    kat_c_comment: Optional[str] = None
    kat_c_talk_notes: Optional[str] = None
    kat_d_self: Optional[int] = None
    kat_d_fk: Optional[int] = None
    kat_d_comment: Optional[str] = None
    kat_d_talk_notes: Optional[str] = None
    kat_e_self: Optional[int] = None
    kat_e_fk: Optional[int] = None
    kat_e_comment: Optional[str] = None
    kat_e_talk_notes: Optional[str] = None
    kat_f_self: Optional[int] = None
    kat_f_fk: Optional[int] = None
    kat_f_comment: Optional[str] = None
    kat_f_talk_notes: Optional[str] = None
    vereinbarungen: Optional[str] = None
    vereinbarungen_items: Optional[List[dict]] = None
    themen_ma: Optional[str] = None
    gespraechsnotiz: Optional[str] = None
    gespraechseindruck: Optional[str] = None
    naechstes_bilat: Optional[str] = None


class BilatSaveRequest(BaseModel):
    data: BilatInput
    flow_action: Optional[str] = None  # submit_* | complete_reveal | reopen_* | rewind


def _bilat_response(b: BilatData | None) -> dict:
    from bilat_flow import (
        PHASE_DONE, PHASE_FK_PREP, PHASE_MA_SELF, PHASE_REVEAL,
        compute_deviations, fk_hint, mild_summary, parse_vereinbarungen,
    )
    if not b:
        return {
            "flow_phase": PHASE_FK_PREP,
            "deviations": {"categories": [], "has_grave": False, "all_mild": False, "ready": False},
            "fk_hints": [],
            "mild_summaries": [],
            "agenda": [],
            "vereinbarungen_items": [{"what": "", "who": "", "until": ""}],
        }
    phase = b.flow_phase or PHASE_FK_PREP
    payload = {
        k: getattr(b, k)
        for k in BilatInput.model_fields
        if k != "vereinbarungen_items" and hasattr(b, k)
    }
    payload["flow_phase"] = phase
    payload["vereinbarungen_items"] = parse_vereinbarungen(b.vereinbarungen)
    # Während MA-Selbsteinschätzung keine FK-Werte an den Client leaken
    if phase == PHASE_MA_SELF:
        for k in ("a", "b", "c", "d", "e", "f"):
            payload[f"kat_{k}_fk"] = None
            payload[f"kat_{k}_comment"] = None
            payload[f"kat_{k}_talk_notes"] = None
        payload["gespraechsnotiz"] = None
        payload["deviations"] = {"categories": [], "has_grave": False, "all_mild": False, "ready": False}
        payload["agenda"] = []
        payload["fk_hints"] = []
        payload["mild_summaries"] = []
        return payload
    if phase in (PHASE_REVEAL, PHASE_DONE):
        dev = compute_deviations(b)
        payload["deviations"] = dev
        payload["agenda"] = dev["categories"]
        payload["fk_hints"] = [fk_hint(c) for c in dev["categories"] if c["grave"]]
        payload["mild_summaries"] = [mild_summary(c) for c in dev["categories"]] if dev["all_mild"] else []
    else:
        payload["deviations"] = {"categories": [], "has_grave": False, "all_mild": False, "ready": False}
        payload["agenda"] = []
        payload["fk_hints"] = []
        payload["mild_summaries"] = []
    return payload


def _clamp_rating(v):
    if v is None:
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    if n < 1 or n > 5:
        return None
    return n


def _apply_bilat_fields(b: BilatData, data: BilatInput, phase: str) -> None:
    from bilat_flow import PHASE_FK_PREP, PHASE_MA_SELF, format_vereinbarungen
    dump = data.model_dump(exclude_unset=False)
    items = dump.pop("vereinbarungen_items", None)
    if items is not None:
        # Explizit leeren erlauben (kein Fallback auf alten Text)
        dump["vereinbarungen"] = format_vereinbarungen(items)
    if phase == PHASE_FK_PREP:
        allowed = {
            k for k in dump
            if k.endswith("_fk") or k.endswith("_comment") or k == "gespraechsnotiz"
        }
    elif phase == PHASE_MA_SELF:
        allowed = {k for k in dump if k.endswith("_self") or k == "themen_ma"}
    else:
        # reveal / done: alles inkl. Gesprächsnotizen & Abschluss
        allowed = {k for k in dump if k != "vereinbarungen_items"}
    for k, v in dump.items():
        if k not in allowed:
            continue
        # Nur echte Tabellen-Spalten setzen (nach Migration E/F)
        if not hasattr(b, k) or k not in BilatData.__table__.columns:
            continue
        if k.endswith("_self") or k.endswith("_fk"):
            v = _clamp_rating(v)
        setattr(b, k, v)

@app.get("/api/bilat-periods")
def get_bilat_periods(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return all existing period_labels for dropdown"""
    from sqlalchemy import distinct
    rows = db.query(distinct(BilatData.period_label)).filter(BilatData.period_label != None).order_by(BilatData.period_label.desc()).all()
    periods = [r[0] for r in rows if r[0]]
    # Add current default if not present
    import datetime as dt
    from bilat_hj1_export import period_for_calendar
    today = dt.date.today()
    default = period_for_calendar(today.year, today.month)
    if default not in periods:
        periods.insert(0, default)
    return periods

@app.get("/api/bilat/{ma_name}/{year}/{period_label}")
def get_bilat(ma_name: str, year: int, period_label: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from bilat_hj1_export import canonical_period_label
    from ma_access import TEAM_SCOPE_ROLES, ma_visible_to_user
    from database import ensure_bilat_ef_columns
    ensure_bilat_ef_columns()
    ma = db.query(MAStammdaten).filter_by(name=ma_name).first()
    if not ma:
        raise HTTPException(status_code=404, detail="MA nicht gefunden")
    period = canonical_period_label(period_label, year)
    if current_user.role in TEAM_SCOPE_ROLES:
        if not ma_visible_to_user(ma, current_user, db, year=year, months=months_for_period(period)):
            raise HTTPException(status_code=403, detail="Keine Berechtigung")
    elif not has_full_access(current_user.role):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    b = db.query(BilatData).filter_by(ma_name=ma_name, year=year, period_label=period).first()
    if not b:
        return _bilat_response(None)
    return _bilat_response(b)


@app.get("/api/bilat/{ma_name}/{year}/{period_label}/faktenblatt")
def get_bilat_faktenblatt(
    ma_name: str, year: int, period_label: str,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """FK-internes Faktenblatt (Performance, Qualiziele, Leitfaden) — auch ohne Word."""
    from calc import reporting_through_month
    from bilat_hj1_export import build_faktenblatt, canonical_period_label
    from ma_access import TEAM_SCOPE_ROLES, ma_visible_to_user

    ma = db.query(MAStammdaten).filter_by(name=ma_name).first()
    if not ma:
        raise HTTPException(status_code=404, detail="MA nicht gefunden")
    period = canonical_period_label(period_label, year)
    period_months = months_for_period(period)
    if current_user.role in TEAM_SCOPE_ROLES:
        if not ma_visible_to_user(ma, current_user, db, year=year, months=period_months):
            raise HTTPException(status_code=403, detail="Keine Berechtigung")
    elif not has_full_access(current_user.role):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    through_report = reporting_through_month(year)
    through_month = min(max(period_months), through_report) if through_report else max(period_months)
    if through_month <= 0:
        raise HTTPException(status_code=400, detail="Keine abgeschlossenen Monate für diese Periode")

    umsatz_rows = db.query(UmsatzData).filter(
        UmsatzData.ma_name == ma_name, UmsatzData.year == year,
    ).all()
    umsatz_all = {(r.ma_name, r.month): r.umsatz for r in umsatz_rows}
    input_rows = db.query(MonthlyInput).filter(
        MonthlyInput.ma_name == ma_name, MonthlyInput.year == year,
    ).all()
    inputs_all = {(r.ma_name, r.month): r for r in input_rows}
    bilat = db.query(BilatData).filter_by(ma_name=ma_name, year=year, period_label=period).first()
    return build_faktenblatt(
        ma, year, through_month, umsatz_all, inputs_all, bilat, db,
        period_label=period,
    )

@app.post("/api/bilat/{ma_name}/{year}/{period_label}")
def save_bilat(ma_name: str, year: int, period_label: str, body: BilatSaveRequest,
               db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from bilat_flow import PHASE_FK_PREP, advance_phase
    from bilat_hj1_export import canonical_period_label
    from ma_access import TEAM_SCOPE_ROLES, ma_visible_to_user
    from database import ensure_bilat_ef_columns
    from sqlalchemy.exc import ProgrammingError, OperationalError

    ensure_bilat_ef_columns()

    ma = db.query(MAStammdaten).filter_by(name=ma_name).first()
    if not ma:
        raise HTTPException(status_code=404, detail="MA nicht gefunden")
    period = canonical_period_label(period_label, year)
    if current_user.role in TEAM_SCOPE_ROLES:
        if not ma_visible_to_user(ma, current_user, db, year=year, months=months_for_period(period)):
            raise HTTPException(status_code=403, detail="Keine Berechtigung")
    elif not has_full_access(current_user.role):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    b = db.query(BilatData).filter_by(ma_name=ma_name, year=year, period_label=period).first()
    if not b:
        half = 1 if period.upper().startswith("HJ1") else 2
        b = BilatData(ma_name=ma_name, year=year, period_label=period, half=half, flow_phase=PHASE_FK_PREP)
        db.add(b)
    phase = b.flow_phase or PHASE_FK_PREP
    _apply_bilat_fields(b, body.data, phase)
    if body.flow_action:
        try:
            advance_phase(b, body.flow_action)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    b.updated_at = datetime.utcnow()
    b.updated_by = current_user.username
    try:
        db.commit()
    except (ProgrammingError, OperationalError) as e:
        db.rollback()
        ensure_bilat_ef_columns()
        # Nach Schema-Update: Felder erneut anwenden und committen
        b2 = db.query(BilatData).filter_by(ma_name=ma_name, year=year, period_label=period).first()
        if not b2:
            half = 1 if period.upper().startswith("HJ1") else 2
            b2 = BilatData(ma_name=ma_name, year=year, period_label=period, half=half, flow_phase=PHASE_FK_PREP)
            db.add(b2)
            db.flush()
        _apply_bilat_fields(b2, body.data, b2.flow_phase or PHASE_FK_PREP)
        if body.flow_action:
            try:
                advance_phase(b2, body.flow_action)
            except ValueError as ve:
                raise HTTPException(status_code=400, detail=str(ve)) from ve
        b2.updated_at = datetime.utcnow()
        b2.updated_by = current_user.username
        try:
            db.commit()
            db.refresh(b2)
            return _bilat_response(b2)
        except Exception as e2:
            db.rollback()
            raise HTTPException(
                status_code=503,
                detail=f"Speichern nach Schema-Update fehlgeschlagen: {e2}",
            ) from e2
    db.refresh(b)
    return _bilat_response(b)


@app.delete("/api/bilat/{ma_name}/{year}/{period_label}")
def delete_bilat(
    ma_name: str, year: int, period_label: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Löscht das Bilat für MA + Periode (Bewertungen/Notizen). Qualis bleiben."""
    from bilat_hj1_export import canonical_period_label
    from ma_access import TEAM_SCOPE_ROLES, ma_visible_to_user

    ma = db.query(MAStammdaten).filter_by(name=ma_name).first()
    if not ma:
        raise HTTPException(status_code=404, detail="MA nicht gefunden")
    period = canonical_period_label(period_label, year)
    if current_user.role in TEAM_SCOPE_ROLES:
        if not ma_visible_to_user(ma, current_user, db, year=year, months=months_for_period(period)):
            raise HTTPException(status_code=403, detail="Keine Berechtigung")
    elif not has_full_access(current_user.role):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    b = db.query(BilatData).filter_by(ma_name=ma_name, year=year, period_label=period).first()
    if not b:
        raise HTTPException(status_code=404, detail="Kein Bilat für diese Periode")
    db.delete(b)
    db.commit()
    return {
        "message": f"Bilat für {ma.display_name or ma_name} · {period} gelöscht",
        "ma_name": ma_name,
        "year": year,
        "period_label": period,
    }


@app.get("/api/bilat-overview/{year}/{period_label}")
def get_bilat_overview(year: int, period_label: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from bilat_hj1_export import canonical_period_label
    period = canonical_period_label(period_label, year)
    mas = db.query(MAStammdaten).filter_by(is_active=True).all()
    mas = filter_mas_for_user(mas, current_user, db, year=year, months=months_for_period(period))
    bilats = {b.ma_name: b for b in db.query(BilatData).filter_by(year=year, period_label=period).all()}
    return [{
        "name": m.name, "display_name": m.display_name, "team": m.team,
        "has_data": m.name in bilats and (bilats[m.name].flow_phase == "done" or any(
            getattr(bilats[m.name], f"kat_{k}_fk", None) is not None for k in "abcd"
        )),
        "flow_phase": bilats[m.name].flow_phase if m.name in bilats else "fk_prep",
        "kat_a_fk": bilats[m.name].kat_a_fk if m.name in bilats else None,
        "kat_b_fk": bilats[m.name].kat_b_fk if m.name in bilats else None,
        "kat_c_fk": bilats[m.name].kat_c_fk if m.name in bilats else None,
        "kat_d_fk": bilats[m.name].kat_d_fk if m.name in bilats else None,
        "kpi_type": CC_KPI_TYPE.get(m.name),
        "kpi_label": cc_kpi_label(m.name),
    } for m in mas]


# ── Qualitative Ziele (Management) ────────────────────────────────────────
class QualGoalItem(BaseModel):
    name: str
    result: Optional[str] = None
    status: Optional[str] = None
    detail: Optional[str] = None
    notes: Optional[str] = None
    sort_order: Optional[int] = None


class QualGoalsSaveRequest(BaseModel):
    goals: List[QualGoalItem]
    unlock_signed: Optional[bool] = False  # True = Signatur ungültig machen und speichern


def _validate_upload_file(filename: str | None, content_type: str | None) -> str:
    from documents_store import validate_upload_file
    try:
        return validate_upload_file(filename, content_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _require_qual_goal_access(ma: MAStammdaten, user: User, db: Session, year: int, period_label: str):
    from ma_access import TEAM_SCOPE_ROLES, ma_visible_to_user
    if has_full_access(user.role):
        return
    if user.role in TEAM_SCOPE_ROLES:
        if ma_visible_to_user(ma, user, db, year=year, months=months_for_period(period_label)):
            return
    raise HTTPException(status_code=403, detail="Keine Berechtigung")


@app.get("/api/qual-goals/{year}/{period_label}")
def list_all_qual_goals_overview(
    year: int, period_label: str,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    from bilat_hj1_export import canonical_period_label
    from documents_store import get_signature, signature_as_dict
    from qual_goals import list_qual_goals, goals_as_dicts

    period = canonical_period_label(period_label, year)
    mas = db.query(MAStammdaten).filter_by(is_active=True).all()
    mas = filter_mas_for_user(mas, current_user, db, year=year, months=months_for_period(period))
    out = []
    for m in mas:
        goals = goals_as_dicts(list_qual_goals(db, m.name, year, period))
        sig = signature_as_dict(get_signature(db, m.name, year, period))
        out.append({
            "name": m.name,
            "display_name": m.display_name,
            "team": m.team,
            "goal_count": len(goals),
            "goals": goals,
            "kpi_label": cc_kpi_label(m.name),
            "signed": bool(sig),
            "signature": sig,
        })
    return {"period_label": period, "year": year, "ma_data": out}


@app.get("/api/qual-goals/{ma_name}/{year}/{period_label}")
def get_qual_goals(
    ma_name: str, year: int, period_label: str,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    from bilat_hj1_export import canonical_period_label, _read_qual_goals_from_template
    from documents_store import get_signature, signature_as_dict
    from qual_goals import list_qual_goals, resolve_qual_goals_for_bilat

    ma = db.query(MAStammdaten).filter_by(name=ma_name).first()
    if not ma:
        raise HTTPException(status_code=404, detail="MA nicht gefunden")
    period = canonical_period_label(period_label, year)
    _require_qual_goal_access(ma, current_user, db, year, period)
    rows = list_qual_goals(db, ma_name, year, period)
    goals = resolve_qual_goals_for_bilat(db, ma_name, year, period)
    sig = signature_as_dict(get_signature(db, ma_name, year, period))
    source = "db" if rows else ("template" if goals else "empty")
    return {
        "ma_name": ma_name,
        "display_name": ma.display_name,
        "period_label": period,
        "year": year,
        "source": source,
        "goals": goals,
        "template_goals": _read_qual_goals_from_template(ma_name),
        "signed": bool(sig),
        "signature": sig,
    }


@app.put("/api/qual-goals/{ma_name}/{year}/{period_label}")
def save_qual_goals(
    ma_name: str, year: int, period_label: str, body: QualGoalsSaveRequest,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    from bilat_hj1_export import canonical_period_label
    from documents_store import get_signature
    from qual_goals import replace_qual_goals, goals_as_dicts
    from qual_sign import supersede_signatures

    ma = db.query(MAStammdaten).filter_by(name=ma_name).first()
    if not ma:
        raise HTTPException(status_code=404, detail="MA nicht gefunden")
    period = canonical_period_label(period_label, year)
    _require_qual_goal_access(ma, current_user, db, year, period)

    existing_sig = get_signature(db, ma_name, year, period)
    if existing_sig and not body.unlock_signed:
        raise HTTPException(
            status_code=409,
            detail="Qualis sind unterzeichnet. Zum Ändern zuerst «Bearbeitung freigeben» — die Signatur wird ungültig.",
        )
    if existing_sig and body.unlock_signed:
        supersede_signatures(db, ma_name, year, period)

    rows = replace_qual_goals(
        db,
        ma_name=ma_name,
        year=year,
        period_label=period,
        goals=[g.model_dump() for g in body.goals],
        updated_by=current_user.username,
    )
    return {
        "message": (
            f"{len(rows)} Quali-Ziele gespeichert"
            + (" — Signatur aufgehoben, bitte neu unterzeichnen" if existing_sig and body.unlock_signed else "")
        ),
        "ma_name": ma_name,
        "period_label": period,
        "goals": goals_as_dicts(rows),
        "source": "db",
        "signed": False if (existing_sig and body.unlock_signed) else bool(existing_sig and not body.unlock_signed),
    }


@app.post("/api/qual-goals/{ma_name}/{year}/{period_label}/import-template")
def import_qual_goals_from_template(
    ma_name: str, year: int, period_label: str,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """Übernimmt Zielnamen/Status aus der Word-Vorlage in die DB (einmalig füttern)."""
    from bilat_hj1_export import canonical_period_label, _read_qual_goals_from_template
    from qual_goals import replace_qual_goals, goals_as_dicts

    ma = db.query(MAStammdaten).filter_by(name=ma_name).first()
    if not ma:
        raise HTTPException(status_code=404, detail="MA nicht gefunden")
    period = canonical_period_label(period_label, year)
    _require_qual_goal_access(ma, current_user, db, year, period)
    from documents_store import get_signature
    if get_signature(db, ma_name, year, period):
        raise HTTPException(
            status_code=409,
            detail="Qualis sind unterzeichnet — Import blockiert. Zuerst Bearbeitung freigeben.",
        )
    tpl = _read_qual_goals_from_template(ma_name)
    if not tpl:
        raise HTTPException(status_code=404, detail="Keine Quali-Ziele in der Word-Vorlage")
    rows = replace_qual_goals(
        db,
        ma_name=ma_name,
        year=year,
        period_label=period,
        goals=tpl,
        updated_by=current_user.username,
    )
    return {
        "message": f"{len(rows)} Ziele aus Vorlage importiert",
        "goals": goals_as_dicts(rows),
        "source": "db",
    }


class QualSignRequest(BaseModel):
    fk_display_name: str
    ma_confirm_name: str
    vereinbarungen: Optional[str] = None
    notes: Optional[str] = None


@app.post("/api/qual-goals/{ma_name}/{year}/{period_label}/sign")
def sign_qual_goals_endpoint(
    ma_name: str, year: int, period_label: str, body: QualSignRequest,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    from bilat_hj1_export import canonical_period_label
    from qual_sign import sign_qual_goals

    ma = db.query(MAStammdaten).filter_by(name=ma_name).first()
    if not ma:
        raise HTTPException(status_code=404, detail="MA nicht gefunden")
    period = canonical_period_label(period_label, year)
    _require_qual_goal_access(ma, current_user, db, year, period)
    try:
        return sign_qual_goals(
            db,
            ma=ma,
            year=year,
            period_label=period,
            current_user=current_user,
            fk_display_name=body.fk_display_name,
            ma_confirm_name=body.ma_confirm_name,
            vereinbarungen=body.vereinbarungen,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Dokumenten-Ablage ─────────────────────────────────────────────────────
@app.get("/api/documents")
def list_documents(
    ma_name: Optional[str] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    from documents_store import document_as_dict, list_documents_for_mas

    y = year or datetime.utcnow().year
    mas = db.query(MAStammdaten).filter_by(is_active=True).all()
    mas = filter_mas_for_user(mas, current_user, db, year=y, months=list(range(1, 13)))
    if ma_name:
        mas = [m for m in mas if m.name == ma_name]
        if not mas:
            raise HTTPException(status_code=403, detail="Keine Berechtigung")
    docs = list_documents_for_mas(db, [m.name for m in mas])
    ma_index = {m.name: m for m in mas}
    return {
        "documents": [
            {
                **document_as_dict(d),
                "display_name": (ma_index.get(d.ma_name).display_name if ma_index.get(d.ma_name) else d.ma_name),
                "team": (ma_index.get(d.ma_name).team if ma_index.get(d.ma_name) else None),
            }
            for d in docs
        ],
        "mas": [
            {"name": m.name, "display_name": m.display_name, "team": m.team}
            for m in sorted(mas, key=lambda x: (x.team or "", x.display_name or x.name))
        ],
    }


@app.get("/api/documents/{doc_id}/download")
def download_document(
    doc_id: int,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user_download),
):
    from documents_store import read_document_bytes

    doc = db.query(MaDocument).filter_by(id=doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    ma = db.query(MAStammdaten).filter_by(name=doc.ma_name).first()
    if not ma:
        raise HTTPException(status_code=404, detail="MA nicht gefunden")
    y = doc.year or datetime.utcnow().year
    _require_qual_goal_access(ma, current_user, db, y, doc.period_label or f"HJ1 {y}")
    payload = read_document_bytes(doc)
    if not payload:
        raise HTTPException(status_code=404, detail="Datei fehlt auf dem Server")
    fname = doc.filename or "dokument.bin"
    safe_ascii = fname.encode("ascii", "ignore").decode("ascii") or "dokument.bin"
    return Response(
        content=payload,
        media_type=doc.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename=\"{safe_ascii}\"; filename*=UTF-8''{quote(fname)}",
            "Cache-Control": "no-store",
        },
    )


@app.delete("/api/documents/{doc_id}")
def delete_document_endpoint(
    doc_id: int,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    from documents_store import delete_document

    doc = db.query(MaDocument).filter_by(id=doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")
    ma = db.query(MAStammdaten).filter_by(name=doc.ma_name).first()
    if not ma:
        raise HTTPException(status_code=404, detail="MA nicht gefunden")
    y = doc.year or datetime.utcnow().year
    _require_qual_goal_access(ma, current_user, db, y, doc.period_label or f"HJ1 {y}")
    delete_document(db, doc)
    return {"message": "Dokument gelöscht"}


@app.post("/api/documents/{ma_name}/upload")
async def upload_document(
    ma_name: str,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    year: Optional[int] = Form(None),
    period_label: Optional[str] = Form(None),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    from documents_store import document_as_dict, save_bytes_document
    from bilat_hj1_export import canonical_period_label, period_for_calendar

    ma = db.query(MAStammdaten).filter_by(name=ma_name).first()
    if not ma:
        raise HTTPException(status_code=404, detail="MA nicht gefunden")
    y = year or datetime.utcnow().year
    today = datetime.utcnow()
    default_period = period_for_calendar(today.year, today.month)
    period = canonical_period_label(period_label or default_period, y)
    _require_qual_goal_access(ma, current_user, db, y, period)
    fname = _validate_upload_file(file.filename, file.content_type)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Leere Datei")
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Datei zu gross (max. 15 MB)")
    doc = save_bytes_document(
        db,
        ma_name=ma_name,
        title=title or fname,
        doc_type="upload",
        filename=fname,
        content=content,
        mime_type=file.content_type or "application/octet-stream",
        created_by=current_user.username,
        year=y,
        period_label=period,
        notes=notes,
    )
    return {"message": "Hochgeladen", "document": document_as_dict(doc)}


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
from bg_pct import normalize_bg_pct

class MACreate(BaseModel):
    name: str
    display_name: str
    team: str
    role: str = "therapeut"
    bg_pct: float = 1.0
    eintritt: Optional[str] = None
    austritt: Optional[str] = None
    fk_username: Optional[str] = None


def _ma_admin_dict(m: MAStammdaten, fk_users: dict, *, standorte: list[str] | None = None) -> dict:
    fk = fk_users.get(m.fk_username) if m.fk_username else None
    sites = standorte if standorte is not None else []
    if not sites and m.team and m.team not in ("Office", "Management"):
        sites = [m.team]
    return {
        "id": m.id, "name": m.name, "display_name": m.display_name, "team": m.team,
        "standorte": sites,
        "role": m.role, "bg_pct": m.bg_pct, "is_active": m.is_active,
        "eintritt": m.eintritt, "austritt": m.austritt,
        "fk_username": m.fk_username,
        "fk_display_name": (fk.full_name if fk else None) if m.fk_username else None,
    }


@app.get("/api/admin/teamleads")
def admin_list_teamleads(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_full_access(current_user)
    from ma_access import list_assignable_fk_users
    return list_assignable_fk_users(db)


@app.get("/api/admin/ma")
def admin_get_ma(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_full_access(current_user)
    from datetime import date
    from schedule_utils import build_schedule_cache, standorte_from_entries

    mas = db.query(MAStammdaten).order_by(MAStammdaten.name).all()
    fk_names = {m.fk_username for m in mas if m.fk_username}
    fk_users = {}
    if fk_names:
        fk_users = {u.username: u for u in db.query(User).filter(User.username.in_(fk_names)).all()}
    year = date.today().year
    month = date.today().month
    schedule_cache = build_schedule_cache(db, [m.name for m in mas], year, month)
    return [
        _ma_admin_dict(
            m,
            fk_users,
            standorte=standorte_from_entries(schedule_cache.get((m.name, month), [])),
        )
        for m in mas
    ]

@app.post("/api/admin/ma")
def admin_create_ma(data: MACreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_full_access(current_user)
    payload = data.model_dump()
    payload["bg_pct"] = normalize_bg_pct(payload.get("bg_pct"))
    ma = MAStammdaten(**payload)
    db.add(ma); db.commit(); db.refresh(ma)
    return {"id": ma.id, "message": f"{ma.name} erstellt"}

@app.put("/api/admin/ma/{ma_name:path}")
def admin_update_ma(ma_name: str, data: MACreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_full_access(current_user)
    ma = db.query(MAStammdaten).filter_by(name=ma_name).first()
    if not ma: raise HTTPException(status_code=404, detail="MA nicht gefunden")
    payload = data.model_dump()
    payload["bg_pct"] = normalize_bg_pct(payload.get("bg_pct"))
    for k, v in payload.items():
        setattr(ma, k, v)
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
        "version": "1.0.3",
        "cors": "no-credentials",
        "auth": "bearer-or-query-token",
        "storage": storage,
    }
