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
    normalized = re.sub(r"(?<![\w’'])(\d{1,2})\s+(" + MONTH_NAMES + r")[’']\s*(\d{2})(?!\d)",
                        lambda m: f"{m[1]} {m[2]} 20{m[3]}", normalized, flags=re.I)
    # An explicit day + month + two-digit year is a complete date, unlike a
    # fiscal label or a row of adjacent month/year columns.
    normalized = re.sub(r'(?<![\w\d])(\d{1,2})[-/](' + MONTH_NAMES + r')[-/](\d{2})(?!\d)',
                        lambda m: f'{m[1]} {m[2]} 20{m[3]}', normalized, flags=re.I)
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


def abbreviated_quarter_periods(text):
    """Normalize explicit comparative month-year + Quarter columns only.

    A bare month/FY label is insufficient. Each month column must have its
    own Quarter label on the following header line in a single-scope income
    statement. Other mixed FY/9M columns remain unbound.
    """
    if not re.search(r'\b(?:profit\s*(?:&|and)\s*loss|income\s+statement)\b', text, re.I):
        return []
    if len(set(re.findall(r'\b(?:standalone|consolidated)\b', text.lower()))) != 1:
        return []
    months = {name.lower(): i for i in range(1, 13)
              for name in (calendar.month_name[i], calendar.month_abbr[i])}
    months['sept'] = 9
    pattern = re.compile(r'\b(' + '|'.join(months) + r")\.?\s*[’']\s*(\d{2})(?!\d)", re.I)
    lines = text.splitlines()
    for index, line in enumerate(lines):
        columns = list(pattern.finditer(line))
        if len(columns) < 2:
            continue
        following = ' '.join(lines[index + 1:index + 3])
        if len(re.findall(r'\bQuarter\b', following, re.I)) != len(columns):
            continue
        periods = []
        for column in columns:
            year, month = 2000 + int(column[2]), months[column[1].lower()]
            # Calendar quarters are explicit; arbitrary month labels remain ambiguous.
            if month not in {3, 6, 9, 12}:
                return []
            end = date(year, month, calendar.monthrange(year, month)[1])
            start_index = year * 12 + month - 3
            periods.append({'period_start': date(start_index // 12, start_index % 12 + 1, 1),
                            'period_end': end, 'source_label': column[0] + ' Quarter'})
        return periods
    return []


def explicit_duration_ranges(text):
    """Both full dates must form one stated interval, not separate columns."""
    normalized = re.sub(r'(?<=\d)(?:st|nd|rd|th)\b', '', text, flags=re.I)
    normalized = re.sub(r'\s+', ' ', normalized.replace(',', ' '))
    date_pattern = COMPLETE_DATE.pattern
    result = []
    for match in re.finditer('(' + date_pattern + r')\s+(?:to|through|until|and)\s+(' + date_pattern + ')', normalized, re.I):
        # 'and' dates require an explicit 'between' interval, so a comparative
        # 'as at <date> and <date>' header cannot supply a duration start.
        if re.search(r'\s+and\s+', match[0], re.I) and not re.search(r'\bbetween\s*$', normalized[max(0, match.start() - 16):match.start()], re.I):
            continue
        starts, ends = source_dates(match[1]), source_dates(match[2])
        if len(starts) == len(ends) == 1 and starts[0] < ends[0]:
            result.append({'period_start': starts[0], 'period_end': ends[0], 'source_label': match[0]})
    return result


def declared_duration_periods(text):
    """Normalize an explicit duration plus full end date, never a bare FY label.

    'Year ended 31 March 2026' explicitly denotes the twelve calendar months
    starting 1 April 2025. Ambiguous/mixed headings are deliberately not expanded.
    """
    text = re.sub(r'\bhalf[ -]+year\b', 'six months', text, flags=re.I)
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
            remainder = re.sub(r"\b(?:" + re.escape(labels[0]) + r")\s+ended|audited|unaudited|particulars|metric|period", '', remainder, flags=re.I)
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


def reviewed_table_column_periods(passage):
    """A reviewed PDF table column must retain its literal source header/date.

    Geometry/editorial review supplies the column label; it cannot supply a date
    or duration absent from the original page. This does not infer mixed columns
    from their textual order.
    """
    if passage.extraction_method != 'pdf_table' or not passage.column_label or not passage.row_label:
        return []
    label = passage.column_label
    match = re.fullmatch(r'\s*(year|quarter|half[ -]+year|six months)\s+ended\s+(.+?)\s*', label, re.I)
    if not match or len(source_dates(match[2])) != 1:
        return []
    original = re.sub(r'\s+', ' ', passage.text).lower()
    header = re.sub(r'\s+', ' ', match[1] + ' ended').lower()
    if header not in original or passage.row_label.lower() not in original:
        return []
    if source_dates(match[2])[0] not in source_dates(passage.text):
        return []
    return declared_duration_periods(label)
