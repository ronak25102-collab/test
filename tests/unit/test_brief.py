from types import SimpleNamespace
from uuid import uuid4

from signal_research.domain.schemas import Fact
from signal_research.research.brief import compatible_candidate, submission_checklist


def test_a_polished_abstention_never_counts_as_a_complete_discovery():
    report = SimpleNamespace(discoveries=[], source_coverage={}, facts=[], calculations=[object()],
                             generation_metadata={})
    checklist = submission_checklist(report)
    assert not checklist['discovery_ready']
    assert len(checklist['items']) == 8
    assert [i['key'] for i in checklist['items'] if i['status'] == 'complete'] == ['numbers']


def test_scope_check_follows_calculation_inputs_not_only_explicit_candidate_facts():
    entity = uuid4()
    facts = [SimpleNamespace(id=uuid4(), entity_id=entity, scope=scope, segment='all', currency='INR')
             for scope in ['standalone', 'consolidated']]
    calc = SimpleNamespace(id=uuid4(), input_fact_ids=[facts[1].id])
    hypothesis = SimpleNamespace(fact_ids=[facts[0].id], calculation_ids=[calc.id])
    compatible, reason = compatible_candidate(hypothesis, facts, [calc])
    assert not compatible and 'scope' in reason
    facts[1].scope = 'standalone'
    assert compatible_candidate(hypothesis, facts, [calc])[0]


def test_timeline_requires_reviewed_comparable_development_not_uncited_history():
    entity = uuid4()
    facts = [Fact(id=uuid4(), entity_id=entity, metric_key='deposits', value_decimal=100,
                  unit_normalized='INR_crore', currency='INR', period_end=f'{year}-03-31',
                  period_type='instant', scope='standalone', definition_id='deposits_as_reported_v1',
                  passage_id=uuid4(), status='verified') for year in (2024, 2025, 2026)]
    claim = SimpleNamespace(id=uuid4(), evidence_links=[], calculation_ids=[])
    discovery = SimpleNamespace(why_it_matters=[1, 2, 3], timeline_event_ids=[uuid4()],
                                counterargument=SimpleNamespace(search_attempted=True),
                                falsification_rules=[object()], strength_rationale='Reviewed but qualified.')
    report = SimpleNamespace(discoveries=[discovery], facts=facts,
                             calculations=[SimpleNamespace(id=uuid4(), input_fact_ids=[])],
                             source_coverage={}, claims=[claim], generation_metadata={
                                 'temporal_reasoning': {'onset_status': 'unknown', 'claim_id': str(claim.id)}})
    # Global historical coverage cannot substitute for the temporal claim's evidence.
    claim.evidence_links = [SimpleNamespace(passage_or_fact_id=f.id) for f in facts[:2]]
    assert submission_checklist(report)['items'][3]['status'] == 'limited'
    claim.evidence_links.append(SimpleNamespace(passage_or_fact_id=facts[2].id))
    assert submission_checklist(report)['discovery_ready']
    # Three dates spanning different reporting scopes still cannot establish development.
    facts[0].scope = facts[0].scope.__class__('consolidated')
    assert submission_checklist(report)['items'][3]['status'] == 'limited'
