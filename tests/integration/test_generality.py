import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from signal_research.domain.enums import Profile, RunMode
from signal_research.domain.schemas import Company, Passage
from signal_research.extraction.bank_tables import comparative_bank_batch
from signal_research.extraction.models import ExtractedFactBatch, ExtractedFactCandidate
from signal_research.finance.registry import metrics_for_profile
from signal_research.main import create_app
from signal_research.providers.llm.openai_provider import OpenAIProvider
from signal_research.providers.search.base import SearchHit
from signal_research.providers.search.tavily_provider import TavilySearchProvider
from signal_research.research.entity_resolver import resolve
from signal_research.research.novelty import Novelty, classify_novelty
from signal_research.research.planner import initial_plan
from signal_research.research.readiness import live_readiness
from signal_research.research.sector import extraction_instruction
from signal_research.retrieval.disclosures import issuer_navigation
from signal_research.retrieval.fetch import FetchResult, PublicFetcher
from signal_research.retrieval.issuer_identity import exchange_issuer_domains
from signal_research.settings import Settings
from signal_research.worker.machine import ResearchMachine


@pytest.mark.parametrize('symbol', [
    'AXISBANK', 'BSE', 'BAJFINANCE', 'BAJAJFINSV', 'HDFCBANK', 'HDFCLIFE',
    'ICICIBANK', 'JIOFIN', 'KOTAKBANK', 'SBILIFE', 'SHRIRAMFIN', 'SBIN'])
def test_each_roster_company_processes_verified_figures_and_honestly_abstains(store, tmp_path, monkeypatch, symbol):
    """Offline workflow regression; search, HTTP sources and model responses are mocked."""
    company = store.search_companies(symbol)[0]
    store.add_verified_issuer_domains(company.id, ['issuer.example'], uuid4())
    company = store.get_company(company.id)
    settings = Settings(data_dir=tmp_path, allow_unknown_cost=True, openai_api_key='test-only',
                        tavily_api_key='test-only', openai_model_extract='extract', openai_model_research='research',
                        model_rate_card_path=tmp_path / 'absent.json')
    source = 'https://issuer.example/results'
    raw = (f'<html><meta property="article:published_time" content="2026-05-15">'
           f'<p>{company.legal_name} consolidated net profit: INR 100 crore for 1 April 2024 '
           'to 31 March 2025; INR 120 crore for 1 April 2025 to 31 March 2026.</p></html>').encode()
    path = tmp_path / 'results.html'
    path.write_bytes(raw)
    monkeypatch.setattr(TavilySearchProvider, 'search', lambda *a, **k: [SearchHit(source, 'Financial results', 'lead', 1, 'mock')])
    monkeypatch.setattr(PublicFetcher, 'fetch', lambda *a, **k: FetchResult(source, source, 200, 'text/html', hashlib.sha256(raw).hexdigest(), str(path)))

    def generate(self, schema, messages, *args, **kwargs):
        payload = json.loads(messages[1]['content'])
        if issubclass(schema, ExtractedFactBatch):
            output = schema(facts=[ExtractedFactCandidate(
                metric_key='net_profit', value_raw=value, unit_raw='INR crore', currency='INR',
                period_start=date(year - 1, 4, 1), period_end=date(year, 3, 31), period_type='duration',
                scope='consolidated', passage_id=payload['passage_id'], extraction_confidence=Decimal('.99')).model_dump()
                for value, year in [('120', 2026), ('100', 2025)]])
        elif schema.__name__ == 'FactReview':
            output = schema(verdicts=[{'index': index, 'supported': True, 'reason': 'Fixture cells match exact issuer and periods.'} for index in range(2)])
        elif schema.__name__ == 'HypothesisBatch':
            output = schema(candidates=[], missing_evidence=['Independent evidence of a non-obvious relationship'])
        else:
            raise AssertionError(schema.__name__)
        return output, SimpleNamespace(input_tokens=100, output_tokens=100)

    monkeypatch.setattr(OpenAIProvider, 'generate', generate)
    run_id = store.create_run(company, date(2026, 10, 8), RunMode.LIVE)
    assert store.lease_next('matrix-test') == run_id
    ResearchMachine(store, settings).process(run_id)
    summary = store.get_summary(run_id)
    assert summary.status.value == 'completed', summary.limitations
    report = store.get_report(run_id)
    assert report.outcome.value == 'insufficient_evidence'
    assert not report.discoveries
    assert len(report.facts) == 2
    assert report.calculations[0].output_value == Decimal('20')


def test_all_roster_companies_fail_preflight_without_creating_jobs(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'api.db'}", data_dir=tmp_path))
    with TestClient(app) as client:
        companies = client.get('/api/v1/companies').json()['items']
        real = [company for company in companies if 'SYNTHBANK' not in company['symbols']]
        assert len(real) == 12
        for company in real:
            profile = Profile(company['business_profiles'][0])
            assert initial_plan(company['legal_name'], profile, company['symbols'][0], '2026-10-11')
            result = client.post('/api/v1/runs', json={
                'company_id': company['id'], 'as_of': '2026-10-08', 'mode': 'live'})
            assert result.status_code == 503
            assert result.json()['code'] == 'LIVE_CONFIGURATION_INCOMPLETE'
        config = client.get('/api/v1/health/configuration').json()
        assert not config['ready']
        assert not any('api_key' in key for key in config)


def test_exact_verified_alias_precedes_substring_matches(store):
    assert resolve(store, 'SBI').company.symbols == ['SBIN']
    assert resolve(store, 'SBI Life').company.symbols == ['SBILIFE']
    assert resolve(store, 'State Bank of India Limited').company.symbols == ['SBIN']
    assert resolve(store, 'HDFC Bnak').company is None


def test_unseen_issuer_uses_same_table_parser_as_existing_issuer():
    original = (Path(__file__).parents[1] / 'fixtures/sbi-comparative-balance.txt').read_text(encoding='utf-8')
    text = original.replace('SBI', 'QFB').replace('State Bank of India', 'Quartz Financial Bank')
    passage = Passage(id=uuid4(), document_id=uuid4(), text=text)
    batch = comparative_bank_batch(passage, SimpleNamespace(legal_name='Quartz Financial Bank'))
    assert batch and len(batch.facts) == 4
    assert batch.facts[0].value_raw == '60,05,805'
    assert batch.facts[0].period_end == date(2026, 6, 30)
    assert comparative_bank_batch(passage, SimpleNamespace(legal_name='Different Financial Bank')) is None


@pytest.mark.parametrize('profile', list(Profile))
def test_sector_guidance_and_metrics_do_not_depend_on_company(profile):
    instruction = extraction_instruction(profile)
    assert "segment='all' only for issuer totals" in instruction
    assert 'SBI' not in instruction and 'HDFC' not in instruction
    assert metrics_for_profile(profile)
    if profile == Profile.LIFE_INSURER:
        assert {'aum', 'vnb_margin', 'persistency_ratio'} <= {m.key for m in metrics_for_profile(profile)}
        assert 'deposits' not in {m.key for m in metrics_for_profile(profile)}


def test_exchange_reference_verifies_unseen_website_without_trusting_search_result():
    company = Company(id=uuid4(), legal_name='Quartz Financial Bank', symbols=['QFB'], isin='INE000000001', business_profiles=[Profile.BANK])
    raw = b'<p>Quartz Financial Bank INE000000001</p><a href="https://quartz.example">Company website</a>'
    text = 'Quartz Financial Bank INE000000001'
    assert exchange_issuer_domains(raw, text, 'https://www.nseindia.com/disclosure', company) == ['quartz.example']
    assert exchange_issuer_domains(raw, text, 'https://untrusted.example/disclosure', company) == []
    assert exchange_issuer_domains(raw, 'Different Financial Bank INE000000001', 'https://www.nseindia.com/disclosure', company) == []
    assert exchange_issuer_domains(raw, 'Quartz Financial Bank', 'https://www.nseindia.com/disclosure', company) == []


def test_navigation_follows_same_issuer_only():
    raw = b'<nav><a href="/investors">Investor Relations</a><a href="https://evil.example">Financial results</a></nav>'
    hits = issuer_navigation(raw, 'https://quartz.example/', ['quartz.example'])
    assert [hit.url for hit in hits] == ['https://quartz.example/investors']


def test_preflight_rejects_malformed_account_prices(tmp_path):
    path = tmp_path / 'rates.json'
    path.write_text('{"models": ["not a model price object"]}', encoding='utf-8')
    settings = Settings(model_rate_card_path=path)
    result = live_readiness(settings)
    assert not result['ready'] and any('models list' in issue for issue in result['issues'])


def test_novelty_filter_does_not_reject_generic_document_titles():
    headline = 'Loan growth diverges from deposits over two comparable periods'
    assert classify_novelty(headline, ['Results', 'Annual report']) != Novelty.ALREADY_COVERED
    assert classify_novelty(headline, [headline]) == Novelty.ALREADY_COVERED


@pytest.mark.parametrize('cutoff_day, learns_domain', [(10, True), (9, False)])
def test_current_retrieval_can_verify_exchange_website_but_cannot_backdate_it(store, tmp_path, monkeypatch, cutoff_day, learns_domain):
    import hashlib
    from types import SimpleNamespace

    from signal_research.providers.search.base import SearchHit
    from signal_research.research.live import LiveResearch
    from signal_research.retrieval.fetch import FetchResult, PublicFetcher
    from signal_research.settings import Settings
    from signal_research.worker.budgets import Budget
    company = store.search_companies('HDFCBANK')[0]
    company.verified_ir_domains = []
    company.isin = company.isin or 'INE040A01034'
    run_id = store.create_run(company, date(2026, 10, cutoff_day), RunMode.LIVE)
    store.lease_next('current-domain-proof')
    raw = f'<p>{company.legal_name} {company.isin}</p><a href="https://verified-new.example">Company website</a>'.encode()
    path = tmp_path / 'exchange.html'; path.write_bytes(raw)
    url = 'https://www.nseindia.com/issuer-disclosure'
    def fetch(self, requested):
        if requested != url:
            return FetchResult(requested, requested, 404, 'text/html', None, None, error='Controlled missing source')
        return FetchResult(url, url, 200, 'text/html', hashlib.sha256(raw).hexdigest(), str(path), retrieved_at='2026-10-10T00:00:00+00:00')
    monkeypatch.setattr(PublicFetcher, 'fetch', fetch)
    settings = Settings(data_dir=tmp_path, model_rate_card_path=tmp_path/'missing-card.json')
    research = LiveResearch(SimpleNamespace(store=store, settings=settings, _cancelled=lambda _: False), run_id, company, date(2026, 10, cutoff_day), Budget(1, 2, 1, 0))
    research.ingest([SearchHit(url, 'Issuer disclosure', '', 1, 'controlled-test')])
    assert ('verified-new.example' in company.verified_ir_domains) == learns_domain
    assert research.documents[0].published_at is None
    proofs = store.artifacts(run_id, 'issuer_domain_verification')
    assert bool(proofs) == learns_domain
    if proofs:
        assert proofs[0]['payload']['availability_basis'] == 'verified_retrieval'
