"""Publication-date sanity, mirror attribution and consistent presentation numbers."""
import re
from datetime import date
from decimal import Decimal

from signal_research.extraction.dates import source_dates
from signal_research.retrieval.metadata import source_publication


def financial_period_end(title, text):
    explicit = []
    for match in re.finditer(r'(?:year|quarter|period)\s+ended\s+([^\n;]{5,45})', text[:12000], re.I):
        explicit.extend(source_dates(match[1]))
    if explicit:
        return max(explicit)
    annual = re.search(r'annual\s+report[^\n]{0,30}?(20\d{2})\s*[-–/]\s*(\d{2,4})\b', title + '\n' + text[:1000], re.I)
    if annual:
        year = int(annual[2]) if len(annual[2]) == 4 else int(annual[1][:2] + annual[2])
        return date(year, 3, 31)
    return None


def sane_publication(raw, text, title, published):
    end = financial_period_end(title, text)
    if published and end and published.date() < end:
        cover = source_publication(raw, text[:3000])
        return (cover if cover and cover.date() >= end else None,
                'Publication metadata predates the financial period; only a valid source-owned cover date may replace it, otherwise the date is unknown.')
    return published, None


def indian_number(value):
    value = Decimal(str(value))
    raw = f'{abs(value):.2f}'
    whole, frac = raw.split('.')
    tail, lead = whole[-3:], whole[:-3]
    groups = []
    while lead:
        groups.insert(0, lead[-2:])
        lead = lead[:-2]
    return ('-' if value < 0 else '') + ','.join([*groups, tail]) + '.' + frac


def format_prose(text):
    # Source quotations and stored evidence are never rewritten. Apply only to
    # generated presentation text before its final entailment review.
    return re.sub(r'(?<![\w.])(-?\d[\d,]*\.\d{3,})(?![\w.])',
                  lambda m: indian_number(m[1].replace(',', '')), text)
