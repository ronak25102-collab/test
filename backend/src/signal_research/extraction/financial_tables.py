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
from .dates import (
    COMPLETE_DATE,
    abbreviated_quarter_periods,
    declared_duration_periods,
    source_dates,
)
from .models import ExtractedFactBatch, ExtractedFactCandidate

NUMBER = re.compile(r"(?<![\w.])\(?-?\d[\d,]*(?:\.\d+)?\)?%?(?![\w.])")
DURATION = re.compile(r"\b(year|quarter|three months|six months|nine months|twelve months|3 months|6 months|9 months|12 months)\s+ended\b", re.I)


def quarter_presentation_batch(passage, company, profile, *, document_issuer_verified=False):
    """Literal leading quarter columns in mixed quarter/YTD presentation tables.

    Only explicitly labelled quarter columns are normalized. Fiscal/YTD cells
    are counted to verify table width, then omitted, never assigned guessed dates.
    Candidates still require the independent source review.
    """
    text = passage.text
    if subsidiary_only(text) or not (document_issuer_verified or issuer_named(text, company)):
        return None
    periods = abbreviated_quarter_periods(text)
    if not periods:
        return None
    lines = text.splitlines()
    headers = [(i, line) for i, line in enumerate(lines) if len(re.findall(r'\bQuarter\b', line, re.I)) == len(periods)]
    if len(headers) != 1:
        return None
    header_index, header = headers[0]
    # Columns must begin with quarter labels. Other layouts need model review.
    if not re.match(r'^\s*(?:Quarter\s+){' + str(len(periods)) + '}', header, re.I):
        return None
    total_columns = len(periods) + len(re.findall(r'\b20\d{2}-\d{2}\b', header))
    prefix = '\n'.join(lines[:header_index + 1])
    unit = re.search(r'(?:₹|INR|Rs\.?)\s*(?:in\s+)?(crores?|cr|lakhs?|millions?|billions?|thousands?)\b', prefix, re.I)
    if not unit:
        return None
    scope = 'consolidated' if scope_in_text('consolidated', prefix) else 'standalone'
    facts = []
    for metric in metrics_for_profile(profile):
        if metric.kind == 'stock' or metric.unit != 'INR_crore':
            continue
        aliases = sorted((*metric.aliases, metric.key.replace('_', ' ')), key=len, reverse=True)
        rows = []
        for line in lines[header_index + 1:]:
            for alias in sorted(aliases, key=len, reverse=True):
                match = re.match(r'^\s*(?:\d+[.)]?\s+)?' + re.escape(alias) +
                                 r'\s*(?:\([\d+\-*/ .]+\))?\s+(.+)$', line, re.I)
                if not match:
                    continue
                cells = NUMBER.findall(match[1])
                if not NUMBER.sub('', match[1]).strip() and len(cells) == total_columns:
                    rows.append(cells)
                break
        if len(rows) != 1:
            continue
        for period, cell in zip(periods, rows[0][:len(periods)], strict=True):
            facts.append(ExtractedFactCandidate(metric_key=metric.key, value_raw=cell, unit_raw='INR ' + unit[1],
                currency='INR', period_type='duration', period_start=period['period_start'], period_end=period['period_end'],
                scope=scope, passage_id=passage.id, extraction_confidence=Decimal('.99')))
            if len(facts) == 6:
                return ExtractedFactBatch(facts=facts, notes=['Literal quarter columns; YTD/FY cells omitted; independent review required.'])
    return ExtractedFactBatch(facts=facts) if facts else None


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
    explicit_columns = []
    if passage.extraction_method == 'html_table' and (passage.column_label or '').startswith('Period columns: '):
        for label in passage.column_label.removeprefix('Period columns: ').split(' | '):
            dates_in_column = source_dates(label)
            durations = declared_duration_periods(label)
            if len(dates_in_column) != 1 or len(durations) > 1:
                return None
            explicit_columns.append((dates_in_column[0], durations[0]['period_start'] if durations else None))
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
    if explicit_columns:
        dates = [period for period, _ in explicit_columns]
        duration = None
    elif len(headers) != 1:
        return None
    else:
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
        if metric.kind != 'stock' and duration is None and not explicit_columns:
            continue
        indices = sorted(range(len(dates)), key=lambda index: dates[index], reverse=True)
        if explicit_columns:
            newest = indices[0]
            end, start = explicit_columns[newest]
            indices = [index for index in indices
                       if (dates[index].month, dates[index].day) == (end.month, end.day)
                       and ((explicit_columns[index][1].month, explicit_columns[index][1].day)
                            if explicit_columns[index][1] else None) ==
                       ((start.month, start.day) if start else None)][:3]
        for index in indices:
            period = dates[index]
            periods = declared_duration_periods(f'{duration} ended {period.isoformat()}') if duration else []
            start = explicit_columns[index][1] if explicit_columns else periods[0]['period_start'] if periods else None
            if metric.kind != 'stock' and start is None:
                continue
            if metric.kind == 'stock' and explicit_columns and start is not None:
                continue  # A duration table does not establish an instant stock.
            facts.append(ExtractedFactCandidate(
                metric_key=metric.key, value_raw=cells[index], unit_raw=unit_raw,
                currency=currency, period_end=period,
                period_start=start if metric.kind != 'stock' else None,
                period_type='instant' if metric.kind == 'stock' else 'duration',
                scope=scopes[0], passage_id=passage.id, extraction_confidence=Decimal('.99')))
            if len(facts) == 6:
                return ExtractedFactBatch(facts=facts, notes=['Explicit financial table columns; independent source review required.'])
    return ExtractedFactBatch(facts=facts, notes=['Explicit financial table columns; independent source review required.']) if facts else None
