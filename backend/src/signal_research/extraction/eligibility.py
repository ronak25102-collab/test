"""Skip model calls on pages that cannot meet the existing fact-binding rules."""
import re

from signal_research.domain.enums import Profile
from signal_research.extraction.bank_tables import month_end_columns, scope_in_text
from signal_research.extraction.dates import abbreviated_quarter_periods, source_dates


def minimum_source_bindings(passage, profile):
    text = passage.text
    if not any(scope_in_text(scope, text) for scope in ('standalone', 'consolidated', 'segment')):
        return False
    if not source_dates(text) and not abbreviated_quarter_periods(text) and not (profile == Profile.BANK and month_end_columns(text)):
        return False
    # A model cannot recover an absent currency mark or scale from prior knowledge.
    # This is a necessary condition only, never acceptance of the page's figures.
    percent = bool(re.search(r'%|\bpercent', text, re.I))
    currency = bool(re.search(r'\b(?:INR|Rs|rupees)\b|₹', text, re.I))
    scale = bool(re.search(r'\b(?:crores?|cr|lakhs?|millions?|billions?|trillions?|thousands?|rupees)\b|\bin\s*[‘’\x27]?000\b', text, re.I))
    return percent or (currency and scale)
