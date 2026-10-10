"""Exercise the actual live state machine without credentials or paid requests."""
import hashlib
import io
import json
from datetime import date
from decimal import Decimal

import pytest
from reportlab.pdfgen import canvas
from signal_research.domain.enums import RunMode
from signal_research.extraction.models import ExtractedFactBatch, ExtractedFactCandidate
from signal_research.providers.llm.openai_provider import OpenAIProvider
from signal_research.providers.search.base import SearchHit
from signal_research.providers.search.tavily_provider import TavilySearchProvider
from signal_research.research.verifier import verify_report
from signal_research.retrieval.fetch import FetchResult, PublicFetcher
from signal_research.settings import Settings
from signal_research.worker.machine import ResearchMachine


def live_fixture(store, tmp_path, monkeypatch, *, refuted=False, reject_claim=False, dated=True, linked=False, no_facts=False, duplicate_review=False):
    settings = Settings(data_dir=tmp_path, allow_unknown_cost=True, auto_start_worker=False,
                        openai_api_key="test-only", tavily_api_key="test-only", openai_model_extract="extract", openai_model_research="research")
    company = store.search_companies("HDFCBANK")[0]
    issuer = "https://www.hdfc.bank.in/about-us/investor-relations/financial-results"
    context = "https://independent.example/sector-review"
    publication = '<meta property="article:published_time" content="2026-05-15">' if dated else ""
    texts = {
        issuer: f'<html><head>{publication}<title>Results</title></head><body><p>HDFC Bank reported consolidated gross advances of INR 100000 crore at 31 March 2025 and INR 120000 crore at 31 March 2026. Consolidated total deposits were INR 125000 crore at 31 March 2025 and INR 137500 crore at 31 March 2026.</p></body></html>',
        context: f'<html><head>{publication}</head><body><p>Independent banking sector review: loan and deposit growth can diverge during expansion. A growth gap alone cannot establish funding stress. Deposit composition and funding cost are needed to test this mechanism.</p></body></html>',
    }
    disclosure = "https://hdfc.bank.in/financial-results.pdf"
    if linked:
        output = io.BytesIO()
        pdf = canvas.Canvas(output)
        text = pdf.beginText(40, 780)
        text.textLine("Analyst Presentation")
        if dated:
            text.textLine("15.05.2026")
        text.textLine("HDFC Bank reported consolidated gross advances of INR 100000 crore at 31 March 2025")
        text.textLine("and INR 120000 crore at 31 March 2026. Consolidated total deposits were INR")
        text.textLine("125000 crore at 31 March 2025 and INR 137500 crore at 31 March 2026.")
        pdf.drawText(text)
        pdf.save()
        texts[disclosure] = output.getvalue()
        texts[issuer] = '<html><body><a href="/financial-results.pdf">Analyst Presentation FY2026</a></body></html>'
    counters = {"search": 0, "model": 0, "fetch": 0}
    def search(self, query, domains, as_of, max_results):
        counters["search"] += 1
        urls = [issuer] if domains else [context]
        return [SearchHit(u, "Results" if u == issuer else "Sector review", "Not evidence", 1, "tavily", date(2026, 5, 15)) for u in urls]
    def fetch(self, url):
        counters["fetch"] += 1
        raw = texts[url] if isinstance(texts[url], bytes) else texts[url].encode()
        digest = hashlib.sha256(raw).hexdigest()
        suffix = ".pdf" if raw.startswith(b"%PDF") else ".html"
        path = tmp_path / f"{digest}{suffix}"
        path.write_bytes(raw)
        final_url = "https://hdfc.bank.in/investor-presentations" if linked and url == issuer else url
        return FetchResult(url, final_url, 200, "application/pdf" if suffix == ".pdf" else "text/html", digest, str(path))
    def generated(self, schema, messages, model_role, deadline, max_output_tokens):
        counters["model"] += 1
        p = json.loads(messages[1]["content"])
        if issubclass(schema, ExtractedFactBatch):
            output = schema(facts=[ExtractedFactCandidate(metric_key=metric, value_raw=value, unit_raw="INR crore", currency="INR", period_end=date(year, 3, 31), scope="consolidated", passage_id=p["passage_id"], extraction_confidence=Decimal(".99"), evidence_quote=None).model_dump()
                                             for metric, value, year in [("gross_advances", "100000", 2025), ("gross_advances", "120000", 2026), ("deposits", "125000", 2025), ("deposits", "137500", 2026)]])
            if no_facts:
                output = schema(facts=[], missing_metrics=["gross_advances"], notes=["Complete dates and financial scope could not be verified."])
        elif schema.__name__ == "FactReview":
            assert [c["index"] for c in p["candidates"]] == list(range(4))
            output = schema(verdicts=[{"index": 0 if duplicate_review else i, "supported": True, "reason": "Exact cell/date/entity/scope/scale binding matched"} for i in range(4)])
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


def test_duplicate_review_indices_cannot_approve_any_facts(store, tmp_path, monkeypatch):
    settings, run_id, calls = live_fixture(store, tmp_path, monkeypatch, duplicate_review=True)
    ResearchMachine(store, settings).process(run_id)
    report = store.get_report(run_id)
    assert not report.facts and report.outcome.value == "insufficient_evidence"
    rejected = store.artifacts(run_id, "fact_extraction")[0]["payload"]["rejected"]
    assert any("duplicate or missing" in item["reason"] for item in rejected)


def test_blocked_news_is_replaced_by_original_independent_rating_context(store, tmp_path, monkeypatch):
    settings, run_id, counters = live_fixture(store, tmp_path, monkeypatch)
    original_search, original_fetch = TavilySearchProvider.search, PublicFetcher.fetch
    rating = "https://www.icra.in/rating-report"
    recovery = []
    def search(self, query, domains, cutoff, maximum):
        if domains and "icra.in" in domains:
            recovery.append(query)
            return [SearchHit(rating, "Independent rating rationale", "lead only", 1, "tavily")]
        return original_search(self, query, domains, cutoff, maximum)
    def fetch(self, url):
        if url == "https://independent.example/sector-review":
            return FetchResult(url, url, 403, "text/html", None, None, "source access returned 403")
        if url != rating:
            return original_fetch(self, url)
        raw = b'<html><meta property="article:published_time" content="2026-05-15"><p>Independent banking sector review: loan and deposit growth can diverge during expansion. A growth gap alone cannot establish funding stress. Deposit composition and funding cost are needed to test this mechanism.</p></html>'
        digest = hashlib.sha256(raw).hexdigest()
        path = tmp_path / f"{digest}.html"
        path.write_bytes(raw)
        return FetchResult(url, url, 200, "text/html", digest, str(path))
    monkeypatch.setattr(TavilySearchProvider, "search", search)
    monkeypatch.setattr(PublicFetcher, "fetch", fetch)
    ResearchMachine(store, settings).process(run_id)
    report = store.get_report(run_id)
    assert report.outcome.value == "discovery"
    assert recovery and '"HDFC Bank"' in recovery[0]
    assert any(d.origin_family_id == "icra.in" for d in report.documents)


def test_withheld_candidate_preserves_verified_numbers(store, tmp_path, monkeypatch):
    settings, run_id, counters = live_fixture(store, tmp_path, monkeypatch, refuted=True)
    ResearchMachine(store, settings).process(run_id)
    report = verify_report(store.get_report(run_id))
    assert not report.discoveries and report.facts and report.calculations
    assert store.get_summary(run_id).progress["calculations_completed"] == len(report.calculations)


def test_live_follows_issuer_index_to_dated_pdf_before_extracting(store, tmp_path, monkeypatch):
    settings, run_id, calls = live_fixture(store, tmp_path, monkeypatch, linked=True)
    ResearchMachine(store, settings).process(run_id)
    summary = store.get_summary(run_id)
    assert summary.status.value == "completed", summary.limitations
    report = verify_report(store.get_report(run_id))
    assert report.outcome.value == "discovery"
    assert calls["fetch"] == 3
    assert any(d.mime_type == "application/pdf" and d.published_at.date() == date(2026, 5, 15) for d in report.documents)


def test_pdf_parse_limit_is_separate_from_download_timeout(store, tmp_path, monkeypatch):
    import signal_research.research.live as live
    settings, run_id, calls = live_fixture(store, tmp_path, monkeypatch, linked=True)
    settings.source_request_timeout_seconds = 1
    settings.pdf_parse_timeout_seconds = 45
    timeouts = []
    original = live.bounded_parse_pdf
    def parse(document_id, path, timeout):
        timeouts.append(timeout)
        return original(document_id, path, timeout)
    monkeypatch.setattr(live, "bounded_parse_pdf", parse)
    ResearchMachine(store, settings).process(run_id)
    assert timeouts == [45]
    assert store.get_summary(run_id).status.value == "completed"


def test_linked_disclosures_obey_fetch_budget(store, tmp_path, monkeypatch):
    settings, run_id, calls = live_fixture(store, tmp_path, monkeypatch, linked=True)
    settings.max_fetch_documents = 1
    ResearchMachine(store, settings).process(run_id)
    assert calls["fetch"] == 1 and calls["model"] == 0
    assert store.get_report(run_id).outcome.value == "insufficient_evidence"


def test_linked_pdf_without_publication_date_remains_ineligible(store, tmp_path, monkeypatch):
    settings, run_id, calls = live_fixture(store, tmp_path, monkeypatch, linked=True, dated=False)
    ResearchMachine(store, settings).process(run_id)
    assert calls["model"] == 0
    assert store.get_report(run_id).outcome.value == "insufficient_evidence"


def test_extraction_gaps_are_explained_in_the_report(store, tmp_path, monkeypatch):
    settings, run_id, calls = live_fixture(store, tmp_path, monkeypatch, linked=True, no_facts=True)
    ResearchMachine(store, settings).process(run_id)
    report = store.get_report(run_id)
    assert report.outcome.value == "insufficient_evidence"
    assert "period, unit and scope" in report.abstention.missing_requirements[0]
    assert "Extraction gap: Complete dates and financial scope could not be verified." in report.limitations
    artifact = store.artifacts(run_id, "fact_extraction")[0]["payload"]
    assert artifact["missing_metrics"] == ["gross_advances"]
    assert artifact["notes"]


def test_live_recovers_a_dated_annual_disclosure_when_initial_sources_are_undated(store, tmp_path, monkeypatch):
    settings, run_id, calls = live_fixture(store, tmp_path, monkeypatch, dated=False)
    original_search, original_fetch = TavilySearchProvider.search, PublicFetcher.fetch
    annual_url = "https://hdfc.bank.in/dated-annual-report"
    annual_queries = []
    def search(self, query, domains, cutoff, max_results):
        if '"annual report"' in query:
            annual_queries.append((query, domains))
            return [SearchHit(annual_url, "Annual report", "Not evidence", 1, "tavily")]
        return original_search(self, query, domains, cutoff, max_results)
    def fetch(self, url):
        if url != annual_url:
            return original_fetch(self, url)
        raw = b'<html><meta property="article:published_time" content="2026-05-15"><p>HDFC Bank reported consolidated gross advances of INR 100000 crore at 31 March 2025 and INR 120000 crore at 31 March 2026. Consolidated total deposits were INR 125000 crore at 31 March 2025 and INR 137500 crore at 31 March 2026.</p></html>'
        digest = hashlib.sha256(raw).hexdigest()
        path = tmp_path / f"{digest}.html"
        path.write_bytes(raw)
        return FetchResult(url, url, 200, "text/html", digest, str(path))
    monkeypatch.setattr(TavilySearchProvider, "search", search)
    monkeypatch.setattr(PublicFetcher, "fetch", fetch)
    ResearchMachine(store, settings).process(run_id)
    summary = store.get_summary(run_id)
    assert summary.status.value == "completed", summary.limitations
    assert len(annual_queries) == 1 and annual_queries[0][1] == store.search_companies("HDFCBANK")[0].verified_ir_domains
    assert any(artifact["payload"]["accepted"] for artifact in store.artifacts(run_id, "fact_extraction"))
    assert calls["model"] > 0


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


@pytest.mark.parametrize("limit", ["deadline", "model_calls"])
def test_limit_during_challenge_saves_verified_partial_report(store, tmp_path, monkeypatch, limit):
    from datetime import UTC, datetime, timedelta

    from signal_research.research.live import LiveResearch

    settings, run_id, calls = live_fixture(store, tmp_path, monkeypatch)
    original = LiveResearch.challenge
    def reach_limit(self, hypothesis):
        if limit == "deadline":
            self.budget.deadline = datetime.now(UTC) - timedelta(seconds=1)
        else:
            self.budget.max_model_calls = self.budget.model_calls
        return original(self, hypothesis)
    monkeypatch.setattr(LiveResearch, "challenge", reach_limit)
    ResearchMachine(store, settings).process(run_id)
    summary = store.get_summary(run_id)
    assert summary.status.value == "completed", summary.limitations
    report = verify_report(store.get_report(run_id))
    assert report.outcome.value == "partial"
    assert len(report.facts) == 4 and report.calculations
    assert not report.discoveries and report.publication_status.value == "abstained"
    assert report.generation_metadata["stopped_by_limit"]
    assert calls["model"] == 3  # Extraction, independent fact review, hypothesis only.
    before = calls.copy()
    ResearchMachine(store, settings).process(run_id)
    assert calls == before


def test_expired_partial_checkpoint_recovers_after_publication_crash(store, tmp_path, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from signal_research.research.live import LiveResearch

    settings, run_id, calls = live_fixture(store, tmp_path, monkeypatch)
    def expire(self, hypothesis):
        self.budget.deadline = datetime.now(UTC) - timedelta(seconds=1)
        self.budget.check()
    monkeypatch.setattr(LiveResearch, "challenge", expire)
    original = store.save_report
    monkeypatch.setattr(store, "save_report", lambda report: (_ for _ in ()).throw(RuntimeError("publication crash")))
    ResearchMachine(store, settings).process(run_id)
    assert store.get_summary(run_id).status.value == "failed"
    checkpoint = store.load_checkpoint(run_id, "verifying")
    assert checkpoint["outcome"] == "partial" and checkpoint["facts"]
    before, budget = calls.copy(), store.get_summary(run_id).budget.copy()
    monkeypatch.setattr(store, "save_report", original)
    store.resume(run_id)
    store.lease_next("partial-recovery")
    ResearchMachine(store, settings).process(run_id)
    assert store.get_summary(run_id).status.value == "completed"
    assert store.get_report(run_id).outcome.value == "partial"
    assert calls == before and store.get_summary(run_id).budget == budget
