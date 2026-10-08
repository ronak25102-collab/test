"""Exercise the actual live state machine without credentials or paid requests."""
import hashlib
import json
from datetime import date
from decimal import Decimal

import pytest
from signal_research.domain.enums import RunMode
from signal_research.extraction.models import ExtractedFactBatch, ExtractedFactCandidate
from signal_research.providers.llm.openai_provider import OpenAIProvider
from signal_research.providers.search.base import SearchHit
from signal_research.providers.search.tavily_provider import TavilySearchProvider
from signal_research.research.verifier import verify_report
from signal_research.retrieval.fetch import FetchResult, PublicFetcher
from signal_research.settings import Settings
from signal_research.worker.machine import ResearchMachine


def live_fixture(store, tmp_path, monkeypatch, *, refuted=False, reject_claim=False, dated=True):
    settings = Settings(data_dir=tmp_path, allow_unknown_cost=True, auto_start_worker=False,
                        openai_api_key="test-only", tavily_api_key="test-only", openai_model_extract="extract", openai_model_research="research")
    company = store.search_companies("HDFCBANK")[0]
    issuer = "https://hdfc.bank.in/results"
    context = "https://independent.example/sector-review"
    publication = '<meta property="article:published_time" content="2026-05-15">' if dated else ""
    texts = {
        issuer: f'<html><head>{publication}<title>Results</title></head><body><p>HDFC Bank reported consolidated gross advances of INR 100000 crore at 31 March 2025 and INR 120000 crore at 31 March 2026. Consolidated total deposits were INR 125000 crore at 31 March 2025 and INR 137500 crore at 31 March 2026.</p></body></html>',
        context: f'<html><head>{publication}</head><body><p>Independent banking sector review: loan and deposit growth can diverge during expansion. A growth gap alone cannot establish funding stress. Deposit composition and funding cost are needed to test this mechanism.</p></body></html>',
    }
    counters = {"search": 0, "model": 0, "fetch": 0}
    def search(self, query, domains, as_of, max_results):
        counters["search"] += 1
        urls = [issuer] if domains else [context]
        return [SearchHit(u, "Results" if u == issuer else "Sector review", "Not evidence", 1, "tavily", date(2026, 5, 15)) for u in urls]
    def fetch(self, url):
        counters["fetch"] += 1
        raw = texts[url].encode()
        digest = hashlib.sha256(raw).hexdigest()
        path = tmp_path / f"{digest}.html"
        path.write_bytes(raw)
        return FetchResult(url, url, 200, "text/html", digest, str(path))
    def generated(self, schema, messages, model_role, deadline, max_output_tokens):
        counters["model"] += 1
        p = json.loads(messages[1]["content"])
        if schema is ExtractedFactBatch:
            output = ExtractedFactBatch(facts=[ExtractedFactCandidate(metric_key=metric, value_raw=value, unit_raw="INR crore", currency="INR", period_end=date(year, 3, 31), scope="consolidated", passage_id=p["passage_id"], extraction_confidence=Decimal(".99"), evidence_quote=p["passage_text"])
                                             for metric, value, year in [("gross_advances", "100000", 2025), ("gross_advances", "120000", 2026), ("deposits", "125000", 2025), ("deposits", "137500", 2026)]])
        elif schema.__name__ == "FactReview":
            output = schema(verdicts=[{"index": i, "supported": True, "reason": "Exact cell/date/entity/scope/scale binding matched"} for i in range(4)])
        elif schema.__name__ == "HypothesisBatch":
            output = schema(candidates=[{"statement": "Advances outpaced deposits", "mechanism": "Balance expansion may change the funding mix", "fact_ids": [f["id"] for f in p["facts"]], "calculation_ids": [c["id"] for c in p["calculations"]], "next_query": "HDFC Bank funding mix disclosures", "opposing_query": "HDFC Bank reclassification acquisition funding growth alternative", "falsification": "A comparable reversal of the growth gap", "significance": 4, "novelty": 3}], missing_evidence=[])
        elif schema.__name__ == "Challenge":
            output = schema(refuted=refuted, unresolved=True, strongest_alternative="Growth alone does not establish funding stress", reason="Composition and cost remain untested", relevant_passage_ids=[v["id"] for v in p["passages"]])
        elif schema.__name__ == "DiscoveryDraft":
            ids = [f["id"] for f in p["facts"]]
            context_ids = [v["id"] for v in p["passages"] if "Independent banking" in v["text"]]
            gap = next(c["id"] for c in p["calculations"] if c["formula_id"] == "growth_gap")
            def statement(text, kind="derived", contextual=False):
                return {"text": text, "kind": kind, "fact_ids": [] if contextual else ids, "passage_ids": context_ids if contextual else [], "calculation_ids": [] if contextual else [gap]}
            headline = statement("HDFC Bank advances grew faster than deposits on comparable consolidated year-end balances; funding stress is not established.")
            headline["passage_ids"] = context_ids
            output = schema(headline=headline, why_it_matters=[statement("Advances grew 20%, while deposits grew 10%."), statement("The reproducible growth gap is 10 percentage points."), statement("Independent context requires funding-composition evidence before inferring stress.", "inferred", True)], counterargument=statement("Expansion can create a growth gap without funding stress.", "inferred", True), falsification="Reconsider if later comparable disclosures reverse the advances/deposit growth gap.")
        elif schema.__name__ == "SemanticReview":
            output = schema(verdicts=[{"claim_id": c["id"], "supported": not reject_claim, "reason": "All linked source spans, inputs and qualifications reviewed"} for c in p["claims"]], falsification_is_observable=True, contains_investment_recommendation=False)
        else:
            raise AssertionError(schema)
        return output, type("Usage", (), {"input_tokens": 100, "output_tokens": 100})()
    monkeypatch.setattr(TavilySearchProvider, "search", search)
    monkeypatch.setattr(PublicFetcher, "fetch", fetch)
    monkeypatch.setattr(OpenAIProvider, "generate", generated)
    run_id = store.create_run(company, date(2026, 10, 8), RunMode.LIVE)
    assert store.lease_next("offline-live") == run_id
    return settings, run_id, counters


def test_live_publishes_evidence_backed_discovery(store, tmp_path, monkeypatch):
    settings, run_id, calls = live_fixture(store, tmp_path, monkeypatch)
    ResearchMachine(store, settings).process(run_id)
    summary = store.get_summary(run_id)
    assert summary.status.value == "completed", summary.limitations
    report = verify_report(store.get_report(run_id))
    assert report.outcome.value == "discovery"
    assert report.source_coverage["synthetic"] is False
    assert report.discoveries[0].counterargument.unresolved
    assert report.discoveries[0].evidence_strength.value == "Weak"
    assert calls["search"] == 5 and calls["fetch"] == 2
    assert summary.budget["model_calls"] == calls["model"]


@pytest.mark.parametrize("options", [{"refuted": True}, {"reject_claim": True}, {"dated": False}])
def test_live_abstains_when_a_publication_gate_fails(store, tmp_path, monkeypatch, options):
    settings, run_id, calls = live_fixture(store, tmp_path, monkeypatch, **options)
    ResearchMachine(store, settings).process(run_id)
    summary = store.get_summary(run_id)
    assert summary.status.value == "completed", summary.limitations
    assert store.get_report(run_id).outcome.value == "insufficient_evidence"
    if not options.get("dated", True):
        assert calls["model"] == 0  # search-engine dates cannot authorize publication


def test_resume_reuses_verified_checkpoint_without_repeating_paid_calls(store, tmp_path, monkeypatch):
    settings, run_id, calls = live_fixture(store, tmp_path, monkeypatch)
    original = store.save_report
    monkeypatch.setattr(store, "save_report", lambda report: (_ for _ in ()).throw(RuntimeError("simulated crash before publication")))
    ResearchMachine(store, settings).process(run_id)
    assert store.get_summary(run_id).status.value == "failed"
    before = calls.copy()
    spend = store.get_summary(run_id).budget.copy()
    assert store.load_checkpoint(run_id, "verifying")
    monkeypatch.setattr(store, "save_report", original)
    store.resume(run_id)
    store.lease_next("recovered-worker")
    ResearchMachine(store, settings).process(run_id)
    assert store.get_summary(run_id).status.value == "completed"
    assert calls == before
    assert store.get_summary(run_id).budget == spend


def test_budget_stops_live_before_any_provider_request(store, tmp_path, monkeypatch):
    settings, run_id, calls = live_fixture(store, tmp_path, monkeypatch)
    settings.max_run_seconds = 0
    ResearchMachine(store, settings).process(run_id)
    assert store.get_summary(run_id).status.value == "failed"
    assert calls == {"search": 0, "fetch": 0, "model": 0}
