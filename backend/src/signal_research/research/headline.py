"""A bounded plain-English rendering of already reviewed financial arithmetic."""
import re
from decimal import Decimal

NUMBER = r'(?<![\w])[-+]?\d[\d,]*(?:\.\d+)?'


def number_tokens(text):
    return [Decimal(n.replace(',', '')) for n in re.findall(NUMBER, text)]


def validate_headline(text, entity, facts, calculations):
    errors = []
    clean = re.sub(r'\b(?:Ltd|Mr|Dr)\.', lambda m: m[0][:-1], text, flags=re.I)
    clean = re.sub(r'(?<=\d)\.(?=\d)', '', clean)
    if len(re.findall(r'[.!?](?:\s|$)', clean)) != 1 or not re.search(r'[.!?]$', text.strip()):
        errors.append('Exactly one complete sentence is required.')
    if len(text.split()) > 35:
        errors.append('Maximum 35 words.')
    if entity.casefold() not in text.casefold():
        errors.append('The entity must be named.')
    if not re.search(r'\b(?:from|between|during)\b|20\d{2}\s*[-–]\s*20\d{2}', text, re.I):
        errors.append('State the observed time span explicitly.')
    if re.search(r'\b(?:pp|yoy|casa|nim|cagr|basis points)\b', text, re.I):
        errors.append('Expand financial jargon into plain English.')
    allowed = {f.value_decimal for f in facts if f.value_decimal is not None}
    allowed.update(c.output_value for c in calculations if c.available and c.output_value is not None)
    allowed.update(Decimal(d.year) for f in facts for d in (f.period_start, f.period_end) if d)
    allowed.update(number_tokens(entity))  # Digits in a verified legal name are identity, not a financial metric.
    rounded = {x.quantize(Decimal('1')) for x in allowed} | {x.quantize(Decimal('.01')) for x in allowed}
    if any(n not in allowed | rounded for n in number_tokens(text)):
        errors.append('A headline number has no verified fact or registered calculation.')
    values_by_unit = [(f.value_decimal, f.unit_normalized) for f in facts if f.value_decimal is not None]
    values_by_unit += [(c.output_value, c.unit) for c in calculations if c.available and c.output_value is not None]
    for match in re.finditer('(' + NUMBER + r')\s*(%|percent\b|percentage points?\b|crore\b)', text, re.I):
        value = Decimal(match[1].replace(',', ''))
        unit = 'percent' if match[2].lower() in {'%', 'percent'} else 'INR_crore' if match[2].lower() == 'crore' else 'percentage_points'
        if not any(u == unit and value in {v, v.quantize(Decimal('1')), v.quantize(Decimal('.01'))} for v, u in values_by_unit):
            errors.append('A headline number uses an unverified unit.')
    years = {str(f.period_end.year) for f in facts if f.period_end}
    if not any(y in text for y in years) or not re.search(r'%|\b(?:percent|percentage points?|crore|lakh|times)\b', text, re.I):
        errors.append('Include the verified time span and measurement units.')
    measured = re.sub(re.escape(entity), '', text, count=1, flags=re.I)
    measured = re.sub(r'\b(?:19|20)\d{2}\b', '', measured)
    if not 1 <= len(number_tokens(measured)) <= 2:
        errors.append('Use one or two key numbers, excluding calendar years.')
    return errors


def template_headline(company, facts, calculations):
    available = [c for c in calculations if c.available and c.output_value is not None]
    c = next((c for c in available if c.formula_id.startswith('recovery_ratio')), None) or next(
        (c for c in available if c.formula_id == 'growth_gap'), available[0])
    inputs = [f for f in facts if f.id in c.input_fact_ids]
    ends = sorted({f.period_end for f in inputs if f.period_end})
    span = f'from {ends[0].year} to {ends[-1].year}'
    value = f'{c.output_value:,.2f}'.rstrip('0').rstrip('.')
    if c.formula_id.startswith('recovery_ratio'):
        detail = f'restored {value}% of its pre-event ' + ('funding mix' if c.formula_id.endswith('funding_mix') else inputs[0].metric_key.replace('_', ' '))
    elif c.formula_id == 'growth_gap':
        detail = f'recorded a {value} percentage point {inputs[0].metric_key.replace("_", " ")} versus {inputs[2].metric_key.replace("_", " ")} growth gap'
    else:
        unit = '%' if c.unit == 'percent' else ' percentage points' if c.unit == 'percentage_points' else ' times'
        label = {'yoy_growth': 'annual growth', 'cagr': 'annual compounded growth'}.get(c.formula_id, c.formula_id.replace('_', ' '))
        detail = f'recorded {value}{unit} for {label} in {inputs[0].metric_key.replace("_", " ")}'
    return f'{company.legal_name} {detail} {span}.', c
