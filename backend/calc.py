from datetime import date
import calendar

ZIEL = 1040.0
STD = 8.4

WEEKDAY_KEYS = ["mo", "di", "mi", "do", "fr"]

FEIERTAGE_FULL = [
    date(2026,1,1), date(2026,1,2), date(2026,4,3), date(2026,4,6),
    date(2026,5,1), date(2026,5,14), date(2026,5,25), date(2026,8,1),
    date(2026,12,25), date(2026,12,26),
]
FEIERTAGE_HALF = [
    date(2026,4,20),  # Sächseläuten
    date(2026,9,14),  # Knabenschiessen
]

MA_PATTERNS = {
    "Andrina.K":  {"mo":0.20,"di":0.20,"mi":0.20,"do":0.20,"fr":0.10,"mgmt":0,"leit":6},
    "Barbara.V":  {"mo":0.20,"di":0.20,"mi":0.20,"do":0.20,"fr":0.00,"mgmt":0,"leit":0},
    "Carmen.W":   {"mo":0.20,"di":0.00,"mi":0.00,"do":0.10,"fr":0.10,"mgmt":0,"leit":0},
    "Clara.B":    {"mo":0.00,"di":0.20,"mi":0.20,"do":0.20,"fr":0.20,"mgmt":0,"leit":11},
    "Emma.L":     {"mo":0.20,"di":0.20,"mi":0.20,"do":0.20,"fr":0.20,"mgmt":0,"leit":0},
    "Eva.D":      {"mo":0.20,"di":0.20,"mi":0.20,"do":0.20,"fr":0.20,"mgmt":0,"leit":0},
    "Hanna.R":    {"mo":0.20,"di":0.20,"mi":0.20,"do":0.20,"fr":0.20,"mgmt":0,"leit":9},
    "Helen.S":    {"mo":0.00,"di":0.20,"mi":0.20,"do":0.20,"fr":0.20,"mgmt":0,"leit":4},
    "Joëlle.R":   {"mo":0.20,"di":0.20,"mi":0.10,"do":0.20,"fr":0.20,"mgmt":0,"leit":0},
    "Lucrecia.G": {"mo":0.20,"di":0.20,"mi":0.20,"do":0.20,"fr":0.00,"mgmt":0,"leit":0},
    "Martino.C":  {"mo":0.20,"di":0.20,"mi":0.20,"do":0.20,"fr":0.20,"mgmt":20,"leit":0},
    "Meike.V":    {"mo":0.20,"di":0.20,"mi":0.20,"do":0.20,"fr":0.00,"mgmt":0,"leit":0},
    "Noah.S":     {"mo":0.20,"di":0.20,"mi":0.00,"do":0.00,"fr":0.20,"mgmt":0,"leit":0},
    "Pablo.G":    {"mo":0.20,"di":0.20,"mi":0.20,"do":0.20,"fr":0.00,"mgmt":0,"leit":0},
    "Pablo.M":    {"mo":0.20,"di":0.20,"mi":0.20,"do":0.20,"fr":0.00,"mgmt":0,"leit":0},
    "Raphael.H":  {"mo":0.00,"di":0.20,"mi":0.20,"do":0.20,"fr":0.20,"mgmt":0,"leit":4},
    "Sereina.U":  {"mo":0.20,"di":0.20,"mi":0.20,"do":0.10,"fr":0.20,"mgmt":40,"leit":6},
    "Sonia.M":    {"mo":0.20,"di":0.20,"mi":0.20,"do":0.20,"fr":0.20,"mgmt":0,"leit":0},
    "Valerio.S":  {"mo":0.20,"di":0.00,"mi":0.20,"do":0.00,"fr":0.20,"mgmt":0,"leit":0},
}

MA_EINTRITTE = {
    "Helen.S": date(2026,3,1),
    "Raphael.H": date(2026,3,1),
    "Valerio.S": date(2026,5,1),
    "Lucrecia.G": date(2026,6,1),
    "Pablo.G": date(2026,6,1),
    "Pablo.M": date(2026,6,1),
    "Sonia.M": date(2026,1,1),
}

MA_OVERRIDES = {
    "Sonia.M": {1: {"mo":0.20,"di":0.20,"mi":0.20,"do":0.20,"fr":0.00}},
}

# Anteil der Arbeitszeit pro Standort (summe = 1.0 über alle Standorte des MA)
MA_STANDORT_SPLITS = {
    "Helen.S":  {"Zollikon": 0.5, "Seefeld": 0.5},
    "Meike.V":  {"Zollikon": 0.5, "Seefeld": 0.5},
}

def get_standort_splits(ma_name: str, primary_team: str, schedule_entries=None) -> dict:
    """Standort-Aufteilung: DB-Schedule mit Standorten > MA_STANDORT_SPLITS > Primary-Team."""
    if schedule_entries:
        splits = {}
        for e in schedule_entries:
            if e.vm_pct and e.vm_standort and e.vm_standort != "Office":
                splits[e.vm_standort] = splits.get(e.vm_standort, 0) + e.vm_pct
            if e.nm_pct and e.nm_standort and e.nm_standort != "Office":
                splits[e.nm_standort] = splits.get(e.nm_standort, 0) + e.nm_pct
        if splits:
            total = sum(splits.values())
            return {k: v / total for k, v in splits.items()}
    if ma_name in MA_STANDORT_SPLITS:
        return dict(MA_STANDORT_SPLITS[ma_name])
    return {primary_team: 1.0}

def pattern_from_schedule(entries) -> dict:
    """Convert MAScheduleEntry rows to a MA_PATTERNS-compatible dict."""
    pat = {k: 0.0 for k in WEEKDAY_KEYS}
    pat["mgmt"] = 0
    pat["leit"] = 0
    for e in entries:
        key = WEEKDAY_KEYS[e.weekday]
        pat[key] = max(pat[key], e.vm_pct or 0, e.nm_pct or 0)
    return pat

def get_feiertage_sets(year: int, db=None) -> tuple[set, set]:
    """Return (full_day_holidays, half_day_holidays) for a year."""
    if db is not None:
        from database import Feiertag
        entries = db.query(Feiertag).filter_by(year=year).all()
        if entries:
            full, half = set(), set()
            for e in entries:
                d = date.fromisoformat(e.date_str)
                if e.faktor >= 1.0:
                    full.add(d)
                else:
                    half.add(d)
            return full, half
    full = {d for d in FEIERTAGE_FULL if d.year == year}
    half = {d for d in FEIERTAGE_HALF if d.year == year}
    return full, half

def get_eintritt(name: str, year: int, db=None) -> date:
    if db is not None:
        from database import MAStammdaten
        ma = db.query(MAStammdaten).filter_by(name=name).first()
        if ma and ma.eintritt:
            try:
                return date.fromisoformat(ma.eintritt)
            except ValueError:
                pass
    return MA_EINTRITTE.get(name, date(year, 1, 1))

def get_pattern(name: str, m_num: int, db=None) -> dict:
    base = dict(MA_PATTERNS.get(name, {}))
    if db is not None:
        from database import MAScheduleEntry
        entries = db.query(MAScheduleEntry).filter_by(ma_name=name).all()
        if entries:
            sched = pattern_from_schedule(entries)
            sched["mgmt"] = base.get("mgmt", 0)
            sched["leit"] = base.get("leit", 0)
            base = sched
    overrides = MA_OVERRIDES.get(name, {})
    if m_num in overrides:
        return {**base, **overrides[m_num]}
    return base

def compute_soll_tage(name: str, year: int, m_num: int, db=None) -> float:
    pat = get_pattern(name, m_num, db=db)
    if not pat:
        return 0.0
    ein = get_eintritt(name, year, db=db)
    last = calendar.monthrange(year, m_num)[1]
    me = date(year, m_num, last)
    if ein > me:
        return 0.0
    feiertage_full, feiertage_half = get_feiertage_sets(year, db=db)
    wd_map = {0: pat.get("mo",0), 1: pat.get("di",0), 2: pat.get("mi",0),
               3: pat.get("do",0), 4: pat.get("fr",0)}
    total = 0.0
    for week in calendar.monthcalendar(year, m_num):
        for wd in range(5):
            day = week[wd]
            if day == 0:
                continue
            pct = wd_map.get(wd, 0)
            if pct == 0:
                continue
            d = date(year, m_num, day)
            if d in feiertage_full:
                continue
            elif d in feiertage_half:
                total += pct / 0.20 * 0.5
            else:
                total += pct / 0.20
    return round(total, 2)


def compute_zeg(
    name: str, year: int, m_num: int,
    umsatz: float,
    ferien_t: float = 0,
    kurs_h: float = 0,
    workshop_h: float = 0,
    marketing_h: float = 0,
    laufanalyse_h: float = 0,
    krank_t: float = 0,
    db=None,
) -> dict:
    soll = compute_soll_tage(name, year, m_num, db=db)
    pat = get_pattern(name, m_num, db=db)
    bg = sum([pat.get(k,0) for k in WEEKDAY_KEYS])

    mgmt_t = pat.get("mgmt", 0) / 100 * soll
    leit_t = (pat.get("leit", 0) / STD * ((soll - ferien_t) / soll)) if soll > 0 else 0

    prod_a = max(soll - ferien_t, 0)
    prod_b = max(soll - ferien_t - (kurs_h + workshop_h) / STD
                 - marketing_h / STD - laufanalyse_h / STD - mgmt_t - leit_t, 0)
    prod_c = max(prod_b - krank_t, 0)

    def zeg(prod):
        if prod > 0 and umsatz > 0:
            return round(umsatz / prod / ZIEL, 4)
        return None

    return {
        "soll_tage": soll,
        "bg_pct": round(bg, 2),
        "mgmt_t": round(mgmt_t, 3),
        "leit_t": round(leit_t, 3),
        "prod_a": round(prod_a, 2),
        "prod_b": round(prod_b, 2),
        "prod_c": round(prod_c, 2),
        "zeg_a": zeg(prod_a),
        "zeg_b": zeg(prod_b),
        "zeg_c": zeg(prod_c),
    }

def parse_csv_umsatz(content: str) -> dict:
    """Parse the Kineo software CSV export → {ma_name: umsatz_total}"""
    lines = content.strip().split('\n')
    result = {}
    for line in lines[1:]:  # skip header
        parts = line.strip().split(';')
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        if name in ('Summe', ''):
            continue
        try:
            amount_str = parts[1].strip().replace("'", "").replace(",", ".")
            amount = float(amount_str)
            result[name] = amount
        except (ValueError, IndexError):
            continue
    return result

def zeg_color(zeg_b: float | None) -> str:
    if zeg_b is None:
        return "gray"
    if zeg_b >= 1.0:
        return "green"
    if zeg_b >= 0.85:
        return "amber"
    return "red"

MONTH_NAMES_DE = {
    1:"Januar",2:"Februar",3:"März",4:"April",5:"Mai",6:"Juni",
    7:"Juli",8:"August",9:"September",10:"Oktober",11:"November",12:"Dezember"
}

HOLIDAY_NAMES = {
    (1, 1): "Neujahr", (1, 2): "Berchtoldstag",
    (4, 3): "Karfreitag", (4, 6): "Ostermontag", (4, 20): "Sächseläuten",
    (5, 1): "Tag der Arbeit", (5, 14): "Auffahrt", (5, 25): "Pfingstmontag",
    (8, 1): "Nationalfeiertag", (9, 14): "Knabenschiessen",
    (12, 25): "Weihnachten", (12, 26): "Stephanstag",
}

def default_feiertage_entries(year: int) -> list[dict]:
    """Default Zürich holidays for a year (from seed lists; movable dates only if listed)."""
    entries = []
    for d in FEIERTAGE_FULL:
        if d.year == year:
            entries.append({
                "date_str": d.strftime("%Y-%m-%d"),
                "name": HOLIDAY_NAMES.get((d.month, d.day), d.strftime("%Y-%m-%d")),
                "faktor": 1.0,
            })
    for d in FEIERTAGE_HALF:
        if d.year == year:
            entries.append({
                "date_str": d.strftime("%Y-%m-%d"),
                "name": HOLIDAY_NAMES.get((d.month, d.day), d.strftime("%Y-%m-%d")),
                "faktor": 0.5,
            })
    return sorted(entries, key=lambda x: x["date_str"])
