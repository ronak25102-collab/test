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


def recovery_calculations(facts, breaks):
    from signal_research.domain.schemas import Calculation
    results = []
    for event in breaks:
        if not event['passage_ids']:
            continue  # A numerical jump alone does not identify a structural event.
        ratios = [f for f in facts if f.scope.value == event['scope'] and f.unit_normalized == 'percent']
        groups = {}
        for f in ratios:
            groups.setdefault((f.metric_key, f.definition_id, f.segment), []).append(f)
        for values in groups.values():
            before = sorted([f for f in values if str(f.period_end) <= event['start']], key=lambda f: f.period_end)
            after = sorted([f for f in values if str(f.period_end) >= event['end']], key=lambda f: f.period_end)
            if before and len(after) >= 2:
                trough = min(after, key=lambda f: f.value_decimal)
                result = calculate('recovery_ratio', [numeric_fact(f) for f in [after[-1], trough, before[-1]]])
                if result.available:
                    results.append(Calculation(id=result.id, formula_id=result.formula_id, formula_version=result.formula_version,
                        input_fact_ids=result.input_fact_ids, output_value=result.output_value, unit=result.unit,
                        period=f"{before[-1].period_end} / {trough.period_end} / {after[-1].period_end}", scope=after[-1].scope,
                        comparability_checks=result.comparability_checks, limitations=['Observed recovery, not merger-adjusted organic performance; verified event receipt remains required.']))
        # A registered funding ratio may also be derived from its source-bound components.
        levels = []
        for end in sorted({f.period_end for f in facts if f.period_end}):
            pair = [next((f for f in facts if f.metric_key == key and f.period_end == end and f.scope.value == event['scope'] and f.segment == 'all'), None) for key in ('deposits', 'borrowings')]
            if all(pair):
                result = calculate('deposit_borrowing_mix', [numeric_fact(f) for f in pair])
                if result.available:
                    levels.append((end, result.output_value, pair))
        pre = [x for x in levels if str(x[0]) <= event['start']]
        post = [x for x in levels if str(x[0]) >= event['end']]
        if pre and len(post) >= 2:
            trough = min(post, key=lambda x: x[1])
            inputs = [*post[-1][2], *trough[2], *pre[-1][2]]
            result = calculate('recovery_ratio_funding_mix', [numeric_fact(f) for f in inputs])
            if result.available:
                results.append(Calculation(id=result.id, formula_id=result.formula_id, formula_version=result.formula_version,
                    input_fact_ids=result.input_fact_ids, output_value=result.output_value, unit=result.unit,
                    period=f'{pre[-1][0]} / {trough[0]} / {post[-1][0]}', scope=inputs[0].scope,
                    comparability_checks=result.comparability_checks, limitations=['Denominator covers deposits plus borrowings only; recovery does not prove organic causality.']))
    return list({c.id: c for c in results}.values())
