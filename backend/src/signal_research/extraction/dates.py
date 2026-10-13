"""Complete source dates offered to constrained fact extraction."""
import calendar
import re
from datetime import date, datetime

MONTH_NAMES = "|".join(calendar.month_name[1:] + calendar.month_abbr[1:])
COMPLETE_DATE = re.compile(
    r"(?<!\w)(?:\d{4}-\d{2}-\d{2}|\d{1,2}[./-]\d{1,2}[./-]\d{4}|"
    r"\d{1,2}[-/ ](?:" + MONTH_NAMES + r")[-/ ]\d{4}|(?:" + MONTH_NAMES + r")\s+\d{1,2}\s+\d{4})(?!\w)", re.I)


def source_dates(text):
    normalized = re.sub(r"(?<=\d)(?:st|nd|rd|th)\b", "", text, flags=re.I)
    # Explicit day/month/'YY notation in contemporary Indian disclosures.
    # Bare FY27 or Q1FY27 still cannot establish any reporting date.
    normalized = re.sub(r"\b(\d{1,2})\s+(" + MONTH_NAMES + r")[’']\s*(\d{2})(?!\d)",
                        lambda m: f"{m[1]} {m[2]} 20{m[3]}", normalized, flags=re.I)
    normalized = normalized.replace(",", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    result = set()
    for match in COMPLETE_DATE.finditer(normalized):
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y", "%d-%b-%Y", "%d-%B-%Y", "%d/%b/%Y", "%d/%B/%Y", "%B %d %Y", "%b %d %Y"):
            try:
                result.add(datetime.strptime(match[0], fmt).date())
                break
            except ValueError:
                continue
    return sorted(result)


def declared_duration_periods(text):
    """Normalize an explicit duration plus full end date, never a bare FY label.

    'Year ended 31 March 2026' explicitly denotes the twelve calendar months
    starting 1 April 2025. Ambiguous/mixed headings are deliberately not expanded.
    """
    normalized = re.sub(r"(?<=\d)(?:st|nd|rd|th)\b", "", text, flags=re.I)
    normalized = re.sub(r"\s+", " ", normalized.replace(',', ' '))
    # A uniform comparative header ('Year ended <date> | <date>') applies
    # the explicitly stated duration to each date column on that header line.
    # Mixed quarter/year headers are deliberately not expanded.
    for line in text.splitlines():
        labels = re.findall(r"\b(year|quarter|three months|six months|nine months|twelve months|3 months|6 months|9 months|12 months)\s+ended\b", line, re.I)
        matches = list(COMPLETE_DATE.finditer(line.replace(',', ' ')))
        if len(matches) >= 2 and len({label.lower() for label in labels}) == 1:
            remainder = COMPLETE_DATE.sub('', line.replace(',', ' '))
            remainder = re.sub(r"\b(?:" + re.escape(labels[0]) + r")\s+ended|audited|unaudited", '', remainder, flags=re.I)
            if not remainder.strip(' |:()\t'):
                normalized += ' ' + '; '.join(f'{labels[0]} ended {match[0]}' for match in matches)
    # 'Quarter and nine months ended <complete date>' explicitly supplies both
    # durations. It must not be mistaken for a bare fiscal-quarter label.
    duration = r"year|quarter|three months|six months|nine months|twelve months|3 months|6 months|9 months|12 months"
    normalized = re.sub(r"\b(" + duration + r")\s+(?:and|&)\s+(" + duration + r")\s+ended\s*(" + COMPLETE_DATE.pattern + r")",
                        lambda m: f"{m[1]} ended {m[3]}; {m[2]} ended {m[3]}", normalized, flags=re.I)
    periods = []
    for match in re.finditer(r"\b(year|quarter|three months|six months|nine months|twelve months|3 months|6 months|9 months|12 months)\s+ended\s*[:\-]?\s*", normalized, re.I):
        end_match = COMPLETE_DATE.match(normalized, match.end())
        if not end_match:
            continue
        ends = source_dates(end_match[0])
        if len(ends) != 1:
            continue
        end = ends[0]
        if end.day != calendar.monthrange(end.year, end.month)[1]:
            continue
        label = match[1].lower()
        months = {'year': 12, 'quarter': 3, 'three months': 3, 'six months': 6,
                  'nine months': 9, 'twelve months': 12, '3 months': 3,
                  '6 months': 6, '9 months': 9, '12 months': 12}[label]
        index = end.year * 12 + end.month - months
        start = date(index // 12, index % 12 + 1, 1)
        periods.append({'period_start': start, 'period_end': end, 'source_label': match[0] + end_match[0]})
    return periods
