from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class FiscalPeriod:
    label: str
    start: date
    end: date
    period_type: str = "duration"


def quarter(label: str, fiscal_year_end_month: int = 3, fiscal_year_end_day: int = 31) -> FiscalPeriod:
    match = re.fullmatch(r"Q([1-4])\s*FY(\d{4})", label.strip().upper())
    if not match:
        raise ValueError(f"invalid fiscal quarter: {label}")
    q, fy = int(match.group(1)), int(match.group(2))
    # FY2027 for a March year end begins in April 2026.
    end_year = fy if fiscal_year_end_month != 3 else fy
    if fiscal_year_end_month == 3:
        starts = [date(end_year - 1, 4, 1), date(end_year - 1, 7, 1), date(end_year - 1, 10, 1), date(end_year, 1, 1)]
        ends = [date(end_year - 1, 6, 30), date(end_year - 1, 9, 30), date(end_year - 1, 12, 31), date(end_year, 3, fiscal_year_end_day)]
    else:
        # General fallback for a non-March fiscal year; month arithmetic stays explicit.
        start_month = fiscal_year_end_month + 1 if fiscal_year_end_month < 12 else 1
        start_year = end_year - 1 if fiscal_year_end_month != 12 else end_year
        starts = []
        ends = []
        for index in range(4):
            month = ((start_month - 1) + index * 3) % 12 + 1
            year = start_year + ((start_month - 1) + index * 3) // 12
            starts.append(date(year, month, 1))
            next_month = month + 3
            next_year = year + (next_month - 1) // 12
            next_month = (next_month - 1) % 12 + 1
            ends.append(date(next_year, next_month, 1) - timedelta(days=1))
    return FiscalPeriod(label.upper(), starts[q - 1], ends[q - 1])


def fiscal_year(label: str, fiscal_year_end_month: int = 3, fiscal_year_end_day: int = 31) -> FiscalPeriod:
    match = re.fullmatch(r"FY(\d{4})", label.strip().upper())
    if not match:
        raise ValueError(f"invalid fiscal year: {label}")
    year = int(match.group(1))
    if fiscal_year_end_month == 3:
        return FiscalPeriod(label.upper(), date(year - 1, 4, 1), date(year, 3, fiscal_year_end_day))
    end = date(year, fiscal_year_end_month, fiscal_year_end_day)
    start_year = year - 1 if fiscal_year_end_month != 12 else year
    start_month = fiscal_year_end_month + 1 if fiscal_year_end_month < 12 else 1
    return FiscalPeriod(label.upper(), date(start_year, start_month, 1), end)


def derive_quarter_flow(cumulative: Decimal, prior_cumulative: Decimal, same_definition: bool = True) -> Decimal:
    if not same_definition:
        raise ValueError("cumulative flows are not comparable")
    return cumulative - prior_cumulative
