from __future__ import annotations

import csv
import io
from decimal import Decimal

from signal_research.domain.schemas import ResearchReport


def spreadsheet_safe(value: object) -> str:
    text = "" if value is None else str(value)
    # Validated numeric values remain usable as numbers (including losses).
    # Strings from documents remain untrusted even if they resemble a number.
    if isinstance(value, Decimal) and value.is_finite():
        return text
    return "'" + text if text.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")) else text


def facts_csv(report: ResearchReport) -> str:
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["id", "metric_key", "value_raw", "value_decimal", "unit", "unit_raw", "currency", "period_start", "period_end", "period_type", "scope", "segment", "definition_id", "status", "passage_id"])
    for fact in report.facts:
        writer.writerow([spreadsheet_safe(value) for value in (fact.id, fact.metric_key, fact.value_raw, fact.value_decimal,
            fact.unit_normalized, fact.unit_raw, fact.currency, fact.period_start, fact.period_end, fact.period_type,
            fact.scope, fact.segment, fact.definition_id, fact.status, fact.passage_id)])
    return stream.getvalue()
