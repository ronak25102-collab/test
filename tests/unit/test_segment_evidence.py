from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from signal_research.domain.enums import Profile, Scope
from signal_research.extraction.validate import validate_candidate
from signal_research.finance.calculations import calculate, numeric_fact
from signal_research.research.brief import compatible_candidate
from signal_research.research.headline import template_headline, validate_headline
from signal_research.research.live import derive_calculations
from signal_research.research.proposals import verified_proposals
from signal_research.retrieval.exchange_tables import exchange_table_batch
from signal_research.retrieval.passages import parse_html


def segment_fixture():
    company = SimpleNamespace(id=uuid4(), legal_name='Quartz Financial Services Limited', symbols=['QFS'],
                              business_profiles=[Profile.DIVERSIFIED], aliases=[])
    raw = b'''<html><table>
    <tr><td>Name of company</td><td>Quartz Financial Services Limited</td></tr>
    <tr><td>NSE Symbol</td><td>QFS</td></tr>
    <tr><td>Description of presentation currency</td><td>INR</td></tr>
    <tr><td>Level of rounding used in financial results</td><td>Crore</td></tr></table>
    <table><tr><td>Date of start of reporting period</td><td>01-04-2026</td></tr>
    <tr><td>Date of end of reporting period</td><td>30-06-2026</td></tr>
    <tr><td>Nature of report standalone or consolidated</td><td>Consolidated</td></tr>
    <tr><td>1</td><td>Segment Revenue (Income)</td></tr>
    <tr><td>1</td><td>Investments</td><td>100.00</td></tr>
    <tr><td>2</td><td>Lending</td><td>60.00</td></tr>
    <tr><td>3</td><td>Others</td><td>40.00</td></tr>
    <tr><td></td><td>Total Segment Revenue</td><td>200.00</td></tr>
    <tr><td></td><td>Less: Inter segment revenue</td><td>20.00</td></tr>
    <tr><td></td><td>Revenue from operations</td><td>180.00</td></tr>
    <tr><td>2</td><td>Segment Result</td></tr>
    <tr><td>1</td><td>Investments</td><td>50.00</td></tr>
    <tr><td>2</td><td>Lending</td><td>5.00</td></tr>
    <tr><td>3</td><td>Others</td><td>(5.00)</td></tr>
    <tr><td></td><td>Total Profit before tax</td><td>50.00</td></tr></table></html>'''
    passage = next(p for p in parse_html(uuid4(), raw).passages if p.extraction_method=='exchange_table')
    batch = exchange_table_batch(passage,company,Profile.DIVERSIFIED)
    validations = [validate_candidate(c,passage,company.id,Profile.DIVERSIFIED) for c in batch.facts]
    assert all(v.fact is not None for v in validations), [v.reason for v in validations]
    return company, passage, [v.fact for v in validations]


def test_repeated_segment_names_retain_section_value_and_named_scope():
    _, passage, facts = segment_fixture()
    assert 'Segment Revenue (Income) :: 1 Investments | 100.00' in passage.text
    assert 'Segment Result :: 1 Investments | 50.00' in passage.text
    assert len(facts)==8
    values = {(f.metric_key,f.segment):f.value_decimal for f in facts}
    assert values['segment_revenue','Investments']==100
    assert values['segment_profit','Investments']==50
    assert values['segment_profit','Others']==-5
    assert values['segment_revenue_total','all']==200  # Gross, not net revenue 180.
    assert not any(f.metric_key=='net_profit' for f in facts)


def test_reconciled_segment_relationship_has_reproducible_lineage_and_snapshot_proposal():
    company, _, facts = segment_fixture()
    calculations = derive_calculations(facts)
    gap = next(c for c in calculations if c.formula_id=='segment_dependency_gap' and c.output_value==50)
    assert len(gap.input_fact_ids)==8
    assert {c.output_value for c in calculations if c.formula_id=='segment_revenue_share'}=={Decimal(50),Decimal(30),Decimal(20)}
    batch = verified_proposals(company,facts,calculations,[])
    assert batch.candidates
    assert '100%' in batch.candidates[0].statement and '50%' in batch.candidates[0].statement
    assert compatible_candidate(batch.candidates[0],facts,calculations)[0]
    text, _ = template_headline(company,facts,[gap])
    assert 'April 2026 to June 2026' in text
    assert not validate_headline(text,company.legal_name,facts,[gap])
    # Arbitrary cross-segment ratios still fail the original gate.
    a = next(f for f in facts if f.metric_key=='segment_revenue' and f.segment=='Investments')
    b = next(f for f in facts if f.metric_key=='segment_profit' and f.segment=='Lending')
    assert not calculate('share_pct',[numeric_fact(a),numeric_fact(b)]).available


def test_single_window_does_not_spend_peer_requests_without_comparable_target_series():
    from signal_research.research.live import LiveResearch
    company, _, facts = segment_fixture()
    research=LiveResearch.__new__(LiveResearch)
    research.company, research.facts, research.calculations=company,facts,derive_calculations(facts)
    research.peer_collection_attempted=False
    research.run_id=uuid4()
    artifacts=[]
    research.store=SimpleNamespace(artifact=lambda *args:artifacts.append(args),
        peer_candidates=lambda *args:(_ for _ in ()).throw(AssertionError('No numeric peer target')))
    research.collect_peer_benchmark(SimpleNamespace(fact_ids=[f.id for f in facts],calculation_ids=[]))
    assert research.peer_collection_attempted and research.peer_benchmark['status']=='inconclusive'
    assert research.peer_benchmark['missing'] and len(artifacts)==1


@pytest.mark.parametrize('status', ['supported', 'contradicted'])
@pytest.mark.parametrize('unverified_number', [False, True])
def test_current_reconciliation_requires_its_own_verified_numbers(status, unverified_number):
    from signal_research.research.live import LiveResearch
    company, passage, facts = segment_fixture()
    calculations = derive_calculations(facts)
    hypothesis = verified_proposals(company, facts, calculations, []).candidates[0]
    research = LiveResearch.__new__(LiveResearch)
    research.facts, research.calculations = facts, calculations
    research.run_id, research.opposing_queries, research.limitations = uuid4(), ['reconciliation notes'], []
    research.payload = lambda _: {'passages': [{'id': passage.id}]}
    reason = ('The note reports 987654.32 crore of eliminations.' if unverified_number
              else 'The original note qualifies how the reported segment results should be interpreted.')
    research.calls = SimpleNamespace(model=lambda schema, *args, **kwargs: schema(
        status=status, passage_ids=[passage.id], reason=reason))
    artifacts = []
    research.store = SimpleNamespace(artifact=lambda *args: artifacts.append(args))
    research.check_current_reconciliation(hypothesis)
    assert research.now_check['searched_queries'] == research.opposing_queries
    if unverified_number:
        assert research.now_check['status'] == 'not_found'
        assert research.now_check['passage_ids'] == []
        assert 'unverified' in research.now_check['reason']
        assert research.limitations and artifacts[0][1] == 'unverified_reconciliation_review'
        assert artifacts[0][2]['status'] == status  # Preserve adverse evidence for audit.
    else:
        assert research.now_check['status'] == status
        assert not research.limitations


@pytest.mark.parametrize('corruption',['missing_component','wrong_scope','wrong_period','wrong_total','different_names','wrong_denominator','different_entity'])
def test_incomplete_or_incomparable_segment_schedules_do_not_produce_dependency(corruption):
    _, _, facts = segment_fixture()
    if corruption=='missing_component':
        facts = [f for f in facts if not(f.segment=='Others' and f.metric_key=='segment_profit')]
    elif corruption=='wrong_scope':
        facts[0].scope=Scope.STANDALONE
    elif corruption=='wrong_period':
        facts[0].period_end=date(2025,6,30)
    elif corruption=='wrong_total':
        next(f for f in facts if f.metric_key=='segment_revenue_total').value_decimal=Decimal(180)
    elif corruption=='wrong_denominator':
        next(f for f in facts if f.metric_key=='segment_profit_total').metric_key='net_profit'
    elif corruption=='different_entity':
        facts[0].entity_id=uuid4()
    else:
        next(f for f in facts if f.metric_key=='segment_profit' and f.segment=='Others').segment='Unmatched'
    assert not any(c.formula_id=='segment_dependency_gap' for c in derive_calculations(facts))


@pytest.mark.parametrize('reject', [False,True])
def test_segment_snapshot_still_requires_complete_independent_publication_review(store,settings,reject):
    from datetime import UTC, datetime

    from signal_research.db.models import CompanyModel
    from signal_research.domain.enums import RunMode
    from signal_research.domain.schemas import Company, SourceDocument
    from signal_research.research.live import Challenge, DiscoveryDraft, LiveResearch
    from signal_research.research.verifier import verify_report
    from signal_research.worker.budgets import Budget
    raw_company, passage, facts = segment_fixture()
    company = Company(id=raw_company.id,legal_name=raw_company.legal_name,symbols=raw_company.symbols,
                      business_profiles=raw_company.business_profiles,verified_ir_domains=['issuer.example'])
    with store.session_factory() as db:
        db.add(CompanyModel(id=str(company.id),legal_name=company.legal_name,symbols=company.symbols,
                            business_profiles=['diversified'],aliases=[],verified_ir_domains=['issuer.example']))
        db.commit()
    rid=store.create_run(company,date(2026,10,18),RunMode.LIVE)
    research=LiveResearch(SimpleNamespace(store=store,settings=settings),rid,company,date(2026,10,18),Budget(100,100,100,0))
    research.facts, research.calculations, research.passages=facts,derive_calculations(facts),[passage]
    research.documents=[SourceDocument(id=passage.document_id,canonical_url='https://issuer.example/segments',
        final_url='https://issuer.example/segments',publisher='Quartz',origin_family_id='issuer:quartz',
        title='Quarterly segment disclosure',document_type='issuer_disclosure',published_at=datetime(2026,7,18,tzinfo=UTC),
        retrieved_at=datetime(2026,10,18,tzinfo=UTC),content_hash='a'*64,mime_type='text/html')]
    hypothesis=verified_proposals(company,facts,research.calculations,[]).candidates[0]
    def statement(text):
        return dict(text=text,kind='derived',fact_ids=hypothesis.fact_ids,calculation_ids=hypothesis.calculation_ids,passage_ids=[passage.id])
    draft=DiscoveryDraft(headline=statement('Quartz Financial Services Limited reported Investments contributing 100% of segment results versus 50% of gross segment revenue during April 2026 to June 2026.'),
        why_it_matters=[statement('Investments contribute disproportionately to the reported segment results.'),
                        statement('Gross segment revenue is the denominator; segment results are not consolidated net profit.'),
                        statement('This disclosed window establishes an observation, not a persistent trend.')],
        counterargument=statement('Other segments include a loss, so persistence and the economic cause of this concentration remain uncertain.'),
        timeline_analysis=statement('Only the April to June 2026 reporting interval is established; the onset of this relationship is unknown.'),
        onset_status='unknown',falsification='Investments no longer contribute more to reported segment results than gross segment revenue.',
        falsification_window='Next comparable quarterly segment disclosure',falsification_source='Original issuer quarterly segment schedule')
    def review(schema,payload,**kwargs):
        assert schema.__name__=='SemanticReview'
        return schema(verdicts=[dict(claim_id=c['id'],supported=not reject,reason='Independent test reviewer verdict')
                                for c in payload['claims']],falsification_is_observable=True,
                      contains_investment_recommendation=False,non_obvious_synthesis_supported=True)
    research.calls=SimpleNamespace(model=review)
    challenge=Challenge(refuted=False,unresolved=True,strongest_alternative='Reported losses or accounting classifications may explain concentration.',
        reason='A bounded arithmetic observation survives; causal persistence is not established.',relevant_passage_ids=[passage.id],
        novelty_status='additional_supported_synthesis',novelty_rationale='Cross-metric result concentration beyond headline totals.',published_explanation='Segment totals only.')
    report=research.compose(draft,challenge,'segment concentration alternative accounting explanation')
    if reject:
        assert report is None
    else:
        assert verify_report(report).outcome.value=='discovery'
        assert report.discoveries[0].evidence_strength.value=='Weak'
        assert report.generation_metadata['temporal_reasoning']['onset_status']=='unknown'
        condition=report.generation_metadata['falsification_tests']['conditions'][0]
        assert condition['metric']=='segment_dependency_gap'
