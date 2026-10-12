"""Reject invented percentage findings before spending retrieval allowance."""
import re
from decimal import Decimal

TOKEN = re.compile(r'(?<![\w.])(-?\d+(?:\.\d+)?)\s*(%|percentage points?|basis points?|bps|pp)(?!\w)', re.I)


def numeric_mentions(statement):
    for match in TOKEN.finditer(statement):
        unit = match[2].lower()
        unit = 'percent' if unit == '%' else 'basis_points' if unit in {'bps', 'basis point', 'basis points'} else 'percentage_points'
        decimals = len(match[1].partition('.')[2])
        yield Decimal(match[1]), unit, Decimal(1).scaleb(-decimals) / 2


def matches(number, unit, tolerance, value, value_unit):
    return value is not None and unit == value_unit and abs(abs(number) - abs(Decimal(str(value)))) <= tolerance


def complete_calculation_lineage(statement, fact_ids, calculation_ids, calculations):
    """Attach omitted, uniquely matching existing arithmetic; never invent a value."""
    linked = [c for c in calculations if c.id in calculation_ids]
    bound_facts = set(fact_ids) | {i for c in linked for i in c.input_fact_ids}
    result = list(calculation_ids)
    for number, unit, tolerance in numeric_mentions(statement):
        if any(matches(number, unit, tolerance, c.output_value, c.unit) for c in linked):
            continue
        candidates = [c for c in calculations if set(c.input_fact_ids) <= bound_facts and
                      matches(number, unit, tolerance, c.output_value, c.unit)]
        if len(candidates) == 1 and candidates[0].id not in result and len(result) < 8:
            result.append(candidates[0].id)
            linked.append(candidates[0])
    return result


def supported_percentages(statement, facts, calculations):
    values = [(c.output_value, c.unit) for c in calculations]
    values += [(f.value_decimal, f.unit_normalized) for f in facts if f.unit_normalized == 'percent']
    for number, unit, tolerance in numeric_mentions(statement):
        if not any(matches(number, unit, tolerance, value, value_unit) for value, value_unit in values):
            return False
    return True
