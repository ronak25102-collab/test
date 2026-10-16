"""Comparable peer arithmetic with separate issuer lineage; never mix peer facts into issuer totals."""
from decimal import Decimal
from statistics import median

from signal_research.domain.enums import FactStatus
from signal_research.finance.calculations import calculate, numeric_fact


def signature(fact):
    return (fact.metric_key, fact.scope, fact.segment, fact.currency, fact.unit_normalized,
            fact.period_type, fact.period_start, fact.period_end, fact.definition_id)


def compare_peers(target_facts, peer_facts, *, gap_threshold=Decimal('10')):
    rows = []
    for current in target_facts:
        if current.status != FactStatus.VERIFIED or current.value_decimal is None:
            continue
        prior = next((f for f in target_facts if f.metric_key == current.metric_key and f.scope == current.scope
                      and f.definition_id == current.definition_id and f.period_end and current.period_end
                      and 350 <= (current.period_end - f.period_end).days <= 380), None)
        comparison = 'reported_ratio' if current.unit_normalized == 'percent' else 'annual_growth'
        if comparison == 'annual_growth':
            if prior is None:
                continue
            result = calculate('yoy_growth', [numeric_fact(current), numeric_fact(prior)])
            if not result.available:
                continue
            target_value = result.output_value
        else:
            target_value = current.value_decimal
        peers = {}
        for fact in peer_facts:
            if fact.entity_id == current.entity_id or fact.status != FactStatus.VERIFIED or signature(fact) != signature(current):
                continue
            inputs, value = [fact], fact.value_decimal
            if comparison == 'annual_growth':
                old = next((f for f in peer_facts if f.entity_id == fact.entity_id and f.status == FactStatus.VERIFIED
                            and signature(f) == signature(prior)), None)
                if not old:
                    continue
                growth = calculate('yoy_growth', [numeric_fact(fact), numeric_fact(old)])
                if not growth.available:
                    continue
                inputs, value = [fact, old], growth.output_value
            peers[str(fact.entity_id)] = {'value': str(value), 'fact_ids': [str(f.id) for f in inputs]}
        if len(peers) < 2:
            continue
        mid = Decimal(str(median([Decimal(p['value']) for p in peers.values()])))
        gap = target_value - mid
        rows.append({'id': f'peer:{current.id}', 'metric': current.metric_key, 'comparison': comparison,
                     'period_end': str(current.period_end), 'scope': current.scope.value, 'unit': 'percentage_points',
                     'company_value': str(target_value), 'peer_median': str(mid), 'gap': str(gap),
                     'target_fact_ids': [str(current.id), *([str(prior.id)] if comparison == 'annual_growth' else [])],
                     'peers': peers, 'classification': 'company-specific' if abs(gap) >= gap_threshold else 'sector-wide',
                     'rule': f'Absolute gap to median >= {gap_threshold} percentage points means company-specific; otherwise sector-wide. Descriptive screen, not causality.'})
    return {'status': 'verified' if rows else 'inconclusive', 'comparisons': rows,
            'missing': [] if rows else ['At least two peers with independently verified matching metric, definition, scope, unit and period endpoints.']}
