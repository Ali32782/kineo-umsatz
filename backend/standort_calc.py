"""Standort-Aufteilung inkl. Office, Umsatz und ZEG-B pro Standort."""
from __future__ import annotations

from calc import (
    ZIEL,
    _collect_schedule_weights,
    get_standort_fte_weights,
    get_standort_splits,
    zeg_color,
)


def expand_ma_standort_rows(
    ma_row: dict,
    ma_bg: float,
    primary_team: str,
    schedule_entries,
) -> list[dict]:
    """
    Zerlegt eine MA-Zeile in Standort-Zeilen mit eigenem Umsatz, FTE und ZEG-B.
  Office erhält FTE aber keinen Umsatz.
    """
    umsatz = ma_row.get("umsatz") or 0
    prod_b = ma_row.get("prod_b") or 0
    clinical_weights = _collect_schedule_weights(schedule_entries, include_office=False)
    office_weight = _collect_schedule_weights(schedule_entries, include_office=True).get("Office", 0)

    fte_weights = get_standort_fte_weights(ma_row["name"], primary_team, ma_bg, schedule_entries)
    umsatz_splits = get_standort_splits(ma_row["name"], primary_team, schedule_entries)

    if not fte_weights:
        fte_weights = {primary_team: ma_bg}
        umsatz_splits = {primary_team: 1.0}
        if not clinical_weights:
            clinical_weights = {primary_team: ma_bg}

    total_clinical = sum(clinical_weights.values()) or sum(fte_weights.values()) or ma_bg

    rows: list[dict] = []
    for standort, fte in fte_weights.items():
        split = umsatz_splits.get(standort, 0)
        umsatz_s = round(umsatz * split, 2)
        # prod_b mit gleichem Anteil wie Umsatz — sonst ZEG-B verfälscht (z. B. 500 %+)
        prod_b_s = round(prod_b * split, 2) if prod_b else 0
        zeg_b_s = None
        if prod_b_s > 0 and umsatz_s > 0:
            zeg_b_s = round(umsatz_s / prod_b_s / ZIEL, 4)

        rows.append({
            **ma_row,
            "team": standort,
            "umsatz": umsatz_s,
            "bg_pct": fte,
            "standort_pct": round(fte / ma_bg * 100) if ma_bg else 0,
            "primary_team": primary_team,
            "prod_b_standort": prod_b_s,
            "zeg_b": zeg_b_s,
            "color": zeg_color(zeg_b_s),
            "is_office": False,
        })

    if office_weight > 0:
        rows.append({
            **ma_row,
            "team": "Office",
            "umsatz": 0,
            "bg_pct": round(office_weight, 2),
            "standort_pct": round(office_weight / ma_bg * 100) if ma_bg else 0,
            "primary_team": primary_team,
            "prod_b_standort": 0,
            "zeg_b": None,
            "color": "gray",
            "is_office": True,
        })

    return rows


def aggregate_team_summary(expanded_rows: list[dict]) -> dict:
    teams: dict = {}
    for r in expanded_rows:
        t = r["team"]
        if t not in teams:
            teams[t] = {"umsatz": 0, "zeg_b_weighted": 0, "prod_b_sum": 0, "fte": 0, "count": 0}
        teams[t]["umsatz"] += r.get("umsatz") or 0
        teams[t]["fte"] += r.get("bg_pct") or 0
        if r.get("zeg_b") and r.get("prod_b_standort"):
            teams[t]["zeg_b_weighted"] += r["zeg_b"] * r["prod_b_standort"]
            teams[t]["prod_b_sum"] += r["prod_b_standort"]
            teams[t]["count"] += 1

    summary = {}
    for t, v in teams.items():
        avg = None
        if v["prod_b_sum"] > 0:
            avg = round(v["zeg_b_weighted"] / v["prod_b_sum"], 3)
        summary[t] = {
            "umsatz": round(v["umsatz"]),
            "fte": round(v["fte"], 2),
            "zeg_b_avg": avg,
            "color": zeg_color(avg),
            "is_office": t == "Office",
        }
    return summary
