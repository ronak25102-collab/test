"""Recognize column-oriented numeric leads without accepting any financial fact."""
import re

from signal_research.finance.registry import metrics_for_profile

from .bank_tables import scope_in_text, subsidiary_only
from .dates import source_dates
from .eligibility import minimum_source_bindings

NUMERIC_CELL = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?\s*%?(?![\w.])")


def column_metric_lead(passage, profile):
    """Allow independent model extraction of explicitly dated metric columns.

    This is only a ranking/eligibility hint. It creates no candidates and cannot
    bypass issuer identity, value/date binding or independent source review.
    """
    text = passage.text
    if subsidiary_only(text) or not minimum_source_bindings(passage, profile):
        return False
    if sum(scope_in_text(scope, text) for scope in ("standalone", "consolidated")) != 1:
        return False
    metrics = metrics_for_profile(profile)
    lines = text.splitlines()
    for index, line in enumerate(lines):
        total = re.fullmatch(r"\s*Total\s*[:|]?\s+(.+)", line, re.I)
        if not total:
            continue
        tail = total[1]
        values = NUMERIC_CELL.findall(tail)
        if len(values) < 2 or NUMERIC_CELL.sub("", tail).strip(" |\t"):
            continue
        for header_index, header in enumerate(lines[:index]):
            if len(header) > 180 or re.search(r"\d", header):
                continue
            columns = {metric.key for metric in metrics
                       if any(re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", header, re.I)
                              for alias in (*metric.aliases, metric.key.replace("_", " ")))}
            if len(columns) < 2 or len(values) < len(columns):
                continue
            # A footnote date elsewhere on the page cannot stand in for a dated header.
            nearby_header = "\n".join(lines[max(0, header_index - 2):min(index, header_index + 5)])
            if source_dates(nearby_header):
                return True
    return False
