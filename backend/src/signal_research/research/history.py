"""Describe comparable observed series without inferring causality or onset."""
from __future__ import annotations

import calendar


def _series(observed, cadence):
    periods = {fact.period_end for fact in observed}
    first = observed[0]
    return {
        'metric': first.metric_key, 'scope': first.scope.value,
        'segment': first.segment, 'definition_id': first.definition_id,
        'unit': first.unit_normalized, 'currency': first.currency,
        'period_type': first.period_type.value, 'cadence': cadence,
        'observations': [{'fact_id': fact.id, 'period_start': fact.period_start,
                          'period_end': fact.period_end, 'value': fact.value_decimal,
                          'passage_id': fact.passage_id} for fact in observed],
        'comparable_periods': len(periods),
        'coverage': 'multi_period' if len(periods) >= 3 else 'two_snapshots' if len(periods) == 2 else 'single_snapshot',
        'limitations': (['Consecutive quarter-end observations establish coverage, not seasonally adjusted growth or causality.']
                        if cadence == 'quarterly' else [] if len(periods) >= 3 else
                        ['Observed snapshots do not establish when a trend began or prove a causal mechanism.']),
    }


def comparable_series(facts):
    groups = {}
    for fact in facts:
        if fact.period_end is None or fact.value_decimal is None:
            continue
        key = (fact.entity_id, fact.metric_key, fact.definition_id, fact.scope,
               fact.segment, fact.currency, fact.unit_normalized, fact.period_type,
               (fact.period_start.month, fact.period_start.day) if fact.period_start else None)
        groups.setdefault(key, []).append(fact)
    result = []
    for values in groups.values():
        values.sort(key=lambda f: f.period_end)
        # Report each fiscal/calendar endpoint separately. A June snapshot and
        # a March balance are not a single annual-comparison history.
        endpoints = {}
        for fact in values:
            endpoints.setdefault((fact.period_end.month, fact.period_end.day), []).append(fact)
        for observed in endpoints.values():
            result.append(_series(observed, 'annual_endpoint'))
    # Quarter-end stocks and explicit three-month flows may also form a series.
    # They remain separate from same-endpoint annual comparisons and YTD flows.
    quarterly = {}
    for fact in facts:
        end = fact.period_end
        if end is None or fact.value_decimal is None or end.month not in (3, 6, 9, 12) or end.day != calendar.monthrange(end.year, end.month)[1]:
            continue
        if fact.period_type.value == 'duration' and (not fact.period_start or not 88 <= (end - fact.period_start).days <= 92):
            continue
        key = (fact.entity_id, fact.metric_key, fact.definition_id, fact.scope, fact.segment,
               fact.currency, fact.unit_normalized, fact.period_type)
        quarterly.setdefault(key, {})[end] = fact
    for values in quarterly.values():
        sequence = []
        for fact in sorted(values.values(), key=lambda f: f.period_end):
            if sequence and not 80 <= (fact.period_end - sequence[-1].period_end).days <= 100:
                if len(sequence) >= 3:
                    result.append(_series(sequence, 'quarterly'))
                sequence = []
            sequence.append(fact)
        if len(sequence) >= 3:
            result.append(_series(sequence, 'quarterly'))
    return result


def needs_history(facts):
    return not any(series['comparable_periods'] >= 3 for series in comparable_series(facts))


def has_relationship_evidence(facts, calculations):
    """A lone headline growth number is insufficient for cross-metric research."""
    by_id = {fact.id: fact for fact in facts}
    for calculation in calculations:
        if len({by_id[identifier].metric_key for identifier in calculation.input_fact_ids
                if identifier in by_id}) >= 2:
            return True
    compared = {by_id[identifier].metric_key for calculation in calculations
                for identifier in calculation.input_fact_ids if identifier in by_id}
    return len(compared) >= 2
