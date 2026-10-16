"""Source-bound structural-break warnings; a large jump is not itself a discovery."""
import re
from decimal import Decimal

from signal_research.finance.calculations import calculate, numeric_fact
from signal_research.research.history import comparable_series

BREAK_WORDS = r'\b(?:merger|amalgamation|scheme of arrangement|demerger|acquisition|reclassification|restatement)\b'


def detect_breaks(facts, passages, documents, peer_medians=None, threshold=Decimal('40')):
    sources = {p.id: p for p in passages}
    docs = {d.id: d for d in documents}
    result, seen = [], set()
    for series in comparable_series(facts):
        if series['cadence'] != 'annual_endpoint' or series['period_type'] != 'instant' or series['unit'] != 'INR_crore':
            continue
        ordered = sorted([f for f in facts if f.id in {o['fact_id'] for o in series['observations']}], key=lambda f: f.period_end)
        for prior, current in zip(ordered, ordered[1:]):
            if not 350 <= (current.period_end - prior.period_end).days <= 380:
                continue
            growth = calculate('yoy_growth', [numeric_fact(current), numeric_fact(prior)])
            key = (current.metric_key, prior.period_end, current.period_end, current.scope)
            if not growth.available or abs(growth.output_value) <= threshold or key in seen:
                continue
            seen.add(key)
            median = (peer_medians or {}).get(key)
            if median is not None and abs(Decimal(str(median))) >= 20:
                continue
            linked = [p for p in passages if p.document_id == sources[current.passage_id].document_id
                      and re.search(BREAK_WORDS, p.text, re.I)]
            result.append({'id': f'break:{current.id}', 'metric': current.metric_key,
                           'scope': current.scope.value, 'start': str(prior.period_end), 'end': str(current.period_end),
                           'fact_ids': [str(prior.id), str(current.id)],
                           'growth': str(growth.output_value), 'unit': 'percent',
                           'status': 'documented_event_requires_reconciliation' if linked else 'suspected_requires_filing_search',
                           'passage_ids': [str(p.id) for p in linked[:3]],
                           'source_ids': [str(sources[current.passage_id].document_id)],
                           'peer_median': str(median) if median is not None else None,
                           'reason': 'Large comparable annual balance change; event causality and organic growth are not established.',
                           'source_url': str(docs[sources[current.passage_id].document_id].canonical_url)})
    return result


def break_calculations(breaks, calculations):
    """Exclude only growth comparisons crossing a flagged interval, not recovery arithmetic."""
    return {c.id for c in calculations if c.formula_id in {'yoy_growth', 'growth_gap', 'ldr_change'}
            and any(set(b['fact_ids']) <= {str(i) for i in c.input_fact_ids} for b in breaks)}
