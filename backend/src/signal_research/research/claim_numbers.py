"""Reject generated numerical detail that is absent from its own verified lineage."""
import re
from decimal import Decimal, InvalidOperation

from signal_research.research.headline import number_tokens


def supported_numbers(text, facts, calculations):
    dates = [d for f in facts for d in (f.period_start, f.period_end) if d]
    allowed = {Decimal(component) for d in dates for component in (d.year, d.month, d.day)}
    allowed.update(f.value_decimal for f in facts if f.value_decimal is not None)
    allowed.update(c.output_value for c in calculations if c.available and c.output_value is not None)
    for fact in facts:
        try:
            allowed.add(Decimal((fact.value_raw or '').replace(',', '')))
        except InvalidOperation:
            pass
    # Permit an explicitly stated rounded rendering, not a new estimate.
    allowed |= {v.quantize(Decimal('1').scaleb(-precision)) for v in allowed for precision in (0, 1, 2)}
    normalized = text.replace('−', '-').replace('–', '-')
    normalized = re.sub(r'\bFY(?=20\d{2})', '', normalized, flags=re.I)
    normalized = re.sub(r'\b(20\d{2})-(\d{2})-(\d{2})\b', r'\1 \2 \3', normalized)
    normalized = re.sub(r'\b(20\d{2})-(\d{2})\b', lambda m: m[1] + ' ' + m[1][:2] + m[2], normalized)
    normalized = re.sub(r'(?<=\d)-(?=\d)', ' ', normalized)  # Explicit dates/ranges, not subtraction.
    values = number_tokens(normalized)
    if re.search(r'\b(?:declin|fell|decreas|reduc|drop|slower|down|shrank|contract)', text, re.I):
        allowed |= {abs(v) for v in allowed}
    return all(value in allowed for value in values)
