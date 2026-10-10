"""Bind explicit bank balance columns without inventing dates or financial scope."""
from __future__ import annotations

import calendar
import re
from datetime import date
from decimal import Decimal

from .models import ExtractedFactBatch, ExtractedFactCandidate

MONTHS = {name.lower(): index for index in range(1, 13)
          for name in (calendar.month_abbr[index], calendar.month_name[index])}
MONTH_COLUMN = re.compile(r"\b(" + "|".join(MONTHS) + r")\.?\s+(20\d{2}|\d{2})(?!\d)\b", re.I)


def subsidiary_only(text: str) -> bool:
    return bool(re.search(r"regional\s+rural\s+banks[\s\S]{0,100}sponsored\s+by", text, re.I)
                or re.search(r"(?im)^\s*(?:audit review\s+)?employee welfare trust\b", text))


def scope_in_text(scope, text: str) -> bool:
    label = getattr(scope, "value", scope)
    if re.search(r"\b" + re.escape(label) + r"\b", text, re.I):
        return True
    alias = {"standalone": r"\bSBI\s+SOLO\b", "consolidated": r"\bSBI\s+GROUP\b"}.get(label)
    return bool(alias and re.search(alias, text, re.I))


def month_end_columns(text: str) -> list[tuple[str, date]]:
    # A lone month, quarter or FY label never supplies an exact reporting date.
    # Only comparative stock-balance column headers authorize month-end dates.
    if subsidiary_only(text) or not re.search(r"\bbalance\s*sheet\b", text, re.I):
        return []
    if not any(scope_in_text(scope, text) for scope in ("standalone", "consolidated")):
        return []
    for line in text.splitlines():
        matches = list(MONTH_COLUMN.finditer(line))
        if len(matches) < 2:
            continue
        if any(len(match[2]) == 2 for match in matches) and not re.search(r"\bYOY\b|year[- ]on[- ]year", line, re.I):
            continue  # Two-digit labels need an explicit year-comparison header.
        columns = []
        for match in matches:
            year = int(match[2]) + (2000 if len(match[2]) == 2 else 0)
            month = MONTHS[match[1].lower()]
            columns.append((match[0], date(year, month, calendar.monthrange(year, month)[1])))
        return columns
    return []


def comparative_bank_batch(passage, company) -> ExtractedFactBatch | None:
    """Bind unambiguous comparative stock tables; all candidates still need review."""
    text = passage.text
    if subsidiary_only(text):
        return None
    if company.legal_name != "State Bank of India" or not re.search(r"SBI\s+SOLO\s+SBI\s+GROUP", text, re.I):
        return _explicit_bank_balance(passage, company)
    if not re.search(r"SBI\s+SOLO\s+SBI\s+GROUP", text, re.I):
        return None
    if not re.search(r"(?:\u20b9|INR|Rs\.?)\s+in\s+Crores?\b", text, re.I):
        return None
    if len(re.findall(r"YOY\s+Growth\s*\(\s*%\s*\)", text, re.I)) < 2:
        return None
    columns = month_end_columns(text)
    if len(columns) != 4 or [d for _, d in columns[:2]] != [d for _, d in columns[2:]]:
        return None
    if columns[0][1] == columns[1][1]:
        return None
    facts = []
    for metric, label in (("deposits", "Deposits"), ("borrowings", "Borrowings"), ("gross_advances", "Gross Advances")):
        rows = re.findall(r"(?im)^\s*" + re.escape(label) + r"\s+([^\n]+)$", text)
        if len(rows) != 1:
            continue
        cells = re.findall(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?(?![\w.])", rows[0])
        # Two balances and a YoY percentage per scope. Never treat net advances
        # as gross advances, or a percentage as an amount.
        if len(cells) != 6:
            continue
        for index in sorted(range(2), key=lambda i: columns[i][1], reverse=True):
            facts.append(ExtractedFactCandidate(metric_key=metric, value_raw=cells[index],
                unit_raw="INR crore", currency="INR", period_end=columns[index][1],
                scope="standalone", passage_id=passage.id, extraction_confidence=Decimal(".99")))
        if len(facts) == 6:
            break
    return ExtractedFactBatch(facts=facts, notes=["Values bound to explicit SBI SOLO comparative balance columns."]) if facts else None


def _explicit_bank_balance(passage, company) -> ExtractedFactBatch | None:
    """Common issuer balance tables with full dates and one explicit scope."""
    text = passage.text
    if not re.search(r"\bbalance\s*sheet\b|\bstatement\s+of\s+assets\s+and\s+liabilities\b", text, re.I):
        return None
    # An issuer website may also host subsidiary reports. Do not automatically
    # assign a table without its issuer identity and an explicit financial scope.
    if not re.search(r"\b" + re.escape(company.legal_name) + r"\b", text, re.I):
        return None
    if not re.search(r"(?:\u20b9|INR|Rs\.?)\s*(?:in\s+)?(?:crores?|cr)\b", text, re.I):
        return None
    header = None
    columns = []
    for line in text.splitlines():
        labels = re.findall(r"(?<!\d)\d{2}[./-]\d{2}[./-]20\d{2}(?!\d)", line)
        if len(labels) < 2 or not re.search(r"\bas\s+(?:on|at)\b", line, re.I):
            continue
        try:
            columns = [date(int(label[6:]), int(label[3:5]), int(label[:2])) for label in labels]
        except ValueError:
            return None
        if len(set(columns)) != len(columns):
            return None
        header = line
        break
    if header is None:
        return None
    prefix = text.split(header, 1)[0]
    scopes = [scope for scope in ("standalone", "consolidated") if scope_in_text(scope, prefix)]
    if len(scopes) != 1:
        return None
    latest = max(columns)
    # Prefer a year comparison over mixing quarters when both are available.
    previous = next((d for d in columns if d.year == latest.year - 1 and (d.month, d.day) == (latest.month, latest.day)),
                    max(d for d in columns if d < latest))
    facts = []
    for metric, label in (("deposits", "Deposits"), ("borrowings", "Borrowings")):
        rows = re.findall(r"(?im)^\s*(?:Total\s+)?" + label + r"\s+([^\n]+)$", text)
        if len(rows) != 1:
            continue
        cells = re.findall(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?(?![\w.])", rows[0])
        if len(cells) != len(columns):
            continue  # Growth percentages, footnotes and broken columns are ambiguous.
        for period in (latest, previous):
            facts.append(ExtractedFactCandidate(metric_key=metric, value_raw=cells[columns.index(period)],
                unit_raw="INR crore", currency="INR", period_end=period, scope=scopes[0],
                passage_id=passage.id, extraction_confidence=Decimal(".99")))
    return ExtractedFactBatch(facts=facts, notes=["Values bound to explicit dated issuer balance columns and financial scope."]) if facts else None
