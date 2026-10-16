"""Comparative presentation headers enter the same independent numerical gates."""
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
def test_presentation_quarters_require_independent_column_review(store, tmp_path, monkeypatch, supported):
    company = store.search_companies('JIOFIN')[0]
    issuer = 'https://jfs.in/financial-results.html'
    text = (f'{company.legal_name}\nConsolidated Profit & Loss\nINR in million\n'
            'Dec’25 Sept’25 Dec’24 9M FY FY\nSr. No. Particulars\n'
            'Quarter Quarter Quarter 2025-26 2024-25\n'
            'Revenue from operations 100 90 70 260 240\nNet profit 20 18 12 50 40')
    raw = ('<html><meta property="article:published_time" content="2026-02-09">'
           '<pre>' + text + '</pre></html>').encode()
    path = tmp_path / 'results.html'
    path.write_bytes(raw)
    def search(self, *args, **kwargs):
        return [SearchHit(issuer, 'Quarterly financial results', '', 1, 'test')]
    def fetch(self, url):
        if url != issuer:
            return FetchResult(url, url, 404, 'text/html', None, None, 'No fixture disclosure')
        return FetchResult(url, url, 200, 'text/html', hashlib.sha256(raw).hexdigest(), str(path))
    def generate(self, schema, messages, *args):
        payload = json.loads(messages[1]['content'])
        if schema.__name__ == 'ExtractedFactBatch':
            periods = payload['source_declared_durations']
            assert [p['period_end'] for p in periods] == ['2025-12-31', '2025-09-30', '2024-12-31']
            result = schema(facts=[dict(metric_key=key, value_raw=value, unit_raw='INR million', currency='INR',
                period_start=p['period_start'], period_end=p['period_end'], period_type='duration',
                scope='consolidated', passage_id=payload['passage_id'], extraction_confidence='.99')
                for key, values in [('revenue', ['100', '90', '70']), ('net_profit', ['20', '18', '12'])]
                for p, value in zip(periods, values, strict=True)])
        elif schema.__name__ == 'FactReview':
            result = schema(verdicts=[dict(index=c['index'], supported=supported,
                                          reason='Independent row and quarter column review') for c in payload['candidates']])
        elif schema.__name__ == 'HypothesisBatch':
            result = schema(candidates=[], missing_evidence=['A non-obvious corroborated relationship'])
        else:
            raise AssertionError(schema.__name__)
        return result, SimpleNamespace(input_tokens=100, output_tokens=100)
    monkeypatch.setattr(TavilySearchProvider, 'search', search)
    monkeypatch.setattr(PublicFetcher, 'fetch', fetch)
    monkeypatch.setattr(OpenAIProvider, 'generate', generate)
    settings = Settings(data_dir=tmp_path, allow_unknown_cost=True, tavily_api_key='test-only',
                        openai_api_key='test-only', openai_model_research='research', openai_model_extract='extract')
    run_id = store.create_run(company, date(2026, 10, 8), RunMode.LIVE)
    store.lease_next('quarter-review')
    ResearchMachine(store, settings).process(run_id)
    report = store.get_report(run_id)
    assert report and store.get_summary(run_id).status.value == 'completed'
    assert len(report.facts) == (6 if supported else 0)
    assert {f.period_end for f in report.facts} <= {date(2025, 12, 31), date(2025, 9, 30), date(2024, 12, 31)}
    assert not report.discoveries  # Comparable numbers alone do not prove a discovery.
