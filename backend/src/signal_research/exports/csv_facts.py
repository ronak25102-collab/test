from __future__ import annotations

import csv
import io

from signal_research.domain.schemas import ResearchReport


def spreadsheet_safe(value: object) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text


def facts_csv(report: ResearchReport) -> str:
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["id", "metric_key", "value_raw", "value_decimal", "unit", "period_end", "scope", "status"])
    for fact in report.facts:
        writer.writerow([spreadsheet_safe(fact.id), spreadsheet_safe(fact.metric_key), spreadsheet_safe(fact.value_raw), spreadsheet_safe(fact.value_decimal), spreadsheet_safe(fact.unit_normalized), spreadsheet_safe(fact.period_end), spreadsheet_safe(fact.scope), spreadsheet_safe(fact.status)])
    return stream.getvalue()
