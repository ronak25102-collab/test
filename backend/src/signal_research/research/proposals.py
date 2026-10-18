"""Fast, unconfirmed research proposals from already registered arithmetic.

These are proposals, never published discoveries. The normal adversarial,
novelty, numerical and independent semantic review gates still decide publication.
"""
from signal_research.finance.registry import METRICS
from signal_research.research.angles import route_angles
from signal_research.research.brief import compatible_candidate, research_lanes
from signal_research.research.structural import break_calculations


def verified_proposals(company, facts, calculations, structural_breaks):
    from signal_research.research.live import Hypothesis, HypothesisBatch

    blocked = break_calculations(structural_breaks, calculations)
    blocked |= {c.id for c in calculations if not c.formula_id.startswith('recovery_ratio')
                and any(set(event['fact_ids']) <= {str(i) for i in c.input_fact_ids}
                        for event in structural_breaks)}
    rank = {'segment_dependency_gap':0, 'recovery_ratio_funding_mix': 0, 'recovery_ratio': 0,
            'deposit_borrowing_mix_change': 1, 'growth_gap': 2}
    results = []
    by_id = {f.id: f for f in facts}
    def label(key):
        return METRICS[key].aliases[0] if key in METRICS else key.replace('_', ' ')
    def number(calculation):
        value = f'{calculation.output_value:.2f}'.rstrip('0').rstrip('.')
        unit = {'percent': '%', 'percentage_points': ' percentage points', 'basis_points': ' basis points'}.get(calculation.unit)
        return value + unit if unit else None
    def propose(selected, angle):
        identifiers = list(dict.fromkeys(i for c in selected for i in c.input_fact_ids))
        inputs = [by_id[i] for i in identifiers]
        ends = sorted({f.period_end for f in inputs if f.period_end})
        c = selected[0]
        if not ends or (len(ends) < 2 and c.formula_id != 'segment_dependency_gap') or len(identifiers) > 12:
            return
        scope = inputs[0].scope.value
        span = f'from {ends[0].isoformat()} to {ends[-1].isoformat()}'
        if c.formula_id == 'segment_dependency_gap':
            if abs(c.output_value) < 10:
                return  # Descriptive ranking heuristic, not a materiality claim.
            half = len(c.input_fact_ids) // 2
            shares = [next((other for other in calculations if other.input_fact_ids == c.input_fact_ids[start:end]
                            and other.formula_id == formula), None)
                      for start,end,formula in [(0,half,'segment_revenue_share'),(half,len(c.input_fact_ids),'segment_profit_share')]]
            if not all(shares):
                return
            selected = [c,*shares]
            detail = f'reported {inputs[0].segment} contributing {number(shares[1])} of reported segment results versus {number(shares[0])} of gross segment revenue'
            span = f'during {inputs[0].period_start.isoformat()} to {ends[-1].isoformat()}'
        elif c.formula_id == 'growth_gap':
            detail = f'recorded a {number(c)} growth difference between {label(inputs[0].metric_key)} and {label(inputs[2].metric_key)}'
        elif c.formula_id == 'deposit_borrowing_mix_change':
            detail = f'recorded a {number(c)} change in deposits as a share of deposits plus borrowings'
        elif c.formula_id.startswith('recovery_ratio'):
            detail = f'restored {number(c)} of its verified pre-event ratio level'
        elif len(selected) == 2:
            detail = (f'recorded {number(c)} change in {label(by_id[c.input_fact_ids[0]].metric_key)}'
                      f' while {label(by_id[selected[1].input_fact_ids[0]].metric_key)} changed {number(selected[1])}')
        else:
            return
        hypothesis = Hypothesis(statement=f'{company.legal_name} {detail} {span} on the {scope} reporting basis.',
            mechanism=('This is a reproducible comparison, not an established causal explanation. ' +
                       ' '.join(dict.fromkeys(note for calc in selected for note in calc.limitations)))[:600],
            fact_ids=identifiers, calculation_ids=[calc.id for calc in selected],
            next_query=(angle['question'] + ' original disclosures explanation')[:180],
            opposing_query=(' '.join(label(f.metric_key) for f in inputs[:2]) +
                ' merger restatement reclassification seasonality denominator sector comparison')[:180],
            falsification='Test whether the direction reverses in the next comparable quarterly disclosure; check original reconciliation notes now. This tests continuation, not the validity of the historical arithmetic.',
            significance=3, novelty=2)
        if compatible_candidate(hypothesis, facts, calculations)[0]:
            results.append(hypothesis)
    for lane in research_lanes(facts, calculations):
        lane_facts = [f for f in facts if f.id in lane['fact_ids']]
        ids = {f.id for f in lane_facts}
        lane_calcs = [c for c in calculations if c.available and c.output_value is not None
                      and c.id not in blocked and set(c.input_fact_ids) <= ids and number(c)]
        for angle in route_angles(company, lane_facts, lane_calcs):
            if angle['coverage_groups'] != angle['required_groups']:
                continue
            relevant = {f.id for f in lane_facts if f.metric_key in angle['metrics']}
            eligible = [c for c in lane_calcs if set(c.input_fact_ids) <= relevant]
            relations = sorted([c for c in eligible if c.formula_id in rank], key=lambda c: c.period or '', reverse=True)
            relations.sort(key=lambda c: rank[c.formula_id])
            for calculation in relations[:3]:
                propose([calculation], angle)
            # Different units are described side by side, never subtracted.
            growth = [c for c in eligible if c.formula_id == 'yoy_growth']
            quality = [c for c in eligible if c.formula_id == 'change_pp']
            for a in growth:
                for b in quality:
                    if ({by_id[i].period_end for i in a.input_fact_ids} ==
                            {by_id[i].period_end for i in b.input_fact_ids}):
                        propose([a, b], angle)
    unique = {(tuple(h.calculation_ids), h.statement): h for h in results}
    return HypothesisBatch(candidates=list(unique.values())[:3], missing_evidence=[])
