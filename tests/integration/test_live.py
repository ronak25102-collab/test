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
    settings = Settings(data_dir=tmp_path, allow_unknown_cost=True, auto_start_worker=False, fast_verified_proposals=False,
                        tavily_api_key="test-only", openai_api_key="test-only", openai_model_extract="extract", openai_model_research="research")
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
        if url not in texts:
            return FetchResult(url, url, 404, "text/html", None, None, error="Fixture has no disclosure at this navigation URL")
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
            if p.get('candidates') and 'text' in p['candidates'][0]:
                return schema(verdicts=[{'index': 0, 'supported': True, 'reason': 'Rewrite preserves the reviewed arithmetic.'}]), type('Usage', (), {'input_tokens': 100, 'output_tokens': 100})()
            count = len(p['candidates'])
            assert [c["index"] for c in p["candidates"]] == list(range(count))
            output = schema(verdicts=[{"index": 0 if duplicate_review else i, "supported": True, "reason": "Exact cell/date/entity/scope/scale binding matched"} for i in range(count)])
        elif schema.__name__ == "HypothesisBatch":
            output = schema(candidates=[{"statement": "Advances outpaced deposits", "mechanism": "Balance expansion may change the funding mix", "fact_ids": [f["id"] for f in p["facts"]], "calculation_ids": [c["id"] for c in p["calculations"]], "next_query": "HDFC Bank funding mix disclosures", "opposing_query": "HDFC Bank reclassification acquisition funding growth alternative", "falsification": "A comparable reversal of the growth gap", "significance": 4, "novelty": 3}], missing_evidence=[])
        elif schema.__name__ == 'CurrentReconciliation':
            output = schema(status='not_found', passage_ids=[], reason='No directly relevant reconciliation was found in the checked passages.')
        elif schema.__name__ == 'PlainHeadline':
            output = schema(sentence='HDFC Bank recorded a 10 percentage point difference between advances and deposit growth from 2025 to 2026.')
        elif schema.__name__ == "Challenge":
            output = schema(refuted=refuted, unresolved=True, strongest_alternative="Growth alone does not establish funding stress", reason="Composition and cost remain untested", relevant_passage_ids=[v["id"] for v in p["passages"]], novelty_status="additional_supported_synthesis", novelty_rationale="The linked cross-metric comparison qualifies the sector explanation.", published_explanation="Sector review does not quantify the issuer growth gap.")
        elif schema.__name__ == "DiscoveryDraft":
            ids = [f["id"] for f in p["facts"]]
            context_ids = [v["id"] for v in p["passages"] if "Independent banking" in v["text"]]
            gap = next(c["id"] for c in p["calculations"] if c["formula_id"] == "growth_gap")
            def statement(text, kind="derived", contextual=False):
                return {"text": text, "kind": kind, "fact_ids": ids, "passage_ids": context_ids if contextual else [], "calculation_ids": [] if contextual else [gap]}
            headline = statement("HDFC Bank advances grew faster than deposits on comparable consolidated year-end balances; funding stress is not established.")
            headline["passage_ids"] = context_ids
            output = schema(headline=headline, why_it_matters=[statement("Advances grew 20%, while deposits grew 10%."), statement("The reproducible growth gap is 10 percentage points."), statement("Independent context requires funding-composition evidence before inferring stress.", "inferred", True)], counterargument=statement("Expansion can create a growth gap without funding stress.", "inferred", True), timeline_analysis=statement("The relationship is observed between March 2025 and March 2026; these two snapshots do not establish its onset."), onset_status="unknown", falsification="Reconsider if later comparable disclosures reverse the advances/deposit growth gap.", falsification_window="Next two comparable quarterly disclosures", falsification_source="Dated issuer financial results")
        elif schema.__name__ == "SemanticReview":
            output = schema(verdicts=[{"claim_id": c["id"], "supported": not reject_claim, "reason": "All linked source spans, inputs and qualifications reviewed"} for c in p["claims"]], falsification_is_observable=True, contains_investment_recommendation=False, non_obvious_synthesis_supported=True)
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
    assert len(report.discoveries[0].discovery_sentence.split()) <= 35
    assert report.generation_metadata['headline']['technical_detail']
    assert report.generation_metadata['strength_trace']['rules']['peer_comparison_verified'] is False
    conditions = report.generation_metadata['falsification_tests']['conditions']
    assert any(c['kind'] == 'next_quarter' and c['threshold'] == '0' for c in conditions)
    assert next(c for c in conditions if c['checkable_now'])['status'] == 'not_found'
    # Three historical windows, original regulator and peer searches, plus the
    # candidate-specific supporting/opposing pair. Duplicate URLs are not fetched.
    assert 12 <= calls['search'] <= settings.max_search_calls and calls['fetch'] == 2
    assert len(report.generation_metadata['submission_checklist']['items']) == 8
    # A qualified observation can publish Weak without pretending its onset is known.
    assert not report.generation_metadata['submission_checklist']['discovery_ready']
    assert report.generation_metadata['submission_checklist']['items'][3]['status'] == 'limited'
    assert summary.progress['counterevidence_checks'] == 1
    assert summary.budget["model_calls"] == calls["model"]


@pytest.mark.parametrize('primary_only', [False, True])
def test_full_pipeline_peer_comparison_retains_two_other_issuers_and_reproduces_the_median(store, tmp_path, monkeypatch, primary_only):
    from signal_research.research.peer_selector import select_peers
    settings, run_id, _ = live_fixture(store, tmp_path, monkeypatch)
    settings.max_output_tokens = 120000  # Allow concurrent reservations, not just sequential actual receipts.
    target = store.get_summary(run_id).company
    peers = select_peers(target, store.search_companies(''), target.business_profiles[0]).peers
    search, fetch = TavilySearchProvider.search, PublicFetcher.fetch
    pages = {}
    for peer in peers:
        url = f'https://{peer.verified_ir_domains[0]}/peer-fixture.html'
        pages[url] = (peer, ('<html><head><meta property="article:published_time" content="2026-05-15"></head><body><pre>'
            + peer.legal_name + '\nConsolidated Statement of Assets and Liabilities\nINR crore\n'
            'As at 31 March 2026 | 31 March 2025\nDeposits 133750 125000\nBorrowings 15000 14000\n</pre></body></html>'))
    def peer_search(self, query, domains, as_of, max_results):
        for url, (company, _) in pages.items():
            if query.startswith(f'"{company.legal_name}" ') and 'financial results' in query:
                return [SearchHit(url, company.legal_name + ' Results', '', 1, 'test', date(2026, 5, 15))]
        hits = search(self, query, domains, as_of, max_results)
        return [h for h in hits if not primary_only or 'independent.example' not in h.url]
    def peer_fetch(self, url):
        if url not in pages:
            return fetch(self, url)
        raw = pages[url][1].encode()
        digest = hashlib.sha256(raw).hexdigest()
        path = tmp_path / (digest + '.html')
        path.write_bytes(raw)
        return FetchResult(url, url, 200, 'text/html', digest, str(path))
    monkeypatch.setattr(TavilySearchProvider, 'search', peer_search)
    monkeypatch.setattr(PublicFetcher, 'fetch', peer_fetch)
    if primary_only:
        from uuid import UUID

        from signal_research.domain.enums import ClaimKind
        generate = OpenAIProvider.generate
        def observed_draft(self, schema, messages, model_role, deadline, max_output_tokens):
            output, usage = generate(self, schema, messages, model_role, deadline, max_output_tokens)
            if schema.__name__ == 'Challenge':
                output.unresolved = False
                output.reason = 'Verified peer arithmetic addresses the sector comparison for this non-causal observation.'
            if schema.__name__ == 'DiscoveryDraft':
                p = json.loads(messages[1]['content'])
                calc = next(c for c in p['calculations'] if c['formula_id'] == 'yoy_growth' and c['input_bindings'][0]['metric'] == 'deposits')
                output.why_it_matters[2] = output.why_it_matters[0].model_copy(update={
                    'text': 'Deposits grew 10% on the same consolidated reporting basis.', 'kind': ClaimKind.DERIVED,
                    'passage_ids': [], 'calculation_ids': [UUID(calc['id'])]})
            return output, usage
        monkeypatch.setattr(OpenAIProvider, 'generate', observed_draft)
    ResearchMachine(store, settings).process(run_id)
    report = verify_report(store.get_report(run_id))
    benchmark = report.generation_metadata['peer_benchmark']
    assert benchmark['status'] == 'verified', benchmark
    row = next(r for r in benchmark['comparisons'] if r['metric'] == 'deposits')
    assert len(row['peers']) >= 2 and Decimal(row['peer_median']) == 7
    assert row['classification'] == 'sector-wide'
    assert report.generation_metadata['strength_trace']['rules']['peer_comparison_verified']
    assert all(f.entity_id == target.id for f in report.facts)
    if primary_only:
        assert len(report.generation_metadata['strength_trace']['origin_families']) == 1
        assert report.discoveries[0].evidence_strength.value == 'Moderate'


def test_provider_timeout_before_first_verified_fact_still_saves_not_established_candidate(store, tmp_path, monkeypatch):
    from signal_research.providers.llm.codecraft_provider import CodeCraftTimeout
    settings, rid, _ = live_fixture(store, tmp_path, monkeypatch)
    def unavailable(*args, **kwargs):
        raise CodeCraftTimeout('Provider request did not complete; uncertain request will not be replayed.')
    monkeypatch.setattr(OpenAIProvider, 'generate', unavailable)
    ResearchMachine(store, settings).process(rid)
    report = verify_report(store.get_report(rid))
    assert report.outcome.value == 'partial' and not report.facts and not report.discoveries
    assert report.generation_metadata['best_candidate']['label'] == 'Not established'
    assert report.generation_metadata['best_candidate']['missing']


def test_source_only_prose_cannot_replace_the_required_verified_fact_anchor(store, tmp_path, monkeypatch):
    settings, rid, _ = live_fixture(store, tmp_path, monkeypatch)
    generate = OpenAIProvider.generate
    def source_only(self, schema, messages, model_role, deadline, max_output_tokens):
        output, usage = generate(self, schema, messages, model_role, deadline, max_output_tokens)
        if schema.__name__ == 'DiscoveryDraft':
            output.why_it_matters[0].fact_ids = []
            output.why_it_matters[0].calculation_ids = []
            output.why_it_matters[0].passage_ids = output.why_it_matters[2].passage_ids
        return output, usage
    monkeypatch.setattr(OpenAIProvider, 'generate', source_only)
    ResearchMachine(store, settings).process(rid)
    report = verify_report(store.get_report(rid))
    assert not report.discoveries
    assert any('fact or calculation anchor' in limitation for limitation in report.limitations)


def test_primary_origin_arithmetic_can_publish_only_a_non_causal_weak_observation(store, tmp_path, monkeypatch):
    from uuid import UUID

    from signal_research.domain.enums import ClaimKind
    settings, rid, _ = live_fixture(store, tmp_path, monkeypatch)
    original_search, original_generate = TavilySearchProvider.search, OpenAIProvider.generate
    def primary_only(self, query, domains, as_of, max_results):
        return [hit for hit in original_search(self, query, domains, as_of, max_results) if 'independent.example' not in hit.url]
    def observed_draft(self, schema, messages, model_role, deadline, max_output_tokens):
        output, usage = original_generate(self, schema, messages, model_role, deadline, max_output_tokens)
        if schema.__name__ == 'DiscoveryDraft':
            p = json.loads(messages[1]['content'])
            calc = next(c for c in p['calculations'] if c['formula_id'] == 'yoy_growth' and c['input_bindings'][0]['metric'] == 'deposits')
            output.why_it_matters[2] = output.why_it_matters[0].model_copy(update={
                'text': 'Deposits grew 10% on the same consolidated reporting basis.', 'kind': ClaimKind.DERIVED,
                'passage_ids': [], 'calculation_ids': [UUID(calc['id'])]})
        return output, usage
    monkeypatch.setattr(TavilySearchProvider, 'search', primary_only)
    monkeypatch.setattr(OpenAIProvider, 'generate', observed_draft)
    ResearchMachine(store, settings).process(rid)
    report = verify_report(store.get_report(rid))
    assert report.discoveries and report.discoveries[0].evidence_strength.value == 'Weak'
    assert report.generation_metadata['tiered_publication']
    assert len(report.generation_metadata['strength_trace']['origin_families']) == 1


def test_live_credit_failover_uses_nvidia_and_reports_actual_models(store, tmp_path, monkeypatch):
    import httpx
    from signal_research.providers.llm.nvidia_provider import NvidiaProvider

    settings, run_id, _ = live_fixture(store, tmp_path, monkeypatch)
    settings.llm_provider = 'codecraft'
    settings.codecraft_api_key = 'primary-test'
    settings.codecraft_secondary_api_keys = ['backup-one-test', 'backup-two-test']
    settings.codecraft_model_extract = 'cc-extract'
    settings.codecraft_model_research = 'cc-research'
    settings.codecraft_nvidia_fallback = True
    settings.nvidia_api_key = 'nvidia-test'
    settings.nvidia_model_extract = 'nv-extract'
    settings.nvidia_model_research = 'nv-research'
    rejected = []
    async def reject(self, url, **kwargs):
        rejected.append(kwargs['headers']['Authorization'])
        return httpx.Response(402)
    monkeypatch.setattr(httpx.AsyncClient, 'post', reject)
    monkeypatch.setattr(NvidiaProvider, 'generate', OpenAIProvider.generate)
    ResearchMachine(store, settings).process(run_id)
    report = store.get_report(run_id)
    assert report and report.outcome.value == 'discovery'
    assert len(rejected) == 3
    assert report.generation_metadata['configured_provider'] == 'codecraft'
    assert report.generation_metadata['provider'] == 'nvidia'
    assert {m['model_id'] for m in report.generation_metadata['models_used']} == {'nv-extract', 'nv-research'}
    assert report.generation_metadata['model_id'] is None
    exhausted = [a for a in store.artifacts(run_id) if a['kind'].startswith('exhausted:')]
    assert len(exhausted) == 3
    assert all(len(a['kind']) > 50 for a in exhausted)
    assert {a['payload']['slot'] for a in exhausted} == {'codecraft:0', 'codecraft:1', 'codecraft:2'}


def test_duplicate_semantic_verdicts_cannot_publish(store, tmp_path, monkeypatch):
    settings, run_id, calls = live_fixture(store, tmp_path, monkeypatch)
    original = OpenAIProvider.generate

    def duplicate(self, schema, *args, **kwargs):
        output, usage = original(self, schema, *args, **kwargs)
        if schema.__name__ == "SemanticReview":
            output.verdicts.append(output.verdicts[0])
        return output, usage

    monkeypatch.setattr(OpenAIProvider, "generate", duplicate)
    ResearchMachine(store, settings).process(run_id)
    report = store.get_report(run_id)
    assert report.outcome.value == "insufficient_evidence"
    assert any("semantic review rejected" in limitation for limitation in report.limitations)


def test_invalid_top_ranked_candidates_do_not_hide_a_valid_lower_ranked_candidate(store, tmp_path, monkeypatch):
    settings, run_id, _ = live_fixture(store, tmp_path, monkeypatch)
    generated = OpenAIProvider.generate
    def three_candidates(self, schema, *args, **kwargs):
        result, usage = generated(self, schema, *args, **kwargs)
        if schema.__name__ == 'HypothesisBatch':
            valid = result.candidates[0].model_copy(update={'significance': 2, 'novelty': 2})
            invalid = valid.model_copy(update={'statement': 'An unsupported 99% funding shift', 'significance': 5, 'novelty': 5})
            result.candidates = [invalid, invalid.model_copy(update={'statement': 'An unsupported 98% margin shift'}), valid]
        return result, usage
    monkeypatch.setattr(OpenAIProvider, 'generate', three_candidates)
    ResearchMachine(store, settings).process(run_id)
    report = verify_report(store.get_report(run_id))
    assert report.discoveries
    decisions = report.generation_metadata['research_decisions']
    assert len([d for d in decisions if d['disposition'] == 'withheld']) == 2
    assert len([d for d in decisions if d['published']]) == 1
    assert len(report.generation_metadata['challenge_reviews']) == 1


def test_refuted_candidate_retains_actual_challenge_and_test_without_becoming_a_discovery(store, tmp_path, monkeypatch):
    settings, run_id, _ = live_fixture(store, tmp_path, monkeypatch, refuted=True)
    ResearchMachine(store, settings).process(run_id)
    report = verify_report(store.get_report(run_id))
    assert not report.discoveries
    review = report.generation_metadata['challenge_reviews'][0]
    assert review['refuted'] and review['strongest_alternative']
    assert review['proposed_falsification'] and review['relevant_passage_ids']
    assert report.generation_metadata['opposing_queries']
    assert report.timeline_events and report.calculations
    assert store.get_summary(run_id).progress['counterevidence_checks'] == 1
    assert not report.generation_metadata['submission_checklist']['discovery_ready']


def test_optional_extraction_timeout_preserves_facts_for_distinct_research_requests(store, tmp_path, monkeypatch):
    from signal_research.providers.llm.codecraft_provider import CodeCraftTimeout
    from signal_research.research.live import LiveResearch, fact_review_schema

    settings, run_id, _ = live_fixture(store, tmp_path, monkeypatch)
    generated = OpenAIProvider.generate
    failures = []
    def optional_timeout(self, schema, messages, *args, **kwargs):
        if json.loads(messages[1]['content']).get('optional_timeout'):
            failures.append(1)
            raise CodeCraftTimeout('Uncertain test request; not retried')
        return generated(self, schema, messages, *args, **kwargs)
    def historical_timeout(self):
        self.extraction_model(self.passages[0], fact_review_schema(1), {'optional_timeout': True},
                              'extract', 'normalizing', 'Check the optional earlier statement')
    monkeypatch.setattr(OpenAIProvider, 'generate', optional_timeout)
    monkeypatch.setattr(LiveResearch, 'collect_history', historical_timeout)
    ResearchMachine(store, settings).process(run_id)
    report = verify_report(store.get_report(run_id))
    assert failures == [1]
    assert report.discoveries and report.facts
    assert len(report.generation_metadata['challenge_reviews']) == 1
    assert store.artifacts(run_id, 'extraction_failure')[0]['payload']['action'].startswith('optional extraction paused')


@pytest.mark.parametrize('stage', ['Challenge', 'SemanticReview'])
def test_plain_summary_cannot_publish_as_a_novel_discovery(store, tmp_path, monkeypatch, stage):
    settings, run_id, _ = live_fixture(store, tmp_path, monkeypatch)
    original = OpenAIProvider.generate
    def summary_only(self, schema, *args, **kwargs):
        output, usage = original(self, schema, *args, **kwargs)
        if schema.__name__ == stage:
            if stage == 'Challenge':
                output.novelty_status = 'simple_restatement'
                output.novelty_rationale = 'This is an ordinary issuer growth summary.'
            else:
                output.non_obvious_synthesis_supported = False
        return output, usage
    monkeypatch.setattr(OpenAIProvider, 'generate', summary_only)
    ResearchMachine(store, settings).process(run_id)
    report = store.get_report(run_id)
    assert not report.discoveries and report.facts and report.calculations
    decisions = report.generation_metadata['research_decisions']
    assert decisions and not any(d['published'] for d in decisions)


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


def test_reconciled_candidate_cannot_be_challenged_with_withdrawn_arithmetic(store, tmp_path, monkeypatch):
    from signal_research.research.live import LiveResearch, derive_calculations

    settings, run_id, _ = live_fixture(store, tmp_path, monkeypatch)
    extract, generated = LiveResearch.extract, OpenAIProvider.generate
    extraction_count = 0
    def reconcile(self, *args, **kwargs):
        nonlocal extraction_count
        extract(self, *args, **kwargs)
        extraction_count += 1
        if self.store.artifacts(self.run_id, 'hypotheses'):  # Targeted follow-up after candidates were bound.
            self.facts = self.facts[1:]
            self.calculations = derive_calculations(self.facts)
    def no_stale_review(self, schema, *args, **kwargs):
        assert schema.__name__ not in {'Challenge', 'DiscoveryDraft', 'SemanticReview'}
        return generated(self, schema, *args, **kwargs)
    monkeypatch.setattr(LiveResearch, 'extract', reconcile)
    monkeypatch.setattr(OpenAIProvider, 'generate', no_stale_review)
    ResearchMachine(store, settings).process(run_id)
    report = verify_report(store.get_report(run_id))
    assert report.facts and not report.discoveries
    decisions = report.generation_metadata['research_decisions']
    assert decisions[0]['disposition'] == 'withheld'
    assert 'withdrawn during source reconciliation' in decisions[0]['reason']


def test_history_withdrawing_all_arithmetic_stops_before_hypothesis_generation(store, tmp_path, monkeypatch):
    from signal_research.research.live import LiveResearch

    settings, run_id, _ = live_fixture(store, tmp_path, monkeypatch)
    def invalidate(self):
        self.facts, self.calculations = [], []
    monkeypatch.setattr(LiveResearch, 'collect_history', invalidate)
    generated = OpenAIProvider.generate
    def no_hypotheses(self, schema, *args, **kwargs):
        assert schema.__name__ != 'HypothesisBatch'
        return generated(self, schema, *args, **kwargs)
    monkeypatch.setattr(OpenAIProvider, 'generate', no_hypotheses)
    ResearchMachine(store, settings).process(run_id)
    report = store.get_report(run_id)
    assert report.outcome.value == 'insufficient_evidence' and not report.calculations
    assert 'historical-source reconciliation' in report.abstention.missing_requirements[0]


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
    original_search = TavilySearchProvider.search
    queries = []
    def search(self, query, domains, cutoff, max_results):
        queries.append(query)
        return original_search(self, query, domains, cutoff, max_results)
    monkeypatch.setattr(TavilySearchProvider, 'search', search)
    ResearchMachine(store, settings).process(run_id)
    report = store.get_report(run_id)
    assert report.outcome.value == "insufficient_evidence"
    assert "period, unit and scope" in report.abstention.missing_requirements[0]
    assert "Extraction gap: Complete dates and financial scope could not be verified." in report.limitations
    artifact = store.artifacts(run_id, "fact_extraction")[0]["payload"]
    assert artifact["missing_metrics"] == ["gross_advances"]
    assert artifact["notes"]
    assert any('"annual report"' in query for query in queries)
    assert not any('"standalone" "consolidated"' in query for query in queries)


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
    assert annual_queries[0][1] == store.search_companies("HDFCBANK")[0].verified_ir_domains
    assert any("2025 2026" in query for query, _ in annual_queries)
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
@pytest.mark.parametrize("parallel_budget", [False, True])
def test_limit_during_challenge_saves_verified_partial_report(store, tmp_path, monkeypatch, limit, parallel_budget):
    from datetime import UTC, datetime, timedelta
    from threading import Event

    from signal_research.research.live import LiveResearch

    settings, run_id, calls = live_fixture(store, tmp_path, monkeypatch)
    if parallel_budget:
        settings.max_output_tokens = 100000
    original = LiveResearch.challenge
    original_reconciliation = LiveResearch.check_current_reconciliation
    reconciliation_completed = Event()
    stopped_at = []
    def finish_reconciliation(self, hypothesis):
        result = original_reconciliation(self, hypothesis)
        reconciliation_completed.set()
        return result
    def reach_limit(self, hypothesis):
        # Reconciliation and challenge now run concurrently. Deliberately stop
        # after the former completes, rather than asserting a scheduler order.
        assert reconciliation_completed.wait(10), 'Independent reconciliation did not finish'
        stopped_at.append(calls['model'])
        if limit == "deadline":
            self.budget.deadline = datetime.now(UTC) - timedelta(seconds=1)
        else:
            self.budget.max_model_calls = self.budget.model_calls
        return original(self, hypothesis)
    monkeypatch.setattr(LiveResearch, "check_current_reconciliation", finish_reconciliation)
    monkeypatch.setattr(LiveResearch, "challenge", reach_limit)
    ResearchMachine(store, settings).process(run_id)
    summary = store.get_summary(run_id)
    assert summary.status.value == "completed", summary.limitations
    report = verify_report(store.get_report(run_id))
    assert report.outcome.value == "partial"
    assert len(report.facts) == 4 and report.calculations
    assert not report.discoveries and report.publication_status.value == "abstained"
    assert report.generation_metadata["stopped_by_limit"]
    assert stopped_at == [4]  # Extraction, fact review, hypothesis and current reconciliation review.
    assert calls['model'] == stopped_at[0]  # No provider call starts after the limit is reached.
    before = calls.copy()
    ResearchMachine(store, settings).process(run_id)
    assert calls == before


def test_current_reconciliation_and_adversarial_review_overlap_without_skipping_publication_gates(store, tmp_path, monkeypatch):
    from threading import Barrier, Lock

    settings, run_id, _ = live_fixture(store, tmp_path, monkeypatch)
    settings.max_output_tokens = 100000  # Both full response allowances must fit concurrently.
    original = OpenAIProvider.generate
    reviewers_started = Barrier(2)
    recorded = Lock()
    completed = []
    def synchronized_review(self, schema, messages, model_role, deadline, max_output_tokens):
        if schema.__name__ in {'CurrentReconciliation', 'Challenge'}:
            # A sequential implementation cannot get both independent checks
            # through this barrier. Provider mocks never make a paid request.
            reviewers_started.wait(timeout=10)
            with recorded:
                completed.append(schema.__name__)
        return original(self, schema, messages, model_role, deadline, max_output_tokens)
    monkeypatch.setattr(OpenAIProvider, 'generate', synchronized_review)
    ResearchMachine(store, settings).process(run_id)
    report = verify_report(store.get_report(run_id))
    assert sorted(completed) == ['Challenge', 'CurrentReconciliation']
    assert report.outcome.value == 'discovery' and report.discoveries
    assert len(report.facts) == 4 and report.calculations
    checks = report.generation_metadata['falsification_tests']['conditions']
    current = next(condition for condition in checks if condition['kind'] == 'current_reconciliation')
    assert current['checkable_now'] and current['status'] == 'not_found'
    assert report.generation_metadata['challenge_reviews']


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

@pytest.mark.parametrize('kind', ['input_tokens', 'output_tokens', 'model_calls'])
def test_exploration_preserves_final_review_allowance(store, tmp_path, monkeypatch, kind):
    from pydantic import BaseModel
    from signal_research.domain.errors import BudgetExceeded
    from signal_research.providers.llm.base import ProviderUsage
    from signal_research.providers.llm.openai_provider import OpenAIProvider
    from signal_research.worker.budgets import Budget
    from signal_research.worker.calls import DurableCalls

    class Result(BaseModel):
        supported: bool

    settings, run_id, _ = live_fixture(store, tmp_path, monkeypatch)
    settings.max_model_output_tokens_per_call = 256
    budget = Budget(10, 10, 10, 0, max_input_tokens=60000, max_output_tokens=10000)
    setattr(budget, kind, {'input_tokens': 48000, 'output_tokens': 8000, 'model_calls': 8}[kind])
    requested = []
    def generate(self, schema, messages, role, deadline, max_output_tokens):
        requested.append(max_output_tokens)
        return schema(supported=True), ProviderUsage(input_tokens=100, output_tokens=20)
    monkeypatch.setattr(OpenAIProvider, 'generate', generate)
    calls = DurableCalls(store, settings, run_id, budget)
    with pytest.raises(BudgetExceeded):
        calls.model(Result, {'evidence': 'bounded'}, stage='extracting')
    assert requested == []
    assert calls.model(Result, {'evidence': 'bounded'}, stage='verifying').supported
    assert requested == [256]


def test_nvidia_failure_after_fact_review_preserves_evidence_without_discovery(store, tmp_path, monkeypatch):
    from signal_research.providers.llm.nvidia_provider import NvidiaTimeout
    from signal_research.research.live import LiveResearch
    settings, run_id, _ = live_fixture(store, tmp_path, monkeypatch)
    def unavailable(self, hypothesis):
        raise NvidiaTimeout('Controlled provider timeout; no real NVIDIA call was made')
    monkeypatch.setattr(LiveResearch, 'challenge', unavailable)
    ResearchMachine(store, settings).process(run_id)
    report = store.get_report(run_id)
    assert report.outcome.value == 'partial'
    assert report.facts and report.calculations and not report.discoveries
    assert report.generation_metadata['provider_failure'] == 'NVIDIA_RESPONSE_TIMEOUT'


def test_empty_search_and_inaccessible_sources_abstain_without_model_or_dummy_data(store, tmp_path, monkeypatch):
    settings, run_id, calls = live_fixture(store, tmp_path, monkeypatch)
    monkeypatch.setattr(TavilySearchProvider, 'search', lambda *args, **kwargs: [])
    monkeypatch.setattr(PublicFetcher, 'fetch', lambda self, url: FetchResult(url, url, 403, 'text/html', None, None, error='Controlled inaccessible source; no real HTTP request'))
    ResearchMachine(store, settings).process(run_id)
    report = store.get_report(run_id)
    assert store.get_summary(run_id).status.value == 'completed'
    assert report.outcome.value == 'insufficient_evidence'
    assert report.abstention and not report.facts and not report.discoveries
    assert calls['model'] == 0
    assert any('Controlled inaccessible source' in item for item in report.limitations)


@pytest.mark.parametrize('reject_claim', [False, True])
def test_fast_verified_proposals_skip_model_planning_but_keep_final_review(store, tmp_path, monkeypatch, reject_claim):
    settings, run_id, _ = live_fixture(store, tmp_path, monkeypatch, reject_claim=reject_claim)
    settings.fast_verified_proposals = True
    generate = OpenAIProvider.generate
    reviewed = []
    def without_planning(self, schema, *args, **kwargs):
        assert schema.__name__ != 'HypothesisBatch', 'Registered relationships need no extra planning model call'
        if schema.__name__ == 'SemanticReview':
            reviewed.append(True)
        return generate(self, schema, *args, **kwargs)
    monkeypatch.setattr(OpenAIProvider, 'generate', without_planning)
    ResearchMachine(store, settings).process(run_id)
    report = verify_report(store.get_report(run_id))
    assert reviewed
    assert bool(report.discoveries) is not reject_claim
    assert store.artifacts(run_id, 'verified_arithmetic_proposals')[0]['payload']['publication_review_required']


def test_angle_planning_starts_before_slow_peer_collection_finishes(store, tmp_path, monkeypatch):
    from threading import Event

    from signal_research.research.live import LiveResearch
    settings, run_id, _ = live_fixture(store, tmp_path, monkeypatch)
    peer_started, planning_started, overlapped = Event(), Event(), Event()
    peers, planning = LiveResearch.collect_peer_benchmark, LiveResearch.angle_hypotheses
    def slow_peers(self, hypothesis):
        if not self.peer_collection_attempted:
            peer_started.set()
            assert planning_started.wait(timeout=5), 'Planner must not wait for this peer'
            overlapped.set()
        return peers(self, hypothesis)
    def plan(self, payload):
        assert peer_started.wait(timeout=5)
        planning_started.set()
        return planning(self, payload)
    monkeypatch.setattr(LiveResearch, 'collect_peer_benchmark', slow_peers)
    monkeypatch.setattr(LiveResearch, 'angle_hypotheses', plan)
    ResearchMachine(store, settings).process(run_id)
    assert overlapped.is_set()
    assert verify_report(store.get_report(run_id)).discoveries


def test_composition_timeout_preserves_the_actual_candidate_without_publishing_it(store, tmp_path, monkeypatch):
    from signal_research.providers.llm.codecraft_provider import CodeCraftTimeout
    settings, run_id, _ = live_fixture(store, tmp_path, monkeypatch)
    generate = OpenAIProvider.generate
    def timeout_draft(self, schema, *args, **kwargs):
        if schema.__name__ == 'DiscoveryDraft':
            raise CodeCraftTimeout('Controlled timeout after challenge, without a real API request')
        return generate(self, schema, *args, **kwargs)
    monkeypatch.setattr(OpenAIProvider, 'generate', timeout_draft)
    ResearchMachine(store, settings).process(run_id)
    report = verify_report(store.get_report(run_id))
    assert report.outcome.value == 'partial'
    assert not report.discoveries
    candidate = report.generation_metadata['best_candidate']
    assert candidate['text'] == 'Advances outpaced deposits'
    assert candidate['label'] == 'Not established'
    assert 'must finish before publication' in candidate['reason']
    assert any('timed out' in reason for reason in candidate['missing'])


def test_malformed_pdf_is_reported_without_silent_synthetic_substitution(store, tmp_path, monkeypatch):
    settings, run_id, calls = live_fixture(store, tmp_path, monkeypatch)
    settings.max_fetch_documents = 1
    path = tmp_path / 'malformed.pdf'
    path.write_bytes(b'%PDF-1.7\ninvalid body, no trailer or objects')
    monkeypatch.setattr(PublicFetcher, 'fetch', lambda self, url: FetchResult(url, url, 200, 'application/pdf', hashlib.sha256(path.read_bytes()).hexdigest(), str(path)))
    ResearchMachine(store, settings).process(run_id)
    report = store.get_report(run_id)
    assert report and report.outcome.value == 'insufficient_evidence'
    assert not report.facts and not report.discoveries and calls['model'] == 0
    assert any('Source parse failed' in item for item in report.limitations)


def test_expired_run_recovers_last_complete_evidence_without_provider_calls(store, tmp_path, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from signal_research.db.models import ResearchRunModel
    from signal_research.research.live import LiveResearch
    settings, run_id, calls = live_fixture(store, tmp_path, monkeypatch)
    original = LiveResearch.extract
    def interrupted(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError('Controlled power interruption after reviewed extraction')
    monkeypatch.setattr(LiveResearch, 'extract', interrupted)
    ResearchMachine(store, settings).process(run_id)
    assert store.get_summary(run_id).status.value == 'failed'
    checkpoint = store.load_checkpoint(run_id, 'evidence_collected', iteration=None)
    assert checkpoint['facts'] and checkpoint['calculations'] and not checkpoint['discoveries']
    with store.session_factory() as session:
        row = session.get(ResearchRunModel, str(run_id))
        row.budget_json = row.budget_json | {'deadline': (datetime.now(UTC) - timedelta(seconds=1)).isoformat()}
        session.commit()
    before = calls.copy()
    store.resume(run_id); store.lease_next('evidence-recovery')
    ResearchMachine(store, settings).process(run_id)
    report = store.get_report(run_id)
    assert report and report.outcome.value == 'partial' and report.facts and not report.discoveries
    assert calls == before


def test_latest_empty_evidence_checkpoint_does_not_resurrect_withheld_figures(store):
    from signal_research.domain.enums import RunMode
    company = store.search_companies('SYNTHBANK')[0]
    run_id = store.create_run(company, date(2026, 10, 8), RunMode.REPLAY)
    store.lease_next('checkpoint-order')
    store.checkpoint(run_id, 'evidence_collected', 0, {'facts': ['old']})
    store.checkpoint(run_id, 'evidence_collected', 1, {'facts': []})
    assert store.load_checkpoint(run_id, 'evidence_collected', iteration=None) == {'facts': []}
    assert store.load_checkpoint(run_id, 'evidence_collected') == {'facts': ['old']}


@pytest.mark.parametrize('corrected', [True, False])
def test_local_numerical_failure_gets_one_repair_then_fresh_review(store, tmp_path, monkeypatch, corrected):
    settings, rid, _ = live_fixture(store, tmp_path, monkeypatch)
    original = OpenAIProvider.generate
    seen = {'drafts': 0, 'semantic_reviews': 0}
    def generated(self, schema, messages, *args, **kwargs):
        output, usage = original(self, schema, messages, *args, **kwargs)
        if schema.__name__ == 'DiscoveryDraft':
            seen['drafts'] += 1
            if seen['drafts'] == 1 or not corrected:
                output.why_it_matters[0].text += ' Commentary adds an unverified 999%.'
        if schema.__name__ == 'SemanticReview':
            seen['semantic_reviews'] += 1
        return output, usage
    monkeypatch.setattr(OpenAIProvider, 'generate', generated)
    ResearchMachine(store, settings).process(rid)
    report = verify_report(store.get_report(rid))
    assert seen['drafts'] == 2
    assert seen['semantic_reviews'] == int(corrected)
    assert (report.outcome.value == 'discovery') is corrected
    assert all('999%' not in claim.text for claim in report.claims)
    if not corrected:
        assert not report.discoveries


@pytest.mark.parametrize('corrected', [True, False])
def test_hypothesis_numeric_repair_is_bounded_and_never_bypasses_publication_gates(store, tmp_path, monkeypatch, corrected):
    settings, rid, _ = live_fixture(store, tmp_path, monkeypatch)
    original = OpenAIProvider.generate
    seen = {'hypotheses': 0, 'challenge': 0}
    def generated(self, schema, messages, *args):
        output, usage = original(self, schema, messages, *args)
        if schema.__name__ == 'HypothesisBatch':
            seen['hypotheses'] += 1
            if seen['hypotheses'] == 1 or not corrected:
                output.candidates[0].mechanism += ' An unsupported additional 999% change.'
            else:
                assert 'numerical_repair' in json.loads(messages[1]['content'])
        if schema.__name__ == 'ChallengeReview':
            seen['challenge'] += 1
        return output, usage
    monkeypatch.setattr(OpenAIProvider, 'generate', generated)
    ResearchMachine(store, settings).process(rid)
    report = verify_report(store.get_report(rid))
    assert seen['hypotheses'] == 2
    assert len(store.artifacts(rid, 'hypothesis_numeric_repair')) == 1
    assert (report.outcome.value == 'discovery') is corrected
    assert all('999%' not in claim.text for claim in report.claims)
    if not corrected:
        assert not report.discoveries and not seen['challenge']


def test_late_hypothesis_repair_preserves_final_review_window(store, tmp_path, monkeypatch):
    from signal_research.worker.budgets import Budget
    settings, rid, _ = live_fixture(store, tmp_path, monkeypatch)
    original = OpenAIProvider.generate
    count = []
    def generated(self, schema, messages, *args):
        output, usage = original(self, schema, messages, *args)
        if schema.__name__ == 'HypothesisBatch':
            count.append(1)
            output.candidates[0].mechanism += ' Unverified 999%.'
            # It exceeds the old >30s condition but cannot afford a repair and
            # the downstream review stages. Existing numerical gates must hold.
            monkeypatch.setattr(Budget, 'remaining_seconds', lambda self: 80)
        return output, usage
    monkeypatch.setattr(OpenAIProvider, 'generate', generated)
    ResearchMachine(store, settings).process(rid)
    report = store.get_report(rid)
    assert len(count) == 1 and not store.artifacts(rid, 'hypothesis_numeric_repair')
    assert report and not report.discoveries
