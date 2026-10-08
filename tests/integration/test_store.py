import json
from datetime import date
from decimal import Decimal

from signal_research.domain.enums import RunMode
from signal_research.extraction.models import ExtractedFactBatch, ExtractedFactCandidate
from signal_research.providers.llm.openai_provider import OpenAIProvider
from signal_research.providers.search.base import SearchHit
from signal_research.providers.search.tavily_provider import TavilySearchProvider
from signal_research.retrieval.fetch import FetchResult, PublicFetcher
from signal_research.settings import Settings
from signal_research.worker.machine import ResearchMachine


def test_run_idempotency_and_events(store):
    company = store.search_companies("SYNTHBANK")[0]
    first = store.create_run(company, date(2026, 10, 8), RunMode.REPLAY, "same-request")
    second = store.create_run(company, date(2026, 10, 8), RunMode.REPLAY, "same-request")
    assert first == second
    events = store.get_events(first)
    assert events[0].event_type == "run_queued"


def test_cancel_is_terminal_request(store):
    company = store.search_companies("SYNTHBANK")[0]
    run_id = store.create_run(company, date(2026, 10, 8), RunMode.REPLAY)
    assert store.request_cancel(run_id) == "cancelled"
    assert store.is_cancelled(run_id)


def test_live_pipeline_validates_model_facts_before_abstaining(store, tmp_path, monkeypatch):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'live.db'}", data_dir=tmp_path, allow_unknown_cost=True, openai_api_key="configured", openai_model_extract="extractor", openai_model_research="researcher", auto_start_worker=False)
    company = store.search_companies("HDFCBANK")[0]
    run_id = store.create_run(company, date(2026, 10, 8), RunMode.LIVE)
    store.lease_next("live-integration")
    html_path = tmp_path / "results.html"
    html_path.write_text('<html><head><title>Results</title><meta property="article:published_time" content="2026-05-15"></head><p>HDFC Bank consolidated gross advances were INR 1,20,000 crore at 31 March 2026.</p></html>')
    hit = SearchHit("https://hdfc.bank.in/results", "Quarterly results", "lead", 1, "tavily", date(2026, 5, 15))
    monkeypatch.setattr(TavilySearchProvider, "search", lambda self, query, domains, as_of, max_results: [hit])
    monkeypatch.setattr(PublicFetcher, "fetch", lambda self, url: FetchResult(url, url, 200, "text/html", "a" * 64, str(html_path), None))

    def generated(self, schema, messages, model_role, deadline, max_output_tokens):
        if schema.__name__ == "FactReview":
            return schema(verdicts=[{"index": 0, "supported": True, "reason": "Exact issuer cell, date, unit and scope matched"}]), type("Usage", (), {"input_tokens": 10, "output_tokens": 10})()
        passage_id = json.loads(messages[1]["content"])["passage_id"]
        candidate = ExtractedFactCandidate(metric_key="gross_advances", value_raw="1,20,000", unit_raw="INR crore", currency="INR", period_end=date(2026, 3, 31), scope="consolidated", passage_id=passage_id, extraction_confidence=Decimal("0.99"))
        return ExtractedFactBatch(facts=[candidate]), type("Usage", (), {"input_tokens": 10, "output_tokens": 10})()

    monkeypatch.setattr(OpenAIProvider, "generate", generated)
    ResearchMachine(store, settings).process(run_id)
    report = store.get_report(run_id)
    assert report is not None
    assert report.outcome.value == "insufficient_evidence"
    assert report.facts and report.facts[0].value_decimal == Decimal("120000")
    assert store.provider_calls(run_id)
