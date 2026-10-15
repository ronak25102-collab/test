"""Preserve explicit periods and units in exchange-rendered financial tables.

Each output column retains its own start, end, scope and source rows. Labels
are not used to infer values, dates or an issuer from a search result.
"""
import re
from uuid import uuid5

from signal_research.domain.schemas import Passage
from signal_research.extraction.dates import source_dates
from signal_research.finance.units import parse_numeric


def exchange_table_passages(document_id, soup):
    tables = soup.find_all('table')
    if not tables:
        return []
    def rows(table):
        return [[cell.get_text(' ', strip=True) for cell in row.find_all(['th', 'td'], recursive=False)]
                for row in table.find_all('tr') if row.find_parent('table') is table]
    general = {}
    for row in rows(tables[0]):
        if len(row) != 2:
            continue
        key, value = row[0].casefold(), row[1]
        if key in general and general[key] != value:
            return []  # Contradictory company/currency metadata is not a binding.
        general[key] = value
    name = general.get('name of company') or general.get('name of the company')
    symbol = general.get('nse symbol')
    currency = general.get('description of presentation currency', '')
    rounding = general.get('level of rounding used in financial results', '')
    if not name or not symbol or currency != 'INR' or not re.fullmatch(r'lakhs?|crores?|rupees|millions?|thousands?', rounding, re.I):
        return []
    identity = f'Name of company | {name}\nNSE Symbol | {symbol}'
    if general.get('isin'):
        identity += '\nISIN | ' + general['isin']
    passages, seen = [], set()
    for index, table in enumerate(tables[1:], 1):
        content = rows(table)
        fields = {}
        conflict = False
        for row in content:
            for label in ('Date of start of reporting period', 'Date of end of reporting period',
                          'Nature of report standalone or consolidated'):
                if label in row:
                    if label in fields and fields[label] != row[row.index(label) + 1:]:
                        conflict = True
                    fields[label] = row[row.index(label) + 1:]
        starts = fields.get('Date of start of reporting period', [])
        ends = fields.get('Date of end of reporting period', [])
        scopes = fields.get('Nature of report standalone or consolidated', [])
        if conflict or not starts or len(starts) != len(ends) or len(ends) != len(scopes):
            continue
        for column, (start, end, scope) in enumerate(zip(starts, ends, scopes, strict=True)):
            start_dates, end_dates = source_dates(start), source_dates(end)
            if len(start_dates) != 1 or len(end_dates) != 1 or start_dates[0] >= end_dates[0]:
                continue
            if scope.casefold() not in {'standalone', 'consolidated'}:
                continue
            # Keep the literal date cells as well as their explicitly bound pair.
            header = (f'{identity}\nAmounts in {currency} {rounding}\n'
                      f'Reporting scope | {scope}\n'
                      f'Date of start of reporting period | {start}\n'
                      f'Date of end of reporting period | {end}\nReporting interval: {start} to {end}')
            body = []
            for row in content:
                if len(row) < len(starts) + 1:
                    continue
                label = ' '.join(row[:-len(starts)]).strip()
                value = row[-len(starts) + column]
                if parse_numeric(value).value is None or any(field in label for field in fields):
                    continue
                body.append(f'{label} | {value}')
            if not body:
                continue
            # Repeat binding metadata when a large table needs multiple passages.
            chunks, chunk, size = [], [], 0
            for line in body:
                if chunk and size + len(line) > 3000:
                    chunks.append(chunk)
                    chunk, size = [], 0
                chunk.append(line)
                size += len(line)
            chunks.append(chunk)
            for part in chunks:
                text = header + '\n' + '\n'.join(part)
                if text in seen:
                    continue  # Q1 and YTD can be the same explicitly reported interval.
                seen.add(text)
                passages.append(Passage(id=uuid5(document_id, f'exchange:{index}:{column}:{text}'),
                    document_id=document_id, text=text, section='Exchange financial filing',
                    table_id=f'exchange:{index}', column_label=f'{start} to {end}',
                    extraction_method='exchange_table', extraction_quality='explicit_source_columns'))
    return passages


def exchange_table_batch(passage, company, profile):
    """Generate literal single-column candidates; independent review is still required."""
    from decimal import Decimal

    from signal_research.extraction.dates import explicit_duration_ranges
    from signal_research.extraction.models import ExtractedFactBatch, ExtractedFactCandidate
    from signal_research.finance.registry import metrics_for_profile
    from signal_research.research.identity import structured_issuer_identity

    if passage.extraction_method != 'exchange_table' or not structured_issuer_identity(passage.text, company):
        return None
    intervals = explicit_duration_ranges(passage.text)
    unit = re.search(r'^Amounts in INR (.+)$', passage.text, re.M)
    scopes = re.findall(r'^Reporting scope\s*\|\s*(.+)$', passage.text, re.M)
    if len(intervals) != 1 or not unit or len(scopes) != 1:
        return None
    def normalized(value):
        return re.sub(r'[^a-z]', '', re.sub(r'^\s*\d+\s+', '', value).lower())
    rows = [line.rsplit('|', 1) for line in passage.text.splitlines() if '|' in line]
    facts = []
    for metric in metrics_for_profile(profile):
        labels = {normalized(alias) for alias in metric.aliases}
        matches = [(label, value.strip()) for label, value in rows if normalized(label) in labels]
        if len(matches) != 1 or parse_numeric(matches[0][1]).value is None or metric.unit != 'INR_crore':
            continue
        facts.append(ExtractedFactCandidate(metric_key=metric.key, value_raw=matches[0][1],
            unit_raw='INR ' + unit[1], currency='INR', scope=scopes[0].lower(),
            period_start=intervals[0]['period_start'] if metric.kind != 'stock' else None,
            period_end=intervals[0]['period_end'], period_type='duration' if metric.kind != 'stock' else 'instant',
            passage_id=passage.id, extraction_confidence=Decimal('1')))
    return ExtractedFactBatch(facts=facts[:20]) if facts else None
