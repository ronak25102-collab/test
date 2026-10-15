"""An inaccessible issuer portal must not prevent reading an exchange filing."""
import hashlib
import json
from datetime import date
from types import SimpleNamespace

import pytest
from signal_research.domain.enums import RunMode
from signal_research.providers.llm.openai_provider import OpenAIProvider
from signal_research.providers.search.base import SearchHit
from signal_research.providers.search.tavily_provider import TavilySearchProvider
from signal_research.retrieval.fetch import FetchResult, PublicFetcher
from signal_research.settings import Settings
from signal_research.worker.machine import ResearchMachine


@pytest.mark.parametrize('supported', [True, False])
def test_blocked_portal_recovers_exchange_facts_only_after_independent_review(store, tmp_path, monkeypatch, supported):
    company = store.search_companies('JIOFIN')[0]
    settings = Settings(data_dir=tmp_path, allow_unknown_cost=True, tavily_api_key='test-only',
        openai_api_key='test-only', openai_model_research='research', openai_model_extract='extract',
        model_rate_card_path=tmp_path / 'absent.json')
    issuer = 'https://jfs.in/results.pdf'
    exchange = 'https://nsearchives.nseindia.com/corporate/ixbrl/results.html'
    raw = f'''<html><table>
    <tr><td>Name of company</td><td>{company.legal_name} Limited</td></tr>
    <tr><td>NSE Symbol</td><td>JIOFIN</td></tr>
    <tr><td>Description of presentation currency</td><td>INR</td></tr>
    <tr><td>Level of rounding used in financial results</td><td>Lakhs</td></tr></table>
    <table><tr><td>A</td><td>Date of start of reporting period</td><td>01-04-2025</td></tr>
    <tr><td>B</td><td>Date of end of reporting period</td><td>31-03-2026</td></tr>
    <tr><td>D</td><td>Nature of report standalone or consolidated</td><td>Consolidated</td></tr>
    <tr><td></td><td>Total Revenue From Operations</td><td>40,000.00</td></tr>
    <tr><td>15</td><td>Total profit (loss) for period</td><td>6,000.00</td></tr></table></html>'''.encode()
    path = tmp_path / 'exchange.html'
    path.write_bytes(raw)
    depths = []
    def search(self, query, *args):
        depths.append(self.settings.tavily_search_depth)
        if 'INTEGRATED FILING' in query:
            return [SearchHit(exchange, 'Financial filing', '', 1, 'test')]
        return [SearchHit(issuer, 'Financial results', '', 1, 'test')]
    def fetch(self, url):
        if url != exchange:
            return FetchResult(url, url, 403, 'application/pdf', None, None, 'source access returned 403')
        return FetchResult(url, url, 200, 'text/html', hashlib.sha256(raw).hexdigest(), str(path),
                           retrieved_at='2026-07-16T12:00:00+00:00')
    def generate(self, schema, messages, *args):
        payload = json.loads(messages[1]['content'])
        if schema.__name__ == 'FactReview':
            result = schema(verdicts=[{'index': item['index'], 'supported': supported,
                'reason': 'Independent column review verdict'} for item in payload['candidates']])
        elif schema.__name__ == 'HypothesisBatch':
            result = schema(candidates=[], missing_evidence=['A corroborated non-obvious relationship'])
        else:
            raise AssertionError('Literal table extraction must not require generation: ' + schema.__name__)
        return result, SimpleNamespace(input_tokens=100, output_tokens=100)
    monkeypatch.setattr(TavilySearchProvider, 'search', search)
    monkeypatch.setattr(PublicFetcher, 'fetch', fetch)
    monkeypatch.setattr(OpenAIProvider, 'generate', generate)
    run_id = store.create_run(company, date(2026, 10, 8), RunMode.LIVE)
    store.lease_next('exchange-recovery')
    ResearchMachine(store, settings).process(run_id)
    report = store.get_report(run_id)
    assert report and store.get_summary(run_id).status.value == 'completed'
    assert len(report.facts) == (2 if supported else 0)
    assert len(report.calculations) == (1 if supported else 0)
    assert report.source_coverage['documents_used'] == (1 if supported else 0)
    assert any(d.document_type == 'issuer_disclosure' and d.origin_family_id == f'issuer:{company.id}' for d in report.documents)
    assert 'advanced' in depths
    assert any(c['search_credits'] == 2 for c in store.provider_calls(run_id) if c['provider'] == 'tavily')
    assert not report.discoveries  # Accessible figures alone do not prove novelty.
