# Kineo AG — Umsatzanalyse App

## Lokal starten

### Backend (FastAPI)
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

---

## Login-Daten (initial)
| Benutzer | Passwort | Rolle |
|---|---|---|
| ali | kineo2026 | CEO (alles sichtbar) |
| martino | kineo2026 | BD (CSV Upload + Inputs) |
| sereina | kineo2026 | CEO (alles sichtbar) |
| clara | kineo2026 | Teamlead (nur Escher Wyss) |
| hanna | kineo2026 | Teamlead (nur Thalwil) |
| raphael | kineo2026 | Teamlead (nur Wipkingen) |
| helen | kineo2026 | Teamlead (nur Zollikon) |

---

## Workflow für Martino (monatlich)

1. **CSV aus Software exportieren** (Monatsexport)
2. **Login** → `http://localhost:3000`
3. **Daten eingeben** → Monat wählen → CSV hochladen
4. **Tätigkeiten** → Ferien/Kurse/etc. pro MA eintragen → Speichern
5. **Exporte** → Excel oder Bilaterals herunterladen

---

## Deployment auf Hetzner

```bash
# Einmalig
docker-compose build
docker-compose up -d

# Mit Domain (nginx reverse proxy davor)
# Backend: intern :8000
# Frontend: :3000 → nach aussen :80/:443
```

### Passwörter ändern
```bash
cd backend
python -c "
from database import SessionLocal, User
from passlib.context import CryptContext
pwd = CryptContext(schemes=['bcrypt'])
db = SessionLocal()
user = db.query(User).filter(User.username=='ali').first()
user.hashed_password = pwd.hash('NEUES_PASSWORT')
db.commit()
"
```

---

## Struktur
```
kineo-app/
├── backend/
│   ├── main.py          # FastAPI routes
│   ├── database.py      # SQLite models + seed
│   ├── calc.py          # ZEG-B Berechnungslogik
│   ├── excel_export.py  # Excel-Generator
│   ├── bilat_export.py  # Bilat Word-Generator
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx      # React App (Login, Dashboard, Upload, Exporte)
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── data/                # SQLite DB (kineo.db)
├── exports/             # Generierte Dateien
└── docker-compose.yml
```

## API Endpoints
| Method | URL | Beschreibung |
|---|---|---|
| POST | /api/login | Login → JWT Token |
| GET | /api/ma | MA-Liste (gefiltert nach Rolle) |
| POST | /api/upload-csv | CSV-Umsatzdaten importieren |
| GET | /api/inputs/{year}/{month} | Tätigkeits-Inputs lesen |
| POST | /api/inputs | Tätigkeits-Inputs speichern |
| GET | /api/dashboard/{year}/{month} | ZEG-B Dashboard-Daten |
| GET | /api/ytd/{year} | Jahresübersicht alle Monate |
| GET | /api/export/excel/{year} | Excel-Download |
| GET | /api/export/bilats/{year}/{month} | Bilats ZIP-Download |
