"""Bind explicit financial-table columns across issuer business types.

This produces candidates, never verified facts. Exact-source validation and the
independent row/column review remain mandatory in the live pipeline.
"""
from __future__ import annotations

import re
from decimal import Decimal

from signal_research.finance.registry import metrics_for_profile
from signal_research.finance.units import parse_numeric
from signal_research.research.identity import issuer_named

from .bank_tables import scope_in_text, subsidiary_only
from .dates import COMPLETE_DATE, declared_duration_periods, source_dates
from .models import ExtractedFactBatch, ExtractedFactCandidate

NUMBER = re.compile(r"(?<![\w.])\(?-?\d[\d,]*(?:\.\d+)?\)?%?(?![\w.])")
DURATION = re.compile(r"\b(year|quarter|three months|six months|nine months|twelve months|3 months|6 months|9 months|12 months)\s+ended\b", re.I)


def financial_table_batch(passage, company, profile, *, document_issuer_verified=False):
    text = passage.text
    if subsidiary_only(text) or not (document_issuer_verified or issuer_named(text, company)):
        return None
    lines = text.splitlines()
    metrics = metrics_for_profile(profile)
    rows = []
    for index, line in enumerate(lines):
        for metric in metrics:
            for alias in (*metric.aliases, metric.key.replace('_', ' ')):
                match = re.match(r"\s*(?:\d+[.)]\s+)?" + re.escape(alias) +
                                 r"\s*(?:\(%\)|\(percent\))?\s*(?:\||:|\s)\s*(.*)$", line, re.I)
                if match and NUMBER.search(match[1]):
                    rows.append((index, metric, line, match[1]))
                    break
    if not rows:
        return None
    prefix = '\n'.join(lines[:min(row[0] for row in rows)])
    scopes = [scope for scope in ('standalone', 'consolidated') if scope_in_text(scope, prefix)]
    if len(scopes) != 1:
        return None  # Mixed scope columns require explicit geometry, never a guess.
    headers = []
    for index, line in enumerate(prefix.splitlines()):
        normalized = line.replace(',', ' ')
        labels = [match[0] for match in COMPLETE_DATE.finditer(normalized)]
        if len(labels) >= 2:
            dates = [source_dates(label)[0] for label in labels]
            if len(set(dates)) != len(dates):
                continue
            heading = '\n'.join(prefix.splitlines()[max(0, index - 2):index + 1])
            durations = list(DURATION.finditer(heading))
            duration_labels = {match[1].lower() for match in durations}
            headers.append((dates, next(iter(duration_labels)) if len(duration_labels) == 1 else None))
    if len(headers) != 1:
        return None
    dates, duration = headers[0]
    unit = re.search(r"(?:\u20b9|INR|Rs\.?|rupees)\s*(?:in\s+)?(crores?|cr|lakhs?|millions?|billions?|thousands?|['\u2018\u2019]?000)\b", prefix, re.I)
    facts = []
    # Resolve overlapping aliases conservatively. One labelled row per metric.
    for _, metric, line, tail in rows:
        if sum(row[1].key == metric.key for row in rows) != 1:
            continue
        cells = NUMBER.findall(tail)
        residual = NUMBER.sub('', tail).strip(' |\t')
        if residual or len(cells) != len(dates) or any(parse_numeric(cell).value is None for cell in cells):
            continue
        if metric.unit == 'percent':
            if '%' not in line and 'percent' not in line.lower():
                continue  # NPA amounts are not NPA ratios.
            unit_raw, currency = 'percent', None
        elif metric.unit == 'INR_crore' and unit:
            scale = 'thousand' if re.search(r'000|thousand', unit[1], re.I) else unit[1]
            unit_raw, currency = 'INR ' + scale, 'INR'
        else:
            continue
        if metric.kind != 'stock' and duration is None:
            continue
        for period in sorted(dates, reverse=True):
            periods = declared_duration_periods(f'{duration} ended {period.isoformat()}') if duration else []
            if metric.kind != 'stock' and len(periods) != 1:
                continue
            facts.append(ExtractedFactCandidate(
                metric_key=metric.key, value_raw=cells[dates.index(period)], unit_raw=unit_raw,
                currency=currency, period_end=period,
                period_start=periods[0]['period_start'] if metric.kind != 'stock' else None,
                period_type='instant' if metric.kind == 'stock' else 'duration',
                scope=scopes[0], passage_id=passage.id, extraction_confidence=Decimal('.99')))
            if len(facts) == 6:
                return ExtractedFactBatch(facts=facts, notes=['Explicit financial table columns; independent source review required.'])
    return ExtractedFactBatch(facts=facts, notes=['Explicit financial table columns; independent source review required.']) if facts else None
