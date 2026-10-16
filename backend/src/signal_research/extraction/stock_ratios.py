"""Propose source-bound instant ratios from explicitly dated financial tables.

Quarter and year columns can share a reporting date for a stock ratio. Equal
duplicate cells are deduplicated; conflicting duplicates are never resolved by
guessing. These are extraction candidates, still subject to source validation
and the independent model review in the live pipeline.
"""
from __future__ import annotations

import re
from decimal import Decimal

from signal_research.finance.registry import metrics_for_profile
from signal_research.finance.units import parse_numeric
from signal_research.research.identity import foreign_cover_identity, issuer_named

from .bank_tables import scope_in_text, subsidiary_only
from .dates import COMPLETE_DATE, source_dates
from .models import ExtractedFactBatch, ExtractedFactCandidate

PERCENT_CELL = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?\s*%(?!\w)")
ROW_PREFIX = r"\s*(?:(?:\([a-zivx]+\)|[a-zivx]+[.)]|\d+[.)])\s*)?"


def stock_ratio_batch(passage, company, profile, *, document_issuer_verified=False, focus_metrics=()):
    """Bind registered stock percentages only, retaining at most nine candidates."""
    text = passage.text
    if subsidiary_only(text) or foreign_cover_identity(text, company):
        return None
    if not (document_issuer_verified or issuer_named(text, company)):
        return None
    scopes = [scope for scope in ('standalone', 'consolidated') if scope_in_text(scope, text)]
    if len(scopes) != 1:
        return None
    metrics = [metric for metric in metrics_for_profile(profile)
               if metric.kind == 'stock' and metric.unit == 'percent']
    aliases = sorted(((alias, metric) for metric in metrics
                      for alias in (*metric.aliases, metric.key.replace('_', ' '))),
                     key=lambda item: len(item[0]), reverse=True)
    rows = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        for alias, metric in aliases:
            label = r'\s+'.join(re.escape(word) for word in alias.split())
            match = re.fullmatch(ROW_PREFIX + label + r'(?!\w)\s*(?:\(%\)|\(percent\))?\s*[:|]?\s*(.+)', line, re.I)
            if not match:
                continue
            tail = match[1]
            cells = PERCENT_CELL.findall(tail)
            if cells and not PERCENT_CELL.sub('', tail).strip(' |\t'):
                rows.append((index, metric, cells))
            break  # A shorter overlapping alias cannot reinterpret this row.
    if not rows:
        return None
    headers = []
    for line in lines[:min(index for index, _, _ in rows)]:
        normalized = line.replace(',', ' ')
        labels = [match[0] for match in COMPLETE_DATE.finditer(normalized)]
        if len(labels) >= 2:
            parsed = [source_dates(label) for label in labels]
            if any(len(periods) != 1 for periods in parsed):
                return None
            headers.append([periods[0] for periods in parsed])
    if len(headers) != 1 or len(set(headers[0])) < 2:
        return None
    columns = headers[0]
    priority = {key: index for index, key in enumerate(focus_metrics)}
    rows.sort(key=lambda row: priority.get(row[1].key, len(priority)))
    facts = []
    for _, metric, cells in rows:
        if len(cells) != len(columns) or sum(row[1].key == metric.key for row in rows) != 1:
            continue
        values = [parse_numeric(cell).value for cell in cells]
        if any(value is None for value in values):
            continue
        if any(values[index] != values[other] for index, period in enumerate(columns)
               for other in range(index) if columns[other] == period):
            continue  # Quarter/year duplicates disagree: the whole row is ambiguous.
        for period in sorted(set(columns), reverse=True)[:3]:
            facts.append(ExtractedFactCandidate(
                metric_key=metric.key, value_raw=cells[columns.index(period)],
                unit_raw='percent', currency=None, period_end=period,
                period_type='instant', scope=scopes[0], passage_id=passage.id,
                extraction_confidence=Decimal('.99')))
            if len(facts) == 9:
                break
        if len(facts) == 9:
            break
    return ExtractedFactBatch(facts=facts, notes=[
        'Explicit dated stock-percentage columns; identical duplicate dates deduplicated; independent review required.'
    ]) if facts else None
