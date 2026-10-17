from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from pydantic import BaseModel
from signal_research.db.repositories import UNIVERSE_SEED, Store
from signal_research.domain.enums import Profile, RunMode
from signal_research.domain.schemas import Company, Fact
from signal_research.providers.llm.openai_provider import OpenAIProvider
from signal_research.research.identity import multiple_issuer_headings
from signal_research.research.live import LiveResearch, derive_calculations
from signal_research.research.peer_selector import select_peers
from signal_research.research.peers import comparison_targets
from signal_research.worker.budgets import Budget
from signal_research.worker.calls import DurableCalls


def test_parallel_event_allocation_is_atomic_across_store_instances(store):
    rid = store.create_run(store.search_companies('HDFCBANK')[0], date(2026, 10, 17), RunMode.LIVE)
    stores = [Store(store.session_factory, store.data_dir) for _ in range(4)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: stores[i % 4].append_event(rid, 'extracting', 'agent', f'Agent {i}'), range(32)))
    events = store.get_events(rid)
    assert len(events) == 33
    assert [e.sequence for e in events] == list(range(1, 34))


def test_publication_and_review_have_separate_protected_windows():
    research = LiveResearch.__new__(LiveResearch)
    research.settings = SimpleNamespace(max_run_seconds=7200, demo_target_seconds=600,
        stage_request_seconds={'challenging':90, 'composing':120, 'verifying':120})
    research.is_deep = False
    assert research.verification_reserve() == 90
    assert research.publication_reserve() == 210
    assert research.investigation_reserve() == 300


def test_stage_deadline_reserve_reaches_the_actual_provider(store, settings, monkeypatch):
    settings.allow_unknown_cost = True
    settings.openai_api_key = 'test'
    settings.openai_model_research = 'test-model'
    settings.stage_request_seconds = {'composing': 120}
    rid = store.create_run(store.search_companies('AXISBANK')[0], date(2026, 10, 17), RunMode.LIVE)
    budget = Budget(5, 5, 5, 0, deadline=datetime.now(UTC) + timedelta(seconds=100))
    calls = DurableCalls(store, settings, rid, budget)
    calls.stage_deadline_reserves = {'composing':90}
    class Answer(BaseModel):
        supported: bool
    def generate(self, schema, messages, role, deadline, outputs):
        assert 0 < deadline.total_seconds() <= 10
        return schema(supported=True), SimpleNamespace(input_tokens=10, output_tokens=10)
    monkeypatch.setattr(OpenAIProvider, 'generate', generate)
    assert calls.model(Answer, {}, stage='composing').supported


def test_listing_recipients_are_not_interleaved_issuers():
    header = 'National Stock Exchange of India Limited BSE Limited\nQuartz Financial Bank Limited'
    assert not multiple_issuer_headings(header, 'Quartz Financial Bank Limited')
    assert multiple_issuer_headings(header + '\nDifferent Finance Limited', 'Quartz Financial Bank Limited')
    assert multiple_issuer_headings('Quartz Finance Limited\nDifferent Finance Limited', 'Quartz Finance Limited')


def test_bank_peer_selection_prefers_same_business_model_without_ticker_rules():
    def company(name):
        return Company(id=uuid4(), legal_name=name, symbols=[name.split()[0].upper()],
                       business_profiles=[Profile.BANK], verified_ir_domains=['issuer.example'])
    target = company('Quartz Bank')
    small = company('Aardvark Small Finance Bank')
    general = [company('Birch Bank'), company('Cedar Bank'), company('Elm Bank')]
    assert select_peers(target, [small, *general], Profile.BANK).peers == tuple(general)
    other_small = company('Other Small Finance Bank')
    assert select_peers(small, [target, other_small], Profile.BANK).peers[0] == other_small


def test_peer_targets_keep_latest_exact_pair_without_discarding_issuer_history():
    entity = uuid4()
    facts = [Fact(id=uuid4(), entity_id=entity, metric_key='deposits', value_decimal=Decimal(year),
        unit_normalized='INR_crore', currency='INR', period_end=date(year, 6, 30), period_type='instant',
        scope='standalone', definition_id='deposits', status='verified', passage_id=uuid4())
        for year in range(2020, 2027)]
    selected = comparison_targets(facts)
    assert {f.period_end.year for f in selected} == {2025, 2026}
    assert len(facts) == 7
    assert comparison_targets(facts[:1]) == []


def test_sparse_verified_series_registers_adjacent_quarter_changes_and_bps():
    entity = uuid4()
    facts = [Fact(id=uuid4(), entity_id=entity, metric_key='gnpa', value_decimal=Decimal(value),
        unit_normalized='percent', period_end=end, period_type='instant', scope='standalone',
        definition_id='gnpa', status='verified', passage_id=uuid4()) for end, value in
        [(date(2025, 6, 30), '1.40'), (date(2026, 3, 31), '1.15'), (date(2026, 6, 30), '1.17')]]
    calculations = derive_calculations(facts)
    sequential = [c for c in calculations if c.input_fact_ids == [facts[2].id, facts[1].id]]
    assert {(c.formula_id, c.output_value) for c in sequential} == {
        ('change_pp', Decimal('.02')), ('change_bps', Decimal('2'))}
    assert not any(c.input_fact_ids == [facts[1].id, facts[0].id] for c in calculations)
    assert len({c.id for c in calculations}) == len(calculations)
    facts[1].scope = 'consolidated'
    assert not any(c.input_fact_ids == [facts[2].id, facts[1].id] for c in derive_calculations(facts))


def test_live_complete_angle_does_not_spend_final_window_on_optional_metrics():
    research = LiveResearch.__new__(LiveResearch)
    research.extraction_paused = False
    research.is_deep = False
    research.company = SimpleNamespace(business_profiles=[Profile.BANK])
    research.facts, research.calculations = [], []
    research.cutoff = date(2026, 10, 17)
    research.budget = SimpleNamespace(model_calls=1, max_model_calls=100, remaining_seconds=lambda: 500)
    research.analysis_reserve = lambda: 300
    research.angle_evidence_ready = lambda: True
    research.extract = lambda **kwargs: (_ for _ in ()).throw(AssertionError('Optional extraction must be skipped'))
    research.collect_operating_metrics()


def test_roster_remains_twelve_real_companies():
    assert len([s for _, s, _ in UNIVERSE_SEED if s != 'SYNTHBANK']) == 12


def test_optional_page_workers_inherit_the_parent_review_reserve(store, settings, monkeypatch):
    settings.max_run_seconds = settings.demo_target_seconds = 600
    settings.stage_request_seconds = dict.fromkeys(
        ['hypothesizing', 'extracting', 'normalizing', 'challenging', 'composing', 'verifying'], 120)
    rid = store.create_run(store.search_companies('ICICIBANK')[0], date(2026, 10, 17), RunMode.LIVE)
    parent = LiveResearch(SimpleNamespace(store=store, settings=settings), rid,
        store.get_summary(rid).company, date(2026, 10, 17), Budget(30, 30, 100, 0))
    document = SimpleNamespace(id=uuid4(), published_at=None, cutoff_eligibility='eligible')
    document.model_copy = lambda **kwargs: document
    passage = SimpleNamespace(id=uuid4(), document_id=document.id)
    parent.documents = [document]
    checked = []
    def extract(worker, **kwargs):
        checked.append(worker.calls.stage_deadline_reserves['normalizing'])
        assert checked[-1] == parent.analysis_reserve() == 390
    monkeypatch.setattr(LiveResearch, 'extract', extract)
    parent.extract_with_agents([passage], historical=True)
    assert checked == [390]


def test_peer_directory_is_not_truncated_by_autocomplete(store):
    from signal_research.db.models import CompanyModel
    with store.session_factory() as session:
        for i in range(30):
            session.add(CompanyModel(id=str(uuid4()), legal_name=f'Aardvark Finance {i:02}', symbols=[f'Q{i}'],
                aliases=[], verified_ir_domains=[], business_profiles=['nbfc'], identity_source_ids=[]))
        session.commit()
    assert len(store.search_companies('')) == 20
    banks = store.peer_candidates(Profile.BANK)
    assert {'HDFCBANK', 'ICICIBANK', 'SBIN', 'KOTAKBANK', 'AXISBANK'} <= {s for c in banks for s in c.symbols}
    assert all(Profile.BANK in c.business_profiles for c in banks)
