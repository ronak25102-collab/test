"""Explicit component/total reconciliation, never an unrestricted segment merge."""
from decimal import Decimal

SEGMENT_FORMULAS = {'segment_revenue_share', 'segment_profit_share', 'segment_dependency_gap'}


def validate_segment_inputs(formula, facts):
    if len(facts) < 3:
        raise ValueError('segment shares require at least two components and their disclosed total')
    groups = [facts]
    if formula == 'segment_dependency_gap':
        if len(facts) % 2:
            raise ValueError('segment dependency requires equal revenue/result component coverage')
        half = len(facts) // 2
        groups = [facts[:half], facts[half:]]
    expected = ['segment_revenue', 'segment_profit'] if len(groups) == 2 else [
        'segment_revenue' if formula == 'segment_revenue_share' else 'segment_profit']
    for group, metric in zip(groups, expected, strict=True):
        components, total = group[:-1], group[-1]
        if total.metric_key != metric + '_total' or total.segment != 'all':
            raise ValueError('segment denominator must be the separately disclosed segment total')
        if len(components) < 2 or any(f.metric_key != metric or f.segment == 'all' for f in components):
            raise ValueError('segment components require explicit named boundaries and matching definitions')
        if len({f.segment.casefold() for f in components}) != len(components):
            raise ValueError('duplicate segment component')
        if len({f.definition_id for f in components}) != 1:
            raise ValueError('segment component definitions differ')
        if total.value <= 0 or sum((f.value for f in components), Decimal(0)) != total.value:
            raise ValueError('all segment components must reconcile exactly to the reported total')
        if metric == 'segment_revenue' and any(f.value < 0 for f in components):
            raise ValueError('negative segment revenue needs a separately defined reconciliation')
    if len(groups) == 2 and [f.segment.casefold() for f in groups[0]] != [f.segment.casefold() for f in groups[1]]:
        raise ValueError('revenue and result segment boundaries differ')
    if any(f.period_type != 'duration' or not f.period_start for f in facts):
        raise ValueError('segment results require explicit duration windows')
    if len({(f.period_start, f.period) for f in facts}) != 1:
        raise ValueError('segment reporting intervals differ')
    return ['explicit named segment components reconcile to their own reported total',
            'same issuer, scope, currency, unit and exact duration; no consolidated-profit substitution']


def segment_groups(facts):
    """Return unique, complete source groups without silently resolving conflicts."""
    lanes = {}
    for fact in facts:
        if fact.metric_key not in {'segment_revenue', 'segment_profit', 'segment_revenue_total', 'segment_profit_total'}:
            continue
        key = (fact.entity_id, fact.scope, fact.currency, fact.unit_normalized, fact.period_start, fact.period_end)
        lanes.setdefault(key, {}).setdefault((fact.metric_key, fact.segment.casefold()), []).append(fact)
    for lane in lanes.values():
        if any(len({(f.value_decimal, f.definition_id) for f in values}) != 1 for values in lane.values()):
            continue
        unique = [sorted(values, key=lambda f: str(f.id))[0] for values in lane.values()]
        revenue = sorted([f for f in unique if f.metric_key == 'segment_revenue'], key=lambda f: f.segment.casefold())
        profit = sorted([f for f in unique if f.metric_key == 'segment_profit'], key=lambda f: f.segment.casefold())
        rt = next((f for f in unique if f.metric_key == 'segment_revenue_total' and f.segment == 'all'), None)
        pt = next((f for f in unique if f.metric_key == 'segment_profit_total' and f.segment == 'all'), None)
        yield revenue, rt, profit, pt
