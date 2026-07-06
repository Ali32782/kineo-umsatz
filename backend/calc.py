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

HALBTAG_PCT = 0.10   # 10 % der Woche = ein Halbtag (VM oder NM)
TAG_PCT = 0.20       # 20 % der Woche = ganzer Tag (VM + NM)

MA_OVERRIDES = {
    "Sonia.M": {1: {"mo":0.20,"di":0.20,"mi":0.20,"do":0.20,"fr":0.00}},
}

# Anteil der Arbeitszeit pro Standort (summe = 1.0 über alle Standorte des MA)
MA_STANDORT_SPLITS = {
    "Helen.S":  {"Zollikon": 0.5, "Seefeld": 0.5},
    "Meike.V":  {"Zollikon": 0.5, "Seefeld": 0.5},
}

def day_pct_to_halves(day_pct: float) -> tuple[float, float]:
    """MA_PATTERNS-Tagesanteil (0.10=Halbtag, 0.20=Tag) → (vm_pct, nm_pct)."""
    if day_pct <= 0:
        return 0.0, 0.0
    if day_pct <= HALBTAG_PCT + 0.001:
        return round(day_pct, 2), 0.0
    half = round(day_pct / 2, 2)
    return half, half

def schedule_needs_reseed(entries) -> bool:
    """True wenn kein Plan existiert oder noch alte Halbtag-Einheiten (≥15 %) drin sind."""
    if not entries:
        return True
    return any((e.vm_pct or 0) >= 0.15 or (e.nm_pct or 0) >= 0.15 for e in entries)

def _collect_schedule_weights(schedule_entries, include_office: bool = False) -> dict[str, float]:
    weights: dict[str, float] = {}
    if not schedule_entries:
        return weights
    for e in schedule_entries:
        if e.vm_pct and e.vm_standort and (include_office or e.vm_standort != "Office"):
            weights[e.vm_standort] = weights.get(e.vm_standort, 0) + e.vm_pct
        if e.nm_pct and e.nm_standort and (include_office or e.nm_standort != "Office"):
            weights[e.nm_standort] = weights.get(e.nm_standort, 0) + e.nm_pct
    return weights


def get_standort_fte_weights(
    ma_name: str,
    primary_team: str,
    bg_pct: float,
    schedule_entries=None,
) -> dict[str, float]:
    """Absolute FTE pro Standort — Summe der Halbtags-Anteile (0.10 = 10 % der Woche)."""
    weights = _collect_schedule_weights(schedule_entries)
    if weights:
        return {k: round(v, 2) for k, v in weights.items()}
    if ma_name in MA_STANDORT_SPLITS:
        return {k: round(bg_pct * v, 2) for k, v in MA_STANDORT_SPLITS.items()}
    return {primary_team: bg_pct}


def get_standort_splits(ma_name: str, primary_team: str, schedule_entries=None) -> dict:
    """Relative Umsatz-Aufteilung pro Standort (Summe = 1.0)."""
    weights = _collect_schedule_weights(schedule_entries)
    if weights:
        total = sum(weights.values())
        return {k: v / total for k, v in weights.items()}
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
        day_pct = (e.vm_pct or 0) + (e.nm_pct or 0)
        pat[key] = max(pat[key], day_pct)
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


def _parse_ma_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def get_austritt(name: str, db=None) -> date | None:
    if db is not None:
        from database import MAStammdaten
        ma = db.query(MAStammdaten).filter_by(name=name).first()
        if ma:
            return _parse_ma_date(ma.austritt)
    return None


def is_employed_in_month(
    eintritt: str | None,
    austritt: str | None,
    year: int,
    month: int,
    is_active: bool = True,
) -> bool:
    """True wenn MA im Monat beschäftigt war (Eintritt/Austritt berücksichtigt)."""
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])

    ein = _parse_ma_date(eintritt) or date(year, 1, 1)
    if ein > month_end:
        return False

    aus = _parse_ma_date(austritt)
    if aus and aus < month_start:
        return False

    # Deaktiviert ohne Austrittsdatum → nirgends zählen
    if not is_active and not aus:
        return False

    return True

def get_pattern(name: str, year: int, m_num: int, db=None) -> dict:
    base = dict(MA_PATTERNS.get(name, {}))
    if db is not None:
        from schedule_utils import get_schedule_entries_for_month
        entries = get_schedule_entries_for_month(name, year, m_num, db)
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
    pat = get_pattern(name, year, m_num, db=db)
    if not pat:
        return 0.0
    ein = get_eintritt(name, year, db=db)
    last = calendar.monthrange(year, m_num)[1]
    me = date(year, m_num, last)
    if ein > me:
        return 0.0
    aus = get_austritt(name, db=db)
    if aus and aus < date(year, m_num, 1):
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
                total += pct / TAG_PCT * 0.5
            else:
                total += pct / TAG_PCT
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
    pat = get_pattern(name, year, m_num, db=db)
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

MONTH_NAMES_DE = {
    1:"Januar",2:"Februar",3:"März",4:"April",5:"Mai",6:"Juni",
    7:"Juli",8:"August",9:"September",10:"Oktober",11:"November",12:"Dezember"
}

_CSV_NAME_HEADERS = {
    "name", "mitarbeiter", "mitarbeitende", "mitarbeitende/r", "therapeut",
    "therapeut/in", "ma", "person", "bearbeiter",
}
_CSV_AMOUNT_HEADERS = {
    "umsatz", "total", "netto", "brutto", "amount", "revenue",
    "umsatz chf", "total chf",
}
# «Betrag» in Kineo-Pivot-CSV = Jahressumme — nicht als Monatsumsatz verwenden
_CSV_YTD_HEADERS = {"betrag", "betrag chf", "summe", "jahr", "ytd", "total jahr"}
_CSV_MONTH_HEADERS = {"monat", "month", "periode", "period", "monat nr", "monatnr"}
_CSV_DATE_HEADERS = {"datum", "date", "buchungsdatum", "leistungsdatum"}
_CSV_SKIP_NAMES = {"summe", "total", "gesamt", "subtotal", ""}
_MONTH_NAME_LOOKUP = {
    v.lower(): k for k, v in MONTH_NAMES_DE.items()
}
_MONTH_NAME_LOOKUP.update({
    "jan": 1, "feb": 2, "mar": 3, "maerz": 3, "märz": 3, "apr": 4,
    "mai": 5, "jun": 6, "juli": 7, "jul": 7, "aug": 8, "sep": 9,
    "okt": 10, "nov": 11, "dez": 12,
})


def _norm_csv_header(value: str) -> str:
    return (
        (value or "")
        .replace("\xa0", " ")
        .strip()
        .lower()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
    )


def _header_month_year(cell: str) -> tuple[int, int] | None:
    """Spaltenkopf wie «Jun 2026» / «Jun\xa02026» → (month, year)."""
    raw = _norm_csv_header(cell)
    if not raw:
        return None
    year = None
    for tok in raw.split():
        if tok.isdigit() and 2000 <= int(tok) <= 2100:
            year = int(tok)
            break
    month_num = _parse_month_cell(raw, None, None)
    if month_num and year:
        return month_num, year
    return None


def _find_pivot_month_columns(header: list[str]) -> list[tuple[int, int, int]]:
    """Alle (col_index, month, year) aus Pivot-Köpfen «Jan 2026» …"""
    found = []
    for i, h in enumerate(header):
        parsed = _header_month_year(h)
        if parsed:
            found.append((i, parsed[0], parsed[1]))
    return found


def _find_pivot_amount_column(header: list[str], year: int, month: int) -> int | None:
    for col, m, y in _find_pivot_month_columns(header):
        if m == month and y == year:
            return col
    return None


def parse_chf_amount(value: str) -> float:
    """Schweizer Zahlenformat: 1'234.56 / 1'234,56 / 1234,50."""
    s = (value or "").strip().replace("'", "").replace(" ", "").replace("CHF", "").replace("chf", "")
    if not s:
        raise ValueError("empty amount")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        left, right = s.split(",", 1)
        if len(right) <= 2 and right.isdigit():
            s = f"{left}.{right}"
        else:
            s = s.replace(",", "")
    return float(s)


def _parse_month_cell(value, year: int | None, month: int | None) -> int | None:
    """True/Monatsnummer wenn Zelle zum Zielmonat passt; None = nicht filterbar."""
    if value is None or str(value).strip() == "":
        return None
    s = str(value).strip().lower()
    if s.isdigit():
        n = int(s)
        if 1 <= n <= 12:
            return n
        return None
    for key, num in _MONTH_NAME_LOOKUP.items():
        if key in s:
            return num
    if len(s) >= 7 and s[4] == "-":
        try:
            y, m = int(s[:4]), int(s[5:7])
            if year and y != year:
                return -1
            return m
        except ValueError:
            pass
    if len(s) >= 7 and s[2] == ".":
        try:
            m, y = int(s[:2]), int(s[3:7])
            if year and y != year:
                return -1
            return m
        except ValueError:
            pass
    return None


def _row_matches_target_month(
    parts: list[str],
    month_col: int | None,
    date_col: int | None,
    year: int | None,
    month: int | None,
) -> bool:
    if month is None:
        return True
    if month_col is not None and month_col < len(parts):
        m = _parse_month_cell(parts[month_col], year, month)
        if m == -1:
            return False
        if m is not None:
            return m == month
    if date_col is not None and date_col < len(parts):
        raw = parts[date_col].strip()[:10]
        try:
            if len(raw) >= 7 and raw[4] == "-":
                y, mo = int(raw[:4]), int(raw[5:7])
                return (not year or y == year) and mo == month
            if len(raw) >= 7 and raw[2] == ".":
                mo, y = int(raw[:2]), int(raw[3:7])
                return (not year or y == year) and mo == month
        except ValueError:
            pass
    return month_col is None and date_col is None


def _detect_csv_columns(
    header: list[str],
    rows: list[list[str]],
    year: int | None = None,
    month: int | None = None,
) -> tuple[int, int, int | None, int | None]:
    """Finde Name-, Betrag-, Monats- und Datumsspalte."""
    norm = [_norm_csv_header(h) for h in header]
    name_col = next((i for i, h in enumerate(norm) if h in _CSV_NAME_HEADERS), 0)
    pivot_cols = _find_pivot_month_columns(header)

    # Kineo Taxpunkte-Export: Name;Betrag(Jahr);Jan 2026;…;Jun 2026;…
    if year and month and pivot_cols:
        pivot_amount = _find_pivot_amount_column(header, year, month)
        if pivot_amount is not None:
            return name_col, pivot_amount, None, None

    amount_col = next((i for i, h in enumerate(norm) if h in _CSV_AMOUNT_HEADERS), None)
    if amount_col is None and not pivot_cols:
        amount_col = next(
            (i for i, h in enumerate(norm) if h in _CSV_YTD_HEADERS and i != name_col),
            None,
        )
    month_col = next((i for i, h in enumerate(norm) if h in _CSV_MONTH_HEADERS), None)
    date_col = next((i for i, h in enumerate(norm) if h in _CSV_DATE_HEADERS), None)

    if amount_col is None:
        # Fallback: erste Spalte mit parsebarem CHF-Betrag (nicht Name/Monat)
        pivot_indices = {c for c, _, _ in pivot_cols}
        for i in range(len(header)):
            if i == name_col or i == month_col or i == date_col or i in pivot_indices:
                continue
            if norm[i] in _CSV_YTD_HEADERS and pivot_cols:
                continue
            hits = 0
            for row in rows[:20]:
                if i >= len(row):
                    continue
                try:
                    parse_chf_amount(row[i])
                    hits += 1
                except ValueError:
                    pass
            if hits >= max(1, len(rows[:20]) // 2):
                amount_col = i
                break
    if amount_col is None:
        amount_col = 1 if len(header) > 1 else 0

    if month_col is None and rows:
        for i in range(len(header)):
            if i in (name_col, amount_col, date_col):
                continue
            nums = []
            for row in rows:
                if i >= len(row):
                    continue
                m = _parse_month_cell(row[i], None, None)
                if m is not None and 1 <= m <= 12:
                    nums.append(m)
            if len(nums) >= max(3, len(rows) * 0.5) and len(set(nums)) > 1:
                month_col = i
                break

    return name_col, amount_col, month_col, date_col


def parse_csv_umsatz(
    content: str,
    year: int | None = None,
    month: int | None = None,
) -> dict:
    """Parse Kineo-CSV → {csv_name: umsatz_total}. Optional nur Zielmonat."""
    return parse_csv_umsatz_result(content, year=year, month=month)["by_name"]


def parse_csv_umsatz_result(
    content: str,
    year: int | None = None,
    month: int | None = None,
) -> dict:
    """
    Parse Kineo-CSV mit Spaltenerkennung und Monatsfilter.
    Mehrzeilige Exporte (z. B. je Monat eine Zeile) werden nur für den Zielmonat summiert.
    """
    lines = [ln for ln in content.strip().splitlines() if ln.strip()]
    warnings: list[str] = []
    if len(lines) < 2:
        return {"by_name": {}, "warnings": warnings, "rows_used": 0, "rows_skipped": 0, "total": 0.0}

    header = [p.strip() for p in lines[0].split(";")]
    raw_rows = [[p.strip() for p in ln.split(";")] for ln in lines[1:]]
    name_col, amount_col, month_col, date_col = _detect_csv_columns(
        header, raw_rows, year=year, month=month,
    )
    pivot_cols = _find_pivot_month_columns(header)
    if year and month and pivot_cols and _find_pivot_amount_column(header, year, month) is not None:
        warnings.append(
            f"Monatsspalte «{MONTH_NAMES_DE.get(month, month)} {year}» verwendet "
            f"(nicht «Betrag» = Jahressumme)."
        )

    by_name: dict[str, float] = {}
    rows_used = 0
    rows_skipped = 0
    unfiltered_names: dict[str, int] = {}

    for parts in raw_rows:
        if len(parts) <= max(name_col, amount_col):
            continue
        name = parts[name_col].strip()
        if _norm_csv_header(name) in _CSV_SKIP_NAMES:
            continue
        unfiltered_names[name] = unfiltered_names.get(name, 0) + 1
        if not _row_matches_target_month(parts, month_col, date_col, year, month):
            rows_skipped += 1
            continue
        try:
            amount = parse_chf_amount(parts[amount_col])
        except (ValueError, IndexError):
            continue
        if amount <= 0:
            continue
        by_name[name] = by_name.get(name, 0) + amount
        rows_used += 1

    if month and rows_skipped > 0 and rows_used > 0:
        warnings.append(
            f"{rows_skipped} Zeilen aus anderen Monaten ignoriert — nur {MONTH_NAMES_DE.get(month, month)} gezählt."
        )
    elif month and rows_used > 0 and month_col is None and date_col is None:
        dup = {n: c for n, c in unfiltered_names.items() if c >= 3}
        if dup:
            max_dup = max(dup.values())
            warnings.append(
                f"Achtung: bis zu {max_dup} Zeilen pro Person ohne Monatsspalte — "
                "bitte Monatsexport aus der Software verwenden, sonst werden alle Zeilen summiert."
            )

    total = round(sum(by_name.values()), 2)
    return {
        "by_name": by_name,
        "warnings": warnings,
        "rows_used": rows_used,
        "rows_skipped": rows_skipped,
        "total": total,
    }

def zeg_color(zeg_b: float | None) -> str:
    if zeg_b is None:
        return "gray"
    if zeg_b >= 1.0:
        return "green"
    if zeg_b >= 0.85:
        return "amber"
    return "red"

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
