"""Comparable peer arithmetic with separate issuer lineage; never mix peer facts into issuer totals."""
from decimal import Decimal
from statistics import median

from signal_research.domain.enums import FactStatus
from signal_research.finance.calculations import calculate, numeric_fact
from signal_research.finance.registry import METRICS
from signal_research.research.context import exact_excerpt


def peer_search_query(company, target_facts, *, broad=False):
    """Use public filing language; exact matching belongs to verification."""
    ends = [fact.period_end for fact in target_facts if fact.period_end]
    period = max(ends).strftime('%B %Y') if ends else ''
    scopes = {fact.scope.value for fact in target_facts}
    scope = next(iter(scopes)) if len(scopes) == 1 and not broad else ''
    labels = []
    if not broad:
        for key in dict.fromkeys(fact.metric_key for fact in target_facts):
            definition = METRICS.get(key)
            if definition:
                label = next((alias for alias in definition.aliases if '%' not in alias), definition.aliases[0])
                labels.append(label)
    return ' '.join(part for part in [f'"{company.legal_name}"', 'financial results', scope,
        'balance sheet' if labels else '', ' '.join(labels[:3]), period] if part)


def peer_model_context(benchmark):
    """Only verified comparison inputs enter prompts; full documents stay in the report."""
    context = {key: benchmark.get(key, [] if key != 'status' else 'inconclusive')
               for key in ('status', 'comparisons', 'missing')}
    context['evidence'] = []
    used = {identifier for row in benchmark.get('comparisons', [])
            for peer in row['peers'].values() for identifier in peer['fact_ids']}
    for bundle in benchmark.get('sources', []):
        facts = [f for f in bundle['facts'] if str(f['id']) in used]
        if not facts:
            continue
        passage_ids = {f['passage_id'] for f in facts}
        passages = []
        for passage in bundle['passages']:
            if passage['id'] in passage_ids:
                anchors = [f['value_raw'] for f in facts if f['passage_id'] == passage['id']]
                passages.append({'id': passage['id'], 'document_id': passage['document_id'],
                                 **exact_excerpt(passage['text'], anchors, '', limit=3500)})
        documents = [{k: d[k] for k in ('id', 'canonical_url', 'title', 'origin_family_id')}
                     for d in bundle['documents'] if d['id'] in {p['document_id'] for p in passages}]
        context['evidence'].append({'company': bundle['company']['legal_name'], 'facts': facts,
                                    'passages': passages, 'documents': documents})
    context['note'] = 'Only verified matching peer inputs are supplied; full original passages are retained in the exported evidence trail. Missing peer evidence is not absence of a sector effect.'
    return context


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
