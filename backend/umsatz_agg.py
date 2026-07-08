"""Einheitliche Umsatz-Aggregation für Dashboard und Jahresübersicht."""
from __future__ import annotations

from calc import is_employed_in_month


def filter_employed_mas(mas, year: int, month: int):
    return [
        m for m in mas
        if is_employed_in_month(m.eintritt, m.austritt, year, month, m.is_active)
    ]


def ma_umsatz_for_month(umsatz_map: dict, ma_name: str, month: int) -> float:
    return float(umsatz_map.get((ma_name, month), 0) or 0)


def sum_umsatz_for_month(umsatz_map: dict, mas, month: int) -> float:
    return sum(ma_umsatz_for_month(umsatz_map, m.name, month) for m in mas)


def ma_year_umsatz(umsatz_map: dict, ma, year: int) -> float:
    return sum(
        ma_umsatz_for_month(umsatz_map, ma.name, m)
        for m in range(1, 13)
        if is_employed_in_month(ma.eintritt, ma.austritt, year, m, ma.is_active)
    )


def monthly_and_year_totals(
    umsatz_map: dict,
    mas,
    year: int,
    through_month: int = 12,
) -> tuple[list[int | None], int]:
    """Monatssummen und Jahrestotal — nur bis through_month (Rest = None)."""
    monthly: list[int | None] = []
    for m in range(1, 13):
        if m > through_month:
            monthly.append(None)
            continue
        employed = filter_employed_mas(mas, year, m)
        monthly.append(round(sum_umsatz_for_month(umsatz_map, employed, m)))
    return monthly, sum(v for v in monthly if v is not None)
