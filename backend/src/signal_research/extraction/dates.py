"""Complete source dates offered to constrained fact extraction."""
import calendar
import re
from datetime import datetime

MONTH_NAMES = "|".join(calendar.month_name[1:] + calendar.month_abbr[1:])
COMPLETE_DATE = re.compile(
    r"(?<!\w)(?:\d{4}-\d{2}-\d{2}|\d{1,2}[./-]\d{1,2}[./-]\d{4}|"
    r"\d{1,2}\s+(?:" + MONTH_NAMES + r")\s+\d{4}|(?:" + MONTH_NAMES + r")\s+\d{1,2}\s+\d{4})(?!\w)", re.I)


def source_dates(text):
    normalized = re.sub(r"(?<=\d)(?:st|nd|rd|th)\b", "", text, flags=re.I)
    normalized = normalized.replace(",", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    result = set()
    for match in COMPLETE_DATE.finditer(normalized):
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"):
            try:
                result.add(datetime.strptime(match[0], fmt).date())
                break
            except ValueError:
                continue
    return sorted(result)
