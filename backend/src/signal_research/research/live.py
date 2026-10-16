from __future__ import annotations

import re
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import unquote, urlparse
from uuid import UUID, uuid4, uuid5

from pydantic import Field, create_model

from signal_research.domain.enums import (
    ClaimKind,
    DatePrecision,
    EvidenceRelation,
    EvidenceStrength,
    PublicationStatus,
    ResearchOutcome,
    VerificationStatus,
)
from signal_research.domain.schemas import (
    Calculation,
    Claim,
    Counterargument,
    Discovery,
    EvidenceLink,
    FalsificationRule,
    Passage,
    ResearchReport,
    SourceDocument,
    StrictModel,
    TimelineEvent,
    WhyItMatters,
)
from signal_research.evidence.duplicates import near_duplicate
from signal_research.evidence.tiers import evidence_tier
from signal_research.extraction.bank_tables import (
    comparative_bank_batch,
    month_end_columns,
    scope_in_text,
    subsidiary_only,
)
from signal_research.extraction.column_tables import column_metric_lead
from signal_research.extraction.dates import (
    abbreviated_quarter_periods,
    declared_duration_periods,
    explicit_duration_ranges,
    source_dates,
)
from signal_research.extraction.eligibility import minimum_source_bindings
from signal_research.extraction.financial_tables import (
    financial_table_batch,
    quarter_presentation_batch,
)
from signal_research.extraction.models import ExtractedFactBatch, source_fact_batch_schema
from signal_research.extraction.stock_ratios import stock_ratio_batch
from signal_research.extraction.validate import validate_candidate
from signal_research.finance.calculations import calculate, numeric_fact
from signal_research.finance.registry import metrics_for_profile
from signal_research.research.angles import ANGLES, route_angles
from signal_research.research.brief import (
    compatible_candidate,
    observation_timeline,
    research_lanes,
    submission_checklist,
)
from signal_research.research.calculation_context import calculation_context
from signal_research.research.claim_numbers import supported_numbers
from signal_research.research.context import diverse_context, exact_excerpt, relevance
from signal_research.research.falsification import observable_tests
from signal_research.research.headline import template_headline, validate_headline
from signal_research.research.history import (
    comparable_series,
    has_relationship_evidence,
    needs_history,
)
from signal_research.research.history_cache import historical_observations
from signal_research.research.identity import (
    foreign_cover_identity,
    identity_aliases,
    issuer_cover_identity,
    issuer_named,
    issuer_symbol_reference,
    multiple_issuer_headings,
    presentation_issuer_identity,
    structured_issuer_identity,
)
from signal_research.research.integrity import attest_report
from signal_research.research.novelty import Novelty, classify_novelty
from signal_research.research.numeric_claims import (
    complete_calculation_lineage,
    supported_percentages,
)
from signal_research.research.peer_selector import select_peers
from signal_research.research.peers import compare_peers, peer_model_context
from signal_research.research.report_builder import build_abstention
from signal_research.research.sector import CONTEXT_TERMS, extraction_instruction
from signal_research.research.story import quarter_ends, timeline_story
from signal_research.research.structural import (
    break_calculations,
    detect_breaks,
    recovery_calculations,
)
from signal_research.retrieval.disclosures import (
    embedded_disclosures,
    exchange_results_query,
    issuer_navigation,
    linked_disclosures,
    verified_disclosure_indexes,
)
from signal_research.retrieval.exchange_tables import exchange_table_batch
from signal_research.retrieval.fetch import FetchResult, PublicFetcher
from signal_research.retrieval.issuer_identity import (
    ISSUER_REFERENCE_POLICY,
    exchange_issuer_domains,
)
from signal_research.retrieval.metadata import (
    domain_matches,
    source_availability,
    source_origin,
    source_publication,
)
from signal_research.retrieval.passages import (
    bounded_parse_pdf,
    parse_html,
    parse_xbrl,
    prioritized_ocr_pages,
)
from signal_research.retrieval.quality import format_prose, sane_publication
from signal_research.worker.calls import DurableCalls


class FactVerdict(StrictModel):
    index: int = Field(ge=0, le=19)
    supported: bool
    reason: str = Field(max_length=300)


class FactReview(StrictModel):
    verdicts: list[FactVerdict] = Field(max_length=20)


def fact_review_schema(count: int):
    """Bound generation to exactly the candidates requiring independent review."""
    return create_model("FactReview", __base__=FactReview,
                        verdicts=(list[FactVerdict], Field(min_length=count, max_length=count)))


class Hypothesis(StrictModel):
    statement: str = Field(max_length=400)
    mechanism: str = Field(max_length=600)
    fact_ids: list[UUID] = Field(min_length=1, max_length=12)
    calculation_ids: list[UUID] = Field(min_length=1, max_length=8)
    next_query: str = Field(max_length=180)
    opposing_query: str = Field(max_length=180)
    falsification: str = Field(max_length=400)
    significance: int = Field(ge=0, le=5)
    novelty: int = Field(ge=0, le=5)


class HypothesisBatch(StrictModel):
    candidates: list[Hypothesis] = Field(max_length=3)
    missing_evidence: list[Annotated[str, Field(max_length=200)]] = Field(max_length=6)


def cited_hypothesis_schema(payload):
    fields = {name: (list[UUID], Field(min_length=1, max_length=limit, json_schema_extra={'items': {
        'type': 'string', 'enum': [str(item['id']) for item in payload[source]]}}))
        for name, source, limit in (('fact_ids', 'facts', 12), ('calculation_ids', 'calculations', 8))}
    hypothesis = create_model('CitedHypothesis', __base__=Hypothesis, **fields)
    return create_model('HypothesisBatch', __base__=HypothesisBatch,
        candidates=(list[hypothesis], Field(max_length=3)))


class Challenge(StrictModel):
    refuted: bool
    unresolved: bool
    strongest_alternative: str = Field(max_length=600)
    reason: str = Field(max_length=800)
    relevant_passage_ids: list[UUID] = Field(max_length=8)
    novelty_status: Literal['additional_supported_synthesis', 'already_covered', 'simple_restatement', 'novelty_unknown'] = 'novelty_unknown'
    novelty_rationale: str = Field(default='', max_length=600)
    published_explanation: str = Field(default='', max_length=600)


class Statement(StrictModel):
    text: str = Field(max_length=600)
    kind: ClaimKind
    fact_ids: list[UUID] = Field(max_length=8)
    passage_ids: list[UUID] = Field(max_length=6)
    calculation_ids: list[UUID] = Field(max_length=6)


class DiscoveryDraft(StrictModel):
    headline: Statement
    why_it_matters: list[Statement] = Field(min_length=3, max_length=5)
    counterargument: Statement
    timeline_analysis: Statement
    onset_status: Literal['identified', 'bounded', 'unknown']
    falsification: str = Field(max_length=500)
    falsification_window: str = Field(min_length=5, max_length=300)
    falsification_source: str = Field(min_length=5, max_length=300)


class PlainHeadline(StrictModel):
    sentence: str = Field(max_length=500)


class CurrentReconciliation(StrictModel):
    status: Literal['supported', 'contradicted', 'not_found']
    passage_ids: list[UUID] = Field(max_length=6)
    reason: str = Field(max_length=400)


def cited_draft_schema(payload):
    """Give the provider an explicit choice of existing evidence identifiers."""
    limits = {'fact_ids': 8, 'passage_ids': 6, 'calculation_ids': 6}
    fields = {name: (list[UUID], Field(max_length=limits[name], json_schema_extra={"items": {
        "type": "string", "enum": [str(item["id"]) for item in payload[source]]}}))
        for name, source in (("fact_ids", "facts"), ("passage_ids", "passages"), ("calculation_ids", "calculations"))}
    statement = create_model("CitedStatement", __base__=Statement, **fields)
    return create_model("DiscoveryDraft", __base__=DiscoveryDraft, headline=(statement, ...),
        counterargument=(statement, ...), timeline_analysis=(statement, ...),
        why_it_matters=(list[statement], Field(min_length=3, max_length=5)))


class ClaimVerdict(StrictModel):
    claim_id: UUID
    supported: bool
    reason: str = Field(max_length=300)


class SemanticReview(StrictModel):
    verdicts: list[ClaimVerdict] = Field(max_length=20)
    falsification_is_observable: bool
    contains_investment_recommendation: bool
    non_obvious_synthesis_supported: bool = False


def semantic_review_schema(claim_ids):
    verdict = create_model('BoundClaimVerdict', __base__=ClaimVerdict,
        claim_id=(UUID, Field(json_schema_extra={'enum': [str(identifier) for identifier in claim_ids]})))
    return create_model('SemanticReview', __base__=SemanticReview,
        verdicts=(list[verdict], Field(min_length=len(claim_ids), max_length=len(claim_ids))))


def derive_calculations(facts):
    """Registered mathematics only; each output retains its original fact inputs."""
    groups = {}
    for fact in facts:
        key = (fact.metric_key, fact.scope, fact.segment, fact.definition_id, fact.period_type, fact.currency)
        groups.setdefault(key, []).append(fact)
    results = []
    def add(formula, inputs):
        result = calculate(formula, [numeric_fact(f) for f in inputs])
        if result.available:
            results.append(Calculation(id=result.id, formula_id=formula, formula_version=result.formula_version,
                                       input_fact_ids=result.input_fact_ids, output_value=result.output_value, unit=result.unit,
                                       period=" / ".join(str(f.period_end) for f in inputs), scope=inputs[0].scope,
                                       comparability_checks=result.comparability_checks,
                                       limitations=(['Denominator includes deposits and borrowings only, not all liabilities or all funding. Reporting-boundary changes may affect comparisons; this calculation does not prove a causal mechanism.'] if formula.startswith('deposit_borrowing_mix') else [])))
    pairs = []
    for values in groups.values():
        values = sorted(values, key=lambda f: f.period_end)
        for current in values:
            prior = next((f for f in values if f.period_end and current.period_end and (current.period_end.year - f.period_end.year, current.period_end.month, current.period_end.day) == (1, f.period_end.month, f.period_end.day)), None)
            if prior:
                add("change_pp" if current.unit_normalized == "percent" else "yoy_growth", [current, prior])
                if current.unit_normalized == 'percent':
                    add('change_bps', [current, prior])
                pairs.append((current, prior))
    growth_relationships = {
        ('gross_advances', 'deposits'), ('advances_as_reported', 'deposits'),
        ('net_advances', 'deposits'), ('borrowings', 'deposits'),
        ('aum', 'borrowings'), ('on_book_loans', 'borrowings'),
        ('vnb', 'ape'), ('net_profit', 'revenue'),
        ('transaction_revenue', 'revenue'), ('fee_revenue', 'average_aum'),
    }
    for a, b in pairs:
        if a.unit_normalized == 'percent':
            continue
        for c, d in pairs:
            if (a.metric_key, c.metric_key) in growth_relationships:
                add("growth_gap", [a, b, c, d])
                if a.metric_key == "gross_advances":
                    add("ldr_change", [a, b, c, d])
                    add("loan_to_deposit", [a, c])
                    add("loan_to_deposit", [b, d])
    for numerator, denominator, formula in (
        ('deposits', 'borrowings', 'deposit_borrowing_mix'),
        ("vnb", "ape", "vnb_to_ape"), ("fee_revenue", "average_aum", "fee_yield"),
        ("bank_borrowings", "borrowings", "funding_share"),
        ("bond_borrowings", "borrowings", "funding_share"),
        ("net_profit", "revenue", "profit_margin"),
        ("transaction_revenue", "revenue", "transaction_revenue_share"),
    ):
        for a in facts:
            if a.metric_key == numerator:
                for b in facts:
                    if b.metric_key == denominator:
                        add(formula, [a, b])
    mix_groups = {}
    for fact in facts:
        if fact.metric_key in {'deposits', 'borrowings'}:
            key = (fact.scope, fact.segment, fact.currency, fact.unit_normalized, fact.period_type)
            mix_groups.setdefault(key, {}).setdefault(fact.period_end, {})[fact.metric_key] = fact
    for periods in mix_groups.values():
        complete = sorted((end, measures) for end, measures in periods.items()
                          if end and {'deposits', 'borrowings'} <= measures.keys())
        for index, (_, current) in enumerate(complete):
            if index == 0:
                continue
            prior = complete[index - 1][1]
            add('deposit_borrowing_mix_change', [current['deposits'], current['borrowings'], prior['deposits'], prior['borrowings']])
        if len(complete) > 2:
            prior, current = complete[0][1], complete[-1][1]
            add('deposit_borrowing_mix_change', [current['deposits'], current['borrowings'], prior['deposits'], prior['borrowings']])
    for series in comparable_series(facts):
        if series['cadence'] == 'quarterly':
            by_id = {f.id: f for f in facts}
            ordered = [by_id[o['fact_id']] for o in series['observations']]
            for prior, current in zip(ordered, ordered[1:]):
                add('change_pp' if current.unit_normalized == 'percent' else 'period_change', [current, prior])
    return results


class LiveResearch:
    def __init__(self, machine, run_id, company, cutoff, budget, settings=None):
        self.machine, self.store, self.settings = machine, machine.store, settings or machine.settings
        self.run_id, self.company, self.cutoff, self.budget = run_id, company, cutoff, budget
        self.calls = DurableCalls(self.store, self.settings, run_id, budget)
        summary = self.store.get_summary(run_id)
        self.is_deep = bool(summary and summary.mode.value == 'deep')
        self.documents, self.passages, self.facts, self.calculations = [], [], [], []
        self.seen_urls, self.extracted, self.queries, self.limitations = set(), set(), [], []
        self.source_titles = []
        self.evidence_iteration = 0
        self.decisions = []
        self.challenge_reviews = []
        self.opposing_queries = []
        self.context_searches = []
        self.draft_feedback = None
        self.extraction_paused = False
        self.extraction_deadline_reserve = 0
        self.history_cache = []
        self.plan_questions = []
        self.revalidated_documents = set()
        self.structural_breaks = []
        self.peer_mode = False
        self.now_check = {'status': 'not_checked', 'passage_ids': [], 'reason': 'Current reconciliation review has not completed.'}
        self.peer_benchmark = {'status': 'inconclusive', 'comparisons': [], 'missing': ['Peer collection not completed.']}

    def time_reserve(self, seconds):
        """Scale stage allowances to the configured total research deadline."""
        duration = self.settings.max_run_seconds if self.is_deep else min(self.settings.max_run_seconds, self.settings.demo_target_seconds)
        return min(seconds, duration * seconds / 900)

    def analysis_reserve(self):
        """Reserve a real reasoning window, not just one last provider response."""
        if self.peer_mode:
            return self.time_reserve(120)
        duration = self.settings.max_run_seconds if self.is_deep else min(self.settings.max_run_seconds, self.settings.demo_target_seconds)
        stages = self.settings.stage_request_seconds
        # Leave room for a hypothesis, peer fact extraction/review, independent
        # challenge, composition and final review. Optional history must not
        # consume that window simply because the total deadline was increased.
        core = sum(stages.get(stage, self.settings.model_request_timeout_seconds)
                   for stage in ('hypothesizing', 'extracting', 'normalizing', 'challenging', 'composing', 'verifying'))
        return min(core, duration * .65)

    def peer_document_reserve(self):
        """Keep bounded source slots for numeric peers and opposing evidence."""
        return min(6, self.budget.max_fetch_documents // 3)

    def stage(self, status, summary):
        from signal_research.domain.enums import RunStatus
        self.machine._set_stage(self.run_id, RunStatus(status), f"live_{status}", summary)

    def search(self, query, domains=None, opposing=False, *, search_depth=None):
        self.queries.append(query)
        if opposing and query not in self.opposing_queries:
            self.opposing_queries.append(query)
        options = {'search_depth': search_depth} if search_depth else {}
        hits = self.calls.search(query, domains, self.cutoff, "challenging" if opposing else "discovering", **options)
        self.source_titles.extend(hit.title for hit in hits if hit.title)
        # Search metadata ranks retrieval leads only. It never verifies issuer
        # identity, a publication date or a financial figure.
        financial_search = bool(re.search(r'financial results|financial statements|annual report|investor presentation', query.replace('"', ''), re.I))
        annual_search = bool(re.search(r'annual report', query.replace('"', ''), re.I))
        # Filter before callers take their bounded slice. Otherwise previously
        # fetched releases can occupy both slots and hide a new useful document.
        fresh_hits = [hit for hit in hits if hit.url not in self.seen_urls]
        return sorted(fresh_hits, key=lambda hit: (
            '/corporate/ixbrl/' in hit.url.lower() if financial_search or 'INTEGRATED FILING' in query else False,
            not bool(re.search(r'\bsubsidiar(?:y|ies)\b', re.sub(r'[-_/]+', ' ', unquote(hit.url)), re.I)) if financial_search else False,
            bool(re.search(r'annual[-_\s]+report|integrated[-_\s]+report|(?:^|[^a-z])iar(?:[^a-z]|$)', unquote(hit.url) + ' ' + hit.title, re.I)) if annual_search else False,
            bool(re.search(r'(?:un)?audited[-_\s]+financial[-_\s]+results|statement[-_\s]+of[-_\s]+assets|balance[-_\s]+sheet', unquote(hit.url) + ' ' + hit.title, re.I)) if financial_search else False,
            issuer_named(hit.title, self.company),
            issuer_named(hit.title + " " + hit.snippet, self.company),
            bool(re.search(r"\.pdf(?:[/?#]|$)", hit.url, re.I)),
            bool(re.search(r"financial\s+results|investor\s+presentation", hit.title, re.I))), reverse=True)

    def search_many(self, queries):
        """Search independent leads concurrently, keeping source-priority order.

        DurableCalls and Budget serialize reservations; a result remains only a
        retrieval lead until the normal source and numerical gates verify it.
        """
        from concurrent.futures import ThreadPoolExecutor
        if not queries:
            return []
        with ThreadPoolExecutor(max_workers=min(3, len(queries))) as pool:
            futures = [pool.submit(self.search, query, domains) for query, domains in queries]
            return [future.result() for future in futures]

    def ingest(self, hits, *, time_reserve=0, parse_limit=None, stop_when_balance_ready=False,
               stop_when_financial_ready=False, document_reserve=0):
        from concurrent.futures import ThreadPoolExecutor
        candidates = list({hit.url: hit for hit in hits if hit.url not in self.seen_urls
                           and re.search(r'\.pdf(?:[?#]|$)|/ixbrl/|\.xbrl(?:[?#]|$)', hit.url, re.I)}.values())
        count = min(len(candidates), self.settings.max_fetch_concurrency,
                    max(0, self.budget.max_fetch_documents - document_reserve - self.budget.fetch_documents))
        def prefetch(hit):
            fetcher = PublicFetcher(self.settings.data_dir, min(self.settings.source_request_timeout_seconds,
                max(.1, self.budget.remaining_seconds() - time_reserve)), self.settings.max_source_bytes)
            return self.calls.invoke(['fetch', hit.url], 'fetching', lambda: self.budget.reserve('fetch_documents'),
                lambda: (fetcher.fetch(hit.url), {'provider': 'public_http'}), asdict, lambda p: FetchResult(**p))
        prefetched = {}
        if count and self.budget.remaining_seconds() > time_reserve:
            with ThreadPoolExecutor(max_workers=count) as pool:
                futures = {hit.url: pool.submit(prefetch, hit) for hit in candidates[:count]}
                for url, future in futures.items():
                    prefetched[url] = future.result()
        queue = [(hit, 0) for hit in hits]
        while queue:
            hit, depth = queue.pop(0)
            self.budget.check()
            if self.budget.remaining_seconds() <= time_reserve:
                self.limitations.append("Additional retrieval stopped to preserve time for verification and the final report.")
                break
            if self.machine._cancelled(self.run_id):
                return
            if hit.url in self.seen_urls:
                continue
            self.seen_urls.add(hit.url)
            if hit.url not in prefetched and self.budget.fetch_documents >= self.budget.max_fetch_documents - document_reserve:
                self.limitations.append("Document cap reached; remaining source leads were withheld.")
                break
            fetcher = PublicFetcher(self.settings.data_dir, min(self.settings.source_request_timeout_seconds, max(.1, self.budget.remaining_seconds() - time_reserve)), self.settings.max_source_bytes)
            fetched = prefetched[hit.url] if hit.url in prefetched else self.calls.invoke(["fetch", hit.url], "fetching", lambda: self.budget.reserve("fetch_documents"),
                                        lambda: (fetcher.fetch(hit.url), {"provider": "public_http"}), asdict, lambda p: FetchResult(**p))
            if not fetched.local_path or not fetched.body_hash:
                self.limitations.append(f"Source unavailable: {hit.url}: {fetched.error}")
                continue
            known = next((d for d in self.documents if d.content_hash == fetched.body_hash), None)
            if known:
                self.revalidated_documents.add(known.id)
                continue
            document_id = UUID(bytes=bytes.fromhex(fetched.body_hash[:32]))
            raw = Path(fetched.local_path).read_bytes()
            if depth < 3 and fetched.content_type == "text/html":
                leads = linked_disclosures(raw, fetched.final_url or hit.url, self.company.verified_ir_domains, issuer_name=self.company.legal_name)
                leads += embedded_disclosures(raw, fetched.final_url or hit.url, self.company.verified_ir_domains)
                leads += issuer_navigation(raw, fetched.final_url or hit.url, self.company.verified_ir_domains) if depth < 2 else []
                queue[:0] = [(lead, depth + 1) for lead in leads if lead.url not in self.seen_urls]
            try:
                if raw.startswith(b"%PDF"):
                    parsed = bounded_parse_pdf(document_id, Path(fetched.local_path), min(self.settings.pdf_parse_timeout_seconds, parse_limit or self.settings.pdf_parse_timeout_seconds, max(.1, self.budget.remaining_seconds() - time_reserve)))
                elif "xml" in (fetched.content_type or ""):
                    parsed = parse_xbrl(document_id, raw)
                else:
                    parsed = parse_html(document_id, raw)
                native_cover = '\n'.join(p.text for p in parsed.passages if p.page_index == 0)
                ocr_pages = prioritized_ocr_pages(parsed)
                if foreign_cover_identity(native_cover, self.company):
                    ocr_pages = []  # Do not OCR another issuer's annual report.
                # Native financial tables already provide original source spans.
                # OCR unrelated blank artwork must not consume the demo window.
                if any(self.financial_passage(p) for p in parsed.passages):
                    ocr_pages = [page for page in ocr_pages if page == 0]
                per_document_ocr = min(3, self.settings.max_ocr_pages)
                if len(ocr_pages) > per_document_ocr:
                    self.limitations.append('Additional scanned pages deferred after the bounded cover/financial-page pass; source coverage is incomplete.')
                for page_index in ocr_pages[:per_document_ocr]:
                    if self.budget.ocr_pages >= self.budget.max_ocr_pages:
                        self.limitations.append("OCR page cap reached; remaining scanned pages were withheld.")
                        break
                    if self.budget.remaining_seconds() <= time_reserve:
                        self.limitations.append("Additional OCR stopped to preserve time for verification and the final report.")
                        break
                    from signal_research.extraction.ocr import ocr_page
                    try:
                        ocr_text = self.calls.invoke(["ocr", fetched.body_hash, page_index], "extracting", lambda: self.budget.reserve("ocr_pages"),
                                                    lambda: (ocr_page(Path(fetched.local_path), page_index, self.settings.data_dir, min(self.settings.source_request_timeout_seconds, max(.1, self.budget.remaining_seconds() - time_reserve)), pdftoppm_path=self.settings.pdftoppm_path, tesseract_path=self.settings.tesseract_path), {"provider": "local_ocr"}))
                        if ocr_text.strip():
                            parsed.passages.append(Passage(id=uuid5(document_id, f"ocr:{page_index}:{ocr_text}"), document_id=document_id, page_index=page_index, printed_page_label=str(page_index + 1), text=ocr_text, extraction_method="ocr", extraction_quality="numeric_confidence_at_least_95"))
                    except Exception as exc:
                        identity_text = getattr(exc, 'identity_text', '') if page_index == 0 else ''
                        if identity_text and issuer_cover_identity(identity_text, self.company):
                            parsed.passages.append(Passage(id=uuid5(document_id, f'ocr_identity:{page_index}:{identity_text}'),
                                document_id=document_id, page_index=page_index, text=identity_text,
                                extraction_method='ocr_identity', extraction_quality='identity_only; numeric evidence prohibited'))
                        self.limitations.append(f"OCR page {page_index + 1} withheld: {exc}")
            except Exception as exc:
                self.limitations.append(f"Source parse failed: {hit.url}: {exc}")
                continue
            text = "\n".join(p.text for p in parsed.passages)
            published = source_publication(raw, text)
            published, date_warning = sane_publication(raw, text, hit.title or parsed.title, published)
            if date_warning:
                self.limitations.append(date_warning)
            receipt = datetime.fromisoformat(fetched.retrieved_at) if fetched.retrieved_at else None
            eligibility, eligibility_basis = source_availability(published, receipt, self.cutoff)
            if eligibility == 'eligible':
                domains = exchange_issuer_domains(raw, text, fetched.final_url or hit.url, self.company)
                if domains:
                    proof = {
                        'reference_policy': ISSUER_REFERENCE_POLICY, 'company_id': str(self.company.id),
                        "source_url": fetched.final_url or hit.url, "document_id": str(document_id), "domains": domains,
                        "availability_basis": eligibility_basis, "published_at": published, "retrieved_at": receipt,
                        "content_hash": fetched.body_hash}
                    self.store.add_verified_issuer_domains(self.company.id, domains, document_id,
                                                         run_id=self.run_id, proof=proof)
                    self.company.verified_ir_domains = list(dict.fromkeys([*domains, *self.company.verified_ir_domains]))
                    queue.extend((lead, 0) for lead in verified_disclosure_indexes(self.company) if lead.url not in self.seen_urls)
            publisher, origin, kind = source_origin(fetched.final_url or hit.url, self.company, hit.title, text)
            cover_text = '\n'.join(p.text for p in sorted(parsed.passages, key=lambda p: p.page_index or 0) if p.page_index in {0, 1, 2})
            identified = (issuer_cover_identity(cover_text, self.company) or issuer_cover_identity(text[:3000], self.company) or issuer_named(text[:3000], self.company)
                          or issuer_symbol_reference(text, self.company))
            if raw.startswith(b"%PDF") and foreign_cover_identity(cover_text or text, self.company):
                identified = False
            portal_host = urlparse(fetched.final_url or hit.url).hostname or ''
            shared_portal = any(other.id != self.company.id and
                               any(domain_matches(portal_host, domain) for domain in other.verified_ir_domains)
                               for other in self.store.search_companies(''))
            if shared_portal:
                identified = (issuer_cover_identity(text[:3000], self.company) or structured_issuer_identity(text, self.company)
                              or presentation_issuer_identity(cover_text, fetched.final_url or hit.url, self.company)) and not foreign_cover_identity(cover_text, self.company)
            if not identified and self.company.business_profiles[0].value == 'bank':
                # A branded bank presentation can use an acronym cover, while
                # its comparative SOLO/GROUP table explicitly binds the issuer.
                # The binder checks target aliases, scope, dates and columns.
                identified = any(comparative_bank_batch(p, self.company) for p in parsed.passages)
            own_host = any(domain_matches(portal_host, d) for d in self.company.verified_ir_domains)
            exchange_host = any(domain_matches(portal_host, d) for d in ('nseindia.com', 'bseindia.com'))
            original_filing = bool(re.search(r'annual\s+report|statement\s+of\s+(?:assets|financial)|audited\s+financial\s+results|integrated\s+filing', cover_text[:5000], re.I))
            external_analysis = bool(re.search(r'equity\s+research|research\s+(?:report|analyst)|target\s+price|rating\s+(?:rationale|action)|ratings?\s+(?:reaffirmed|assigned)', cover_text[:5000], re.I))
            if identified and original_filing and not external_analysis and not own_host and not exchange_host and raw.startswith(b'%PDF'):
                publisher, origin, kind = self.company.legal_name, f'issuer:{self.company.id}', 'issuer_mirror'
                self.limitations.append(f'Third-party mirror: {hit.url}. Original issuer origin retained; this is not independent corroboration.')
            if raw.startswith(b"%PDF") and kind.startswith("issuer") and not identified:
                # Group portals host parent and subsidiary reports. Keep the
                # related origin so it cannot become independent corroboration,
                # but do not extract target facts from an unidentified cover.
                kind = "related_issuer_context"
                self.limitations.append("Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.")
            for existing in self.documents:
                existing_text = "\n".join(p.text for p in self.passages if p.document_id == existing.id)
                if len(text) > 100 and near_duplicate(text, existing_text):
                    origin = existing.origin_family_id
            if eligibility_basis == 'verified_retrieval':
                self.limitations.append(f"Original publication date unknown for {hit.url}; public availability is verified by the dated retrieval receipt, not an inferred publication date.")
            document = SourceDocument(id=document_id, canonical_url=hit.url, final_url=fetched.final_url or hit.url,
                                      publisher=publisher, origin_family_id=origin, title=hit.title or parsed.title, document_type=kind,
                                      published_at=published, retrieved_at=receipt or datetime.now(UTC), content_hash=fetched.body_hash,
                                      mime_type=fetched.content_type or "application/octet-stream", local_object_key=fetched.local_path,
                                      cutoff_eligibility=eligibility, cutoff_eligibility_basis=eligibility_basis)
            self.documents.append(document)
            self.passages.extend(parsed.passages)
            self.progress()
            if stop_when_financial_ready and kind.startswith('issuer') and eligibility == 'eligible':
                if any(exchange_table_batch(p, self.company, self.company.business_profiles[0]) or
                       (abbreviated_quarter_periods(p.text) and self.financial_passage(p) and
                        minimum_source_bindings(p, self.company.business_profiles[0])) for p in parsed.passages):
                    break  # Review this explicit filing before downloading weaker leads.
            if stop_when_balance_ready and kind.startswith("issuer") and document.cutoff_eligibility == "eligible":
                # Enough explicit comparative balances can enter independent
                # extraction review now; remaining annual-report leads must not
                # consume the time needed to challenge and verify the findings.
                batches = [comparative_bank_batch(p, self.company) for p in parsed.passages]
                if any(batch and len(batch.facts) >= 4 and all(f.period_end <= self.cutoff for f in batch.facts) for batch in batches):
                    break
        self.progress()

    def progress(self, checks=None):
        if self.peer_mode:
            return
        reused = {identifier for item in self.history_cache for identifier in item['fact_ids']}
        self.store.update_run(self.run_id, progress={"sources_found": len(self.seen_urls), "documents_parsed": len(self.documents), 'facts_verified': len(self.facts),
            'facts_reused': sum(str(f.id) in reused for f in self.facts), 'facts_fresh': sum(str(f.id) not in reused for f in self.facts),
            "calculations_completed": len(self.calculations), "counterevidence_checks": len(self.challenge_reviews)})

    def financial_passage(self, passage):
        aliases = [alias for metric in metrics_for_profile(self.company.business_profiles[0])
                   for alias in (*metric.aliases, metric.key.replace('_', ' '))]
        return bool(re.search(r'\d', passage.text) and any(
            re.search(r'\b' + re.escape(alias) + r'\b', passage.text, re.I) for alias in aliases))

    def issuer_financial_coverage(self):
        eligible = {d.id for d in self.documents if d.cutoff_eligibility == 'eligible' and d.document_type.startswith('issuer')}
        return any(p.document_id in eligible and self.financial_passage(p) for p in self.passages)

    def extraction_model(self, passage, schema, payload, *args):
        from signal_research.providers.llm.codecraft_provider import (
            CodeCraftStructuredOutputError,
            CodeCraftTimeout,
        )
        from signal_research.providers.llm.nvidia_provider import (
            NvidiaStructuredOutputError,
            NvidiaTimeout,
        )

        previous_reserve = self.calls.deadline_reserve_seconds
        self.calls.deadline_reserve_seconds = self.extraction_deadline_reserve
        try:
            return self.calls.model(schema, payload, *args)
        except (CodeCraftTimeout, NvidiaTimeout) as exc:
            if not self.facts:
                raise
            # Do not repeat an uncertain request. Existing approved facts can
            # still support distinct hypothesis/challenge requests while optional
            # extraction is paused for the rest of this run.
            self.extraction_paused = True
            self.store.artifact(self.run_id, 'extraction_failure', {
                'passage_id': passage.id, 'schema': schema.__name__, 'error_code': exc.code,
                'reason': str(exc), 'action': 'optional extraction paused; uncertain request not retried'})
            self.limitations.append(f'Optional extraction paused after an uncertain provider response: {exc}. Previously verified evidence remains available for investigation.')
            return None
        except (NvidiaStructuredOutputError, CodeCraftStructuredOutputError) as exc:
            # Another source may be usable. No result from this response can be
            # approved, and duplicate PDF views must not repeat the failed page.
            if passage.page_index is not None:
                self.extracted.update(p.id for p in self.passages
                    if (p.document_id, p.page_index) == (passage.document_id, passage.page_index))
            self.store.artifact(self.run_id, 'extraction_failure', {
                'passage_id': passage.id, 'schema': schema.__name__, 'error_code': exc.code,
                'reason': str(exc), 'action': 'source withheld; request not retried'})
            self.limitations.append(f"Extraction response withheld: {exc}; this source request was not retried.")
            return None
        finally:
            self.calls.deadline_reserve_seconds = previous_reserve

    def angle_evidence_ready(self, calculations=None):
        """Stop collection only for a comparable, profile-native research relationship."""
        calculations = self.calculations if calculations is None else calculations
        calculations = [c for c in calculations if c.available and c.output_value is not None]
        definitions = {angle.key: angle for angle in ANGLES}
        for lane in research_lanes(self.facts, calculations):
            facts = [f for f in self.facts if f.id in lane['fact_ids']]
            arithmetic = [c for c in calculations if c.id in lane['calculation_ids']]
            for angle in route_angles(self.company, facts, arithmetic):
                if angle['coverage_groups'] != angle['required_groups']:
                    continue
                relevant = {f.id for f in facts if f.metric_key in angle['metrics']}
                linked = [c for c in arithmetic if set(c.input_fact_ids) <= relevant]
                cited = {identifier for c in linked for identifier in c.input_fact_ids}
                dates = [{f.period_end for f in facts if f.id in cited
                          and f.metric_key in group and f.period_end}
                         for group in definitions[angle['key']].groups]
                if (dates and set.intersection(*dates)
                        and has_relationship_evidence(facts, linked)):
                    return True
        return False

    def extract(self, limit=4, *, preferred_document_ids=None, historical=False, focus_metrics=()):
        self.extraction_deadline_reserve = self.analysis_reserve() if historical or focus_metrics else 0
        profile = self.company.business_profiles[0]
        metrics = metrics_for_profile(profile)
        focus = [metric for metric in metrics if metric.key in focus_metrics]
        def focus_score(passage):
            return sum(bool(re.search(r'\b' + re.escape(alias) + r'\b', passage.text, re.I))
                       for metric in focus for alias in (*metric.aliases, metric.key.replace('_', ' ')))
        eligible = {d.id for d in self.documents if d.cutoff_eligibility == "eligible" and d.document_type.startswith("issuer")}
        ambiguous = {p.id for p in self.passages if p.document_id in eligible and
                     multiple_issuer_headings(p.text, self.company.legal_name)}
        if ambiguous:
            note = 'Extraction gap: multiple issuer headings require isolated disclosure spans; interleaved page figures were withheld.'
            if note not in self.limitations:
                self.limitations.append(note)
        published = {d.id: d.published_at.timestamp() if d.published_at else 0 for d in self.documents}
        def score(p):
            text = p.text.lower()
            labels = sum(bool(re.search(r"\b" + re.escape(alias.lower()) + r"\b", text)) for m in metrics for alias in m.aliases)
            # Actual balance rows with comparative headers outrank audit commentary
            # and incidental mentions of advances in interest-income rows.
            rows = len(re.findall(r"(?m)^\s*(?:total\s+|gross\s+|net\s+)?(?:advances|deposits|borrowings)\b[^\n]*\d", text))
            bindings = any(scope_in_text(scope, text) for scope in ("standalone", "consolidated"))
            dates = bool(month_end_columns(p.text) or re.search(r"\b\d{1,2}[./-]\d{1,2}[./-]20\d{2}\b|\b(?:march|june|september|december)\b[^\n]*20\d{2}", text))
            # A readable, explicitly denominated table beats an OCR-damaged
            # newer page or a narrative that merely mentions metric names.
            unit_header = bool(re.search(r"(?:₹|INR|Rs\.?)\s*(?:in\s+)?(?:crores?|cr|lakhs?|thousands?|[‘’']?000|millions?|billions?)\b", p.text[:1200], re.I))
            financial_rows = sum(bool(re.search(r"(?im)^\s*(?:\d+[.)]?\s+)?" + re.escape(alias) + r"\b[^\n]*\d", p.text))
                                 for metric in metrics for alias in (*metric.aliases, metric.key.replace('_', ' ')))
            numeric_measures = sum(bool(re.search(r'(?<!\w)' + re.escape(alias) +
                r'(?!\w)(?:\s*\([^()\d]{1,24}\))?\s*(?:(?:was|were|of|is|stood at|[|:=])\s*)?'
                r'(?:(?:INR|Rs\.?|\u20b9)\s*)?\(?-?\d[\d,]*(?:\.\d+)?', p.text, re.I))
                for metric in metrics for alias in (*metric.aliases, metric.key.replace('_', ' ')))
            periods = [period for period in source_dates(p.text) if period <= self.cutoff]
            periods.extend(period for _, period in month_end_columns(p.text) if period <= self.cutoff)
            periods.extend(p['period_end'] for p in abbreviated_quarter_periods(p.text) if p['period_end'] <= self.cutoff)
            latest_period = max(periods).toordinal() if periods else 0
            numeric_lead = numeric_measures > 0 or column_metric_lead(p, profile)
            return (p.document_id in (preferred_document_ids or ()), numeric_lead, bindings and dates and unit_header, bindings and dates, rows > 0 if profile.value == "bank" else financial_rows > 0, p.extraction_method not in {"pdf_table", "html_table"}, rows if profile.value == "bank" else financial_rows, latest_period, published[p.document_id], labels)
        ranked = sorted([p for p in self.passages if p.extraction_method != 'ocr_identity' and p.id not in self.extracted and p.id not in ambiguous and p.document_id in eligible and
                         (preferred_document_ids is None or p.document_id in preferred_document_ids) and
                         not subsidiary_only(p.text) and self.financial_passage(p) and minimum_source_bindings(p, profile)
                         and score(p)[1] and (not focus or focus_score(p))],
                        key=lambda p: (bool(getattr(self, 'preferred_scope', None) and scope_in_text(self.preferred_scope, p.text)), focus_score(p), *score(p)), reverse=True)
        if not ranked and eligible:
            note = 'No unreviewed financial page had the explicit date, scope, unit and numeric metric bindings required for model extraction.'
            if note not in self.limitations:
                self.limitations.append(note)
        passages, pages = [], set()
        for passage in ranked:
            location = (passage.document_id, passage.page_index)
            if passage.page_index is not None and location in pages:
                continue
            if passage.page_index is not None:
                pages.add(location)
            passages.append(passage)
            if len(passages) == limit:
                break
        starting_periods = {(f.scope, f.metric_key, f.period_end) for f in self.facts}
        for passage in passages:
            if self.extraction_paused:
                break
            if (historical or focus_metrics) and self.budget.remaining_seconds() <= self.analysis_reserve():
                self.limitations.append('Additional extraction deferred to preserve the discovery, challenge and final-review window.')
                break
            self.extracted.add(passage.id)
            identity_passages = [p for p in self.passages if p.document_id == passage.document_id and p.page_index in {None, 0, 1, 2}][:6]
            identity_passages = [p for p in identity_passages if issuer_cover_identity(p.text, self.company)
                                 or issuer_symbol_reference(p.text, self.company)
                                 or (presentation_issuer_identity('\n'.join(ip.text for ip in identity_passages),
                                     next(d.canonical_url for d in self.documents if d.id == passage.document_id), self.company)
                                     and issuer_named(p.text, self.company))]
            issuer_bound = bool(identity_passages)
            ratio_batch = stock_ratio_batch(passage, self.company, profile,
                                           document_issuer_verified=issuer_bound, focus_metrics=focus_metrics)
            batch = ratio_batch if ratio_batch and any(f.metric_key in focus_metrics for f in ratio_batch.facts) else None
            if batch is None:
                batch = comparative_bank_batch(passage, self.company, document_issuer_verified=issuer_bound, preferred_scope=getattr(self, "preferred_scope", None)) if profile.value == "bank" else None
            if batch is None:
                batch = exchange_table_batch(passage, self.company, profile)
            if batch is None:
                batch = quarter_presentation_batch(passage, self.company, profile, document_issuer_verified=issuer_bound)
            if batch is None:
                batch = financial_table_batch(passage, self.company, profile, document_issuer_verified=issuer_bound)
            if batch is None:
                batch = ratio_batch
            extraction_method = passage.extraction_method if batch and passage.extraction_method == 'exchange_table' else "explicit_comparative_columns" if batch else "model"
            if batch is None:
                dates = sorted(set(source_dates(passage.text)) | {period for _, period in month_end_columns(passage.text)}
                               | {p['period_end'] for p in abbreviated_quarter_periods(passage.text)})
                batch = self.extraction_model(passage, source_fact_batch_schema([m.key for m in metrics], passage.id, dates), {"passage_id": passage.id, "entity": self.company.legal_name,
                                      "source_period_columns": [{"label": label, "period_end": str(period)} for label, period in month_end_columns(passage.text)],
                                      "source_declared_durations": [*declared_duration_periods(passage.text), *explicit_duration_ranges(passage.text), *abbreviated_quarter_periods(passage.text)],
                                      "document_identity_passages": [{"id": p.id, "text": p.text[:1600]} for p in identity_passages if issuer_named(p.text, self.company)],
                                      "allowed_metric_keys": [m.key for m in metrics],
                                      "research_focus_metrics": list(focus_metrics),
                                      "allowed_metric_definitions": [{"key": m.key, "period_type": "instant" if m.kind == "stock" else "duration"} for m in metrics],
                                      "passage_text": passage.text}, "extract", "extracting",
                                      extraction_instruction(profile) + " Prefer research_focus_metrics where supplied, including their comparative periods, before unrelated balance rows. Supplied source_declared_durations normalize an explicit duration and full end date; use only the matching start/end pair. Never use the period of a different column or metric.")
                if batch is None:
                    batch = ExtractedFactBatch(notes=['Incomplete extraction response; no candidates accepted.'])
            accepted, candidates, rejected = [], [], []
            for candidate in batch.facts:
                validation = validate_candidate(candidate, passage, self.company.id, profile)
                if validation.fact and validation.fact.period_end <= self.cutoff:
                    accepted.append(validation.fact)
                    candidates.append(candidate)
                else:
                    rejected.append({"metric": candidate.metric_key, "reason": validation.reason or "period exceeds cutoff"})
            if accepted:
                review = self.extraction_model(passage, fact_review_schema(len(candidates)), {"entity": self.company.legal_name, "source_text": passage.text,
                                           "document_identity_passages": [{"id": p.id, "text": p.text[:1600]} for p in identity_passages],
                                           "candidates": [c.model_dump(mode="json", exclude={'evidence_quote', 'extraction_confidence', 'notes'}) | {"index": i} for i, c in enumerate(candidates)]}, "extract", "normalizing",
                                           f"Independently check every indexed candidate. A value appearing somewhere in a passage is insufficient. source_text is the complete evidence passage; evidence_quote=null means review source_text, not missing evidence. document_identity_passages establish issuer identity only, never a financial date or value. Verify exact metric/value/date/column binding, issuer identity (reject peer/subsidiary values), scope, unit, currency, period type, segment and definition. Comparative balance-sheet headers Jun 25 and Dec 25 mean the last calendar day of June and December 2025, respectively. Target-issuer SOLO columns denote standalone scope and GROUP columns consolidated scope; keep the two column groups separate and never treat net advances as gross advances. supported=false for ambiguity. Return exactly {len(candidates)} verdicts, one per explicit candidate index from 0 to {len(candidates) - 1}. Preserve those indices. Compare against each candidate's own current or prior period_end column. Each reason must be one brief sentence of at most 300 characters. Do not repeat candidates or add verdicts.")
                verdicts = {v.index: v for v in review.verdicts} if review else {}
                if len(verdicts) != len(candidates) or set(verdicts) != set(range(len(candidates))):
                    accepted = []
                    rejected.append({"reason": "Independent review returned duplicate or missing candidate indices"})
                else:
                    rejected.extend({"metric": fact.metric_key, "reason": f"Independent source review: {verdicts[i].reason}"}
                                    for i, fact in enumerate(accepted) if not verdicts[i].supported)
                    accepted = [fact for i, fact in enumerate(accepted) if verdicts[i].supported]
            self.facts.extend(accepted)
            current_document = next(d for d in self.documents if d.id == passage.document_id)
            if accepted and current_document.published_at and current_document.published_at.date() < max(f.period_end for f in accepted):
                current_document.published_at = None
                current_document.cutoff_eligibility, current_document.cutoff_eligibility_basis = source_availability(None, current_document.retrieved_at, self.cutoff)
                self.limitations.append('A publication date preceded a verified reporting period and was marked unknown. Availability must be established by a dated retrieval receipt.')
                if current_document.cutoff_eligibility != 'eligible':
                    self.facts = [f for f in self.facts if f.passage_id != passage.id]
                    accepted = []
            if accepted and passage.page_index is not None:
                # PDF text and per-row table views can describe the same page.
                # Once that page has verified facts, do not extract its duplicate
                # views again during a later investigation iteration.
                self.extracted.update(p.id for p in self.passages
                                      if (p.document_id, p.page_index) == (passage.document_id, passage.page_index))
            self.store.artifact(self.run_id, "fact_extraction", {"passage_id": passage.id, "extraction_method": extraction_method, "accepted": [f.model_dump(mode="json") for f in accepted], "rejected": rejected, "missing_metrics": batch.missing_metrics, "notes": batch.notes})
            if not accepted:
                reasons = [item["reason"] for item in rejected] or batch.notes
                for note in reasons:
                    explanation = f"Extraction gap: {note}"
                    if explanation not in self.limitations:
                        self.limitations.append(explanation)
            elif historical and any((f.scope, f.metric_key, f.period_end) not in starting_periods for f in accepted):
                # One useful earlier comparative statement is enough for this
                # window. Reading unrelated cash-flow/related-party pages after
                # it was starving the discovery stages of their entire allowance.
                break
            elif not historical and self.angle_evidence_ready(derive_calculations(self.facts)):
                # Two P&L figures do not establish an NBFC Track A angle. Require
                # both routed groups within one reporting lane, shared dates and
                # verified arithmetic before preserving time for investigation.
                break
        # Disagreements are withheld, not silently overwritten by a later source.
        buckets = {}
        for fact in self.facts:
            key = (fact.metric_key, fact.period_start, fact.period_end, fact.scope, fact.segment, fact.currency, fact.definition_id)
            buckets.setdefault(key, []).append(fact)
        self.facts = []
        for values in buckets.values():
            if len({f.value_decimal for f in values}) == 1:
                self.facts.append(values[0])
            else:
                self.limitations.append(f"Conflicting disclosures withheld for {values[0].metric_key} at {values[0].period_end}; restatement status is unresolved.")
        self.calculations = derive_calculations(self.facts)
        self.structural_breaks = detect_breaks(self.facts, self.passages, self.documents)
        self.calculations.extend(recovery_calculations(self.facts, self.structural_breaks))
        self.progress()
        # Persist the whole reviewed state, including an empty state after a
        # conflict invalidates earlier figures. Recovery must never resurrect
        # figures from an older snapshot or pretend a discovery was established.
        from signal_research.research.verifier import verify_report
        if self.peer_mode:
            return
        snapshot = self.abstain(["Investigation did not finish; retained observations do not establish a discovery."])
        snapshot.outcome = ResearchOutcome.PARTIAL
        verify_report(snapshot)
        self.store.checkpoint(self.run_id, "evidence_collected", self.evidence_iteration, snapshot.model_dump(mode="json"))
        self.evidence_iteration += 1

    def payload(self, hypothesis=None, required_passage_ids=(), *, compact=False):
        documents = {d.id: d for d in self.documents if d.cutoff_eligibility == "eligible"}
        selected_facts = self.facts
        selected_calculations = self.calculations
        if hypothesis:
            identifiers = set(hypothesis.fact_ids) | {i for c in self.calculations if c.id in hypothesis.calculation_ids for i in c.input_fact_ids}
            selected_facts = [f for f in self.facts if f.id in identifiers]
            selected_calculations = [c for c in self.calculations if set(c.input_fact_ids) <= identifiers]
        used = {fact.passage_id for fact in selected_facts}
        supporting = [p for p in self.passages if p.id in used and p.document_id in documents]
        context = [p for p in self.passages if p.document_id in documents and
                   not documents[p.document_id].document_type.startswith("issuer")]
        identities = [*identity_aliases(self.company.legal_name), *self.company.aliases, *self.company.symbols]
        question = (getattr(hypothesis, 'statement', getattr(hypothesis, 'text', '')) + ' ' + getattr(hypothesis, 'mechanism', '') if hypothesis else
                    CONTEXT_TERMS[self.company.business_profiles[0]])
        def context_score(passage):
            return relevance(passage.text, identities, question)
        # Keep only cited issuer spans plus bounded original context. Sending an
        # entire annual report again would exhaust the token cap before analysis.
        bounded_context = diverse_context(context, documents, identities, question)
        used_documents = {p.document_id for p in supporting}
        qualifiers = [p for p in self.passages if p.document_id in used_documents and p.id not in used and
            (p.extraction_method == 'exchange_notes' or re.search(r'\bmerger|amalgamation|acquisition|acquired|restatement|reclassif|regrouped|scope\s+of\s+consolidation|change\s+in\s+accounting', p.text, re.I))]
        qualifiers.sort(key=context_score, reverse=True)
        # Management explanations and operating notes are research evidence too.
        # Restricting issuer input to extracted balance cells hid the narrative
        # that an investigator needs to test against those numbers.
        narrative = [p for p in self.passages if p.document_id in documents and
                     documents[p.document_id].document_type.startswith('issuer') and p.id not in used and
                     re.search(r'cost of (?:funds|deposits)|repric|maturit|sell.down|securiti[sz]|co.lend|slippage|write.off|funding mix|liability mix|management|strategy|persistency|distribution mix|underwriting|fee yield|product mix', p.text, re.I)]
        narrative = diverse_context(narrative, documents, identities, question, limit=3)
        required = [p for p in self.passages if p.id in required_passage_ids and p.document_id in documents]
        selected = list({p.id: p for p in [*([] if compact else supporting), *qualifiers[:2], *narrative, *bounded_context, *required]}.values())
        source_spans = []
        for passage in selected:
            anchors = [f.value_raw for f in selected_facts if f.passage_id == passage.id] if not compact else []
            excerpt = exact_excerpt(passage.text, anchors, question,
                                    limit=max(2000, len(passage.text)) if anchors else 1200 if compact else 2000)
            source_spans.append({"id": passage.id, "document_id": passage.document_id,
                                 'source_role': 'verified_figure_span' if anchors else 'issuer_explanation' if documents[passage.document_id].document_type.startswith('issuer') else 'independent_context',
                                 **excerpt})
        selected_documents = {p.document_id for p in selected} | used_documents
        required_calculations = set(hypothesis.calculation_ids) if hypothesis else set()
        blocked = break_calculations(self.structural_breaks, selected_calculations) if compact else set()
        model_calculations = sorted([c for c in selected_calculations if c.id not in blocked], key=lambda c: (
            c.id in required_calculations,
            c.formula_id.startswith('recovery_ratio') or c.formula_id in {'deposit_borrowing_mix_change', 'growth_gap', 'ldr_change', 'funding_share'},
            c.period or ''), reverse=True)[:24]
        return {"company": self.company.model_dump(mode="json"), "cutoff": self.cutoff,
                "facts": [{key: value for key, value in f.model_dump(mode="json").items() if key in {
                    "id", "entity_id", "metric_key", "value_raw", "value_decimal", "unit_normalized", "currency",
                    "period_start", "period_end", "period_type", "scope", "segment", "definition_id", "passage_id"}} for f in selected_facts],
                "calculations": [calculation_context(c, self.facts) for c in model_calculations],
                "documents": [{"id": d.id, "title": d.title, "publisher": d.publisher,
                               "published_at": d.published_at, "origin_family_id": d.origin_family_id,
                               "document_type": d.document_type} for d in documents.values() if d.id in selected_documents],
                "passages": source_spans,
                "historical_series": comparable_series(selected_facts),
                "structural_breaks": self.structural_breaks,
                "peer_benchmark": peer_model_context(self.peer_benchmark),
                "compatible_research_lanes": research_lanes(selected_facts, model_calculations),
                "coverage_note": ("Planning context uses previously verified structured facts; original numeric spans are omitted here to reduce latency. Exact linked spans are supplied for challenge and final claim review. " if compact else '') + "Passages may be exact bounded excerpts. Omitted text is not evidence of absence. Full passages remain in the report; verified facts retain their independently reviewed bindings."}

    def model_metadata(self):
        # Include actual routing before attestation; changing a sealed report
        # afterwards would invalidate the semantic-review integrity checksum.
        used = list({(call["provider"], call["model"]): None for call in self.store.provider_calls(self.run_id)
                     if call["model"] and call["status"] == "ok"})
        return {"configured_provider": self.settings.llm_provider,
                "routing": "nvidia_planning_configured_review" if self.settings.nvidia_planning else "configured",
                "configured_model_id": self.settings.model_for_role("research"),
                "models_used": [{"provider": provider, "model_id": model} for provider, model in used],
                "provider": (used[0][0] if len({p for p, _ in used}) == 1 else "mixed") if used else self.settings.llm_provider,
                "model_id": used[0][1] if len(used) == 1 else None}

    def abstain(self, reasons):
        report = build_abstention(self.run_id, self.company, self.cutoff, self.documents, self.passages, self.facts, reasons, mode='deep' if self.is_deep else 'live')
        report.limitations += self.limitations
        report.generation_metadata["search_queries"] = self.queries
        report.generation_metadata["research_decisions"] = self.decisions
        report.generation_metadata['challenge_reviews'] = self.challenge_reviews
        report.generation_metadata['opposing_queries'] = self.opposing_queries
        report.generation_metadata['context_searches'] = self.context_searches
        report.generation_metadata['historical_cache'] = self.history_cache
        reused_ids = {identifier for entry in self.history_cache for identifier in entry['fact_ids']}
        report.generation_metadata['cache_usage'] = {'cold_start': self.settings.cold_start, 'reused': sum(str(f.id) in reused_ids for f in self.facts), 'fresh': sum(str(f.id) not in reused_ids for f in self.facts)}
        report.generation_metadata['structural_breaks'] = self.structural_breaks
        report.generation_metadata['peer_benchmark'] = self.peer_benchmark
        best = max(self.decisions, key=lambda d: d.get('score', 0), default=None)
        report.generation_metadata['best_candidate'] = {
            'label': 'Not established', 'text': best['candidate'] if best and supported_percentages(best['candidate'], self.facts, self.calculations)
            else f'Can comparable verified operating figures establish a non-obvious relationship for {self.company.legal_name}?',
            'fact_ids': best['fact_ids'] if best else [str(f.id) for f in self.facts[:4]],
            'calculation_ids': best['calculation_ids'] if best else [], 'missing': list(reasons),
            'reason': best['reason'] if best else 'No candidate passed the evidence gates; this is a research question, not a discovery.'}
        report.generation_metadata['timeline_story'] = timeline_story(self.facts, self.calculations, self.passages, self.documents, self.structural_breaks)
        report.generation_metadata.update(self.model_metadata())
        report.source_coverage['historical_series'] = comparable_series(self.facts)
        fact_passages = {f.passage_id for f in self.facts}
        report.source_coverage['documents_used'] = len({p.document_id for p in self.passages if p.id in fact_passages})
        report.source_coverage['eligible_issuer_documents'] = sum(d.document_type.startswith('issuer') and d.cutoff_eligibility == 'eligible' for d in self.documents)
        report.source_coverage['blocked_sources'] = sum(note.startswith('Source unavailable:') for note in self.limitations)
        # A withheld hypothesis must not discard independently verified arithmetic.
        report.calculations = self.calculations
        report.timeline_events = observation_timeline(self.run_id, self.facts, self.passages, self.documents)
        report.generation_metadata['submission_checklist'] = submission_checklist(report)
        if self.decisions:
            report.abstention.attempted_angles = list(dict.fromkeys(d['candidate'] for d in self.decisions))
            report.abstention.strongest_unconfirmed_lead = next((review['candidate'] for review in self.challenge_reviews if not review['refuted']), None)
        elif self.plan_questions:
            report.abstention.attempted_angles = self.plan_questions
        report.abstention.next_evidence_needed = list(dict.fromkeys(reasons))
        return report

    def focused_query(self, query):
        prefix = f'"{self.company.legal_name}"'
        if prefix.lower() in query.lower():
            return query
        if self.company.legal_name.lower() in query.lower():
            return re.sub(re.escape(self.company.legal_name), lambda _: prefix, query, flags=re.I)
        return f"{prefix} {query}"

    def record_decision(self, hypothesis, disposition, reason, passage_ids=()):
        decision = {'candidate': hypothesis.statement, 'disposition': disposition,
                    'score': hypothesis.significance + hypothesis.novelty,
                    'reason': reason, 'fact_ids': hypothesis.fact_ids,
                    'calculation_ids': hypothesis.calculation_ids,
                    'passage_ids': list(passage_ids), 'published': False,
                    'mechanism': hypothesis.mechanism,
                    'proposed_falsification': hypothesis.falsification,
                    'opposing_query': hypothesis.opposing_query,
                    'label': 'Unverified research candidate; not a discovery'}
        self.decisions.append(decision)
        self.store.artifact(self.run_id, 'research_decision', decision)

    def current_candidate(self, hypothesis):
        facts = {fact.id for fact in self.facts}
        calculations = {calculation.id: calculation for calculation in self.calculations}
        if (set(hypothesis.fact_ids) <= facts and set(hypothesis.calculation_ids) <= calculations.keys()
                and all(set(calculations[identifier].input_fact_ids) <= facts
                        for identifier in hypothesis.calculation_ids)):
            return True
        reason = 'Supporting facts or calculations were withdrawn during source reconciliation; the candidate no longer has current evidence.'
        self.record_decision(hypothesis, 'withheld', reason)
        self.limitations.append(reason)
        return False

    def collect_history(self):
        if not self.calculations or self.extraction_paused:
            return
        years = {fact.period_end.year for fact in self.facts if fact.period_end}
        current_fact_passages = {f.passage_id for f in self.facts if f.period_end and f.period_end.year == self.cutoff.year}
        fact_documents = {p.document_id for p in self.passages if p.id in current_fact_passages}
        current_annual = any(d.id in fact_documents and d.published_at and d.published_at.year == self.cutoff.year
                             and re.search(r'annual|integrated report', d.title, re.I) for d in self.documents)
        if len(years) >= 5 and not needs_history(self.facts) and current_annual:
            return
        self.stage('discovering', 'Seeking original disclosures across five years; checking reporting boundaries and earlier periods')
        structured = any(p.extraction_method == 'exchange_table' for p in self.passages)
        # Comparative annual filings usually contain two endpoints. Three bounded
        # searches cover a five-year window without demanding twenty PDFs up front.
        for offset in (0, 2, 4):
            if (self.budget.search_calls >= self.budget.max_search_calls - 5
                    or self.budget.fetch_documents >= self.budget.max_fetch_documents - 4
                    or self.budget.model_calls >= self.budget.max_model_calls - 8
                    or self.budget.remaining_seconds() <= self.analysis_reserve() + 45):
                self.limitations.append('Historical expansion stopped to preserve opposing-search and final-review allowances; five-year coverage is not assumed.')
                break
            year = self.cutoff.year - offset
            query = (f'"{self.company.legal_name}" "INTEGRATED FILING" {year}' if structured else
                     f'"{self.company.legal_name}" "annual report" {year - 1} {year} filetype:pdf')
            hits = self.search(query, ['nsearchives.nseindia.com'] if structured else self.company.verified_ir_domains or None,
                               search_depth='advanced')
            before = {d.id for d in self.documents}
            previously_revalidated = set(self.revalidated_documents)
            self.ingest(hits[:2], time_reserve=self.analysis_reserve() + 30, parse_limit=25, document_reserve=self.peer_document_reserve())
            fresh = ({d.id for d in self.documents} - before) | (self.revalidated_documents - previously_revalidated)
            if fresh:
                self.extract(limit=4, preferred_document_ids=fresh, historical=True)
            if any(s['comparable_periods'] >= 5 for s in comparable_series(self.facts)):
                break
        self.store.artifact(self.run_id, 'historical_coverage', {'series': comparable_series(self.facts)})
        if needs_history(self.facts):
            self.limitations.append('Only one or two comparable snapshots were verified; trend onset and sustained historical development are not established.')

    def load_historical_cache(self):
        if self.settings.cold_start:
            return
        for report in self.store.historical_reports(self.company.id, self.cutoff):
            facts, passages, documents = historical_observations(report, self.company.id, self.cutoff)
            if not facts:
                continue
            self.facts = list({f.id: f for f in [*self.facts, *facts]}.values())
            self.passages = list({p.id: p for p in [*self.passages, *passages]}.values())
            self.documents = list({d.id: d for d in [*self.documents, *documents]}.values())
            self.source_titles.extend(d.title for d in documents if d.title)
            self.history_cache.append({'source_run_id': str(report.run_id), 'fact_ids': [str(f.id) for f in facts],
                                       'policy': 'Historical observations at least one year old; local source hashes rechecked. No conclusions reused. Current sources are searched and fetched again.'})
        if self.history_cache:
            self.calculations = derive_calculations(self.facts)
            self.store.artifact(self.run_id, 'historical_cache', {'sources': self.history_cache})
            self.limitations.append('Historical observations were reused from earlier live runs after source-hash checks. Original retrieval dates are retained; discovery and counterevidence review are performed for this run.')

    def collect_operating_metrics(self):
        """Go beyond balance growth: seek profile-specific quality, mix and economics."""
        if self.extraction_paused:
            return
        focus = {
            'bank': ('gnpa', 'nnpa', 'nim', 'casa_ratio', 'funding_cost', 'credit_cost'),
            'nbfc': ('aum', 'on_book_loans', 'gross_advances', 'stage2_ratio', 'stage3_ratio', 'gnpa', 'funding_cost', 'credit_cost', 'bank_borrowings', 'co_lending_aum'),
            'life_insurer': ('vnb', 'ape', 'vnb_margin', 'persistency_13m', 'persistency_61m'),
            'general_insurer': ('combined_ratio', 'loss_ratio', 'expense_ratio', 'solvency_ratio'),
            'exchange': ('transaction_revenue', 'trading_turnover', 'fee_revenue'),
            'asset_manager': ('fee_revenue', 'average_aum', 'net_flows'),
            'diversified': ('segment_profit', 'segment_revenue', 'bank_borrowings', 'bond_borrowings'),
        }[self.company.business_profiles[0].value]
        # Fill the missing groups of the best generic angles, rather than
        # collecting quality ratios while never requesting the lending stock.
        angles = route_angles(self.company, self.facts, self.calculations)
        missing = [key for angle in angles for group in angle['missing_groups'] for key in group]
        permitted = {metric.key for metric in metrics_for_profile(self.company.business_profiles[0])}
        focus = tuple(key for key in dict.fromkeys([*missing, *focus]) if key in permitted)
        if (self.budget.model_calls >= self.budget.max_model_calls - 8
                or self.budget.remaining_seconds() <= self.analysis_reserve() + 30):
            return
        observed = {f.metric_key for f in self.facts if f.metric_key in focus
                    and f.period_end and f.period_end >= self.cutoff - timedelta(days=400)}
        if len(observed) >= 3 and self.angle_evidence_ready():
            return
        self.stage('extracting', 'Seeking asset quality, funding composition and operating economics beyond headline growth')
        self.extract(limit=2, focus_metrics=focus)

    def collect_sector_context(self, peers):
        """Retrieve original peer/regulator context, never relabel peer figures as target facts."""
        profile = self.company.business_profiles[0]
        regulator = ('RBI', ['rbi.org.in']) if profile.value in {'bank', 'nbfc'} else (
            ('IRDAI', ['irdai.gov.in']) if 'insurer' in profile.value else ('SEBI', ['sebi.gov.in']))
        queries = [('regulator', f'{regulator[0]} {CONTEXT_TERMS[profile]} {self.cutoff.year}', regulator[1])]
        for peer in peers.peers:
            queries.append(('peer', f'"{peer.legal_name}" "financial results" {CONTEXT_TERMS[profile]} {self.cutoff.year}', peer.verified_ir_domains or None))
        for kind, query, domains in queries:
            if (self.budget.search_calls >= self.budget.max_search_calls - 4
                    or self.budget.fetch_documents >= self.budget.max_fetch_documents - 3
                    or self.budget.remaining_seconds() <= self.analysis_reserve() + 30):
                self.limitations.append('Additional regulator/peer retrieval stopped to preserve final verification; comparisons remain limited to retrieved evidence.')
                break
            self.stage('discovering', f'Seeking original {kind} context for comparison and alternative explanations')
            before = {d.id for d in self.documents}
            hits = self.search(query, domains)
            self.ingest(hits[:1], time_reserve=self.analysis_reserve(), parse_limit=15, document_reserve=self.peer_document_reserve())
            self.context_searches.append({'kind': kind, 'query': query,
                                         'new_document_ids': list({d.id for d in self.documents} - before),
                                         'note': 'Retrieved context; numeric peer comparisons require separate verified bindings.'})

    def recover_issuer_identity(self):
        """Re-check authoritative website references when existing domains yield no facts."""
        if (self.facts or not self.company.isin
                or self.budget.search_calls >= self.budget.max_search_calls - 3
                or self.budget.fetch_documents >= self.budget.max_fetch_documents - 3
                or self.budget.remaining_seconds() <= self.time_reserve(180)):
            return
        self.stage('discovering', 'Checking authoritative issuer website references after financial retrieval failed')
        hits = self.search(f'"{self.company.legal_name}" "{self.company.isin}" website',
                           ['nseindia.com', 'bseindia.com'])
        before = set(self.company.verified_ir_domains)
        self.ingest(hits[:1], time_reserve=self.time_reserve(150), parse_limit=20, document_reserve=2)
        if set(self.company.verified_ir_domains) != before:
            self.stage('discovering', 'Seeking disclosures on the newly verified issuer website')
            hits = self.search(f'"{self.company.legal_name}" "financial results" {self.cutoff.year}',
                               self.company.verified_ir_domains)
            self.ingest(hits[:1], time_reserve=self.time_reserve(120), parse_limit=25, document_reserve=1)
            self.extract(limit=1)

    def recover_context(self, hypothesis, force=False):
        """Search original independent reports before giving up on a candidate."""
        if self.budget.search_calls >= self.budget.max_search_calls or self.budget.fetch_documents >= self.budget.max_fetch_documents or self.budget.remaining_seconds() <= self.time_reserve(120):
            return
        context_texts = [" ".join(p.text.lower() for p in self.passages if p.document_id == d.id)
                         for d in self.documents if d.document_type == "public_context" and d.cutoff_eligibility == "eligible"]
        identities = [self.company.legal_name, *self.company.aliases, *self.company.symbols]
        question = hypothesis.statement + ' ' + hypothesis.mechanism
        if not force and any(relevance(text, identities, question)[1] >= 2 for text in context_texts):
            return
        self.stage("discovering", "Searching original independent rating reports to corroborate the funding observation")
        domains = ["icra.in", "crisil.com", "crisilratings.com", "indiaratings.co.in", "fitchratings.com"]
        query = self.focused_query(hypothesis.next_query) + f' rating rationale {self.cutoff.year}'
        hits = self.search(query, domains)
        self.stage("fetching", "Retrieving independent rating reports within the remaining source budget")
        self.ingest(hits[:3], time_reserve=self.time_reserve(120), parse_limit=25)

    def challenge(self, hypothesis):
        payload = self.payload(hypothesis) | {"hypothesis": hypothesis.model_dump(mode="json"), "opposing_query": hypothesis.opposing_query}
        schema = create_model("Challenge", __base__=Challenge, relevant_passage_ids=(list[UUID], Field(max_length=8, json_schema_extra={"items": {
            "type": "string", "enum": [str(p["id"]) for p in payload['passages']]}})))
        result = self.calls.model(schema, payload, stage="challenging", instruction="Challenge the proposed mechanism using all evidence. Check every stated percentage against its specific registered calculation, input dates and scope; reject invented numbers and reversed arithmetic. Mark refuted if contradicted. Mark unresolved if scope, acquisitions, seasonality or missing evidence could explain the relationship. Select only directly relevant eligible source passage IDs. relevant_passage_ids must contain full IDs from the passages array only, never fact or calculation IDs. Distinguish a qualified arithmetic observation from an unproven causal mechanism; unresolved mechanism evidence does not refute reproducible arithmetic. Lack of search results does not establish absence of counterevidence. Retain only a qualified observation if the stronger inference fails. Assess novelty using the supplied original passages: identify the published explanation and describe the additional cross-metric or cross-source synthesis. Different headline wording is not novelty. Mark simple_restatement for ordinary reported results, already_covered if the relationship is already explained by the sources, and novelty_unknown when evidence is insufficient. historical_series describes observed coverage; two snapshots cannot establish onset, a sustained trend or causality.")
        self.challenge_reviews.append({'candidate': hypothesis.statement, 'proposed_falsification': hypothesis.falsification,
                                       'opposing_query': hypothesis.opposing_query, **result.model_dump(mode='json')})
        self.progress()
        return result

    def check_current_reconciliation(self, hypothesis):
        payload = self.payload(hypothesis)
        payload['question'] = 'Do original notes disclose acquired-balance run-off, merger bases or reclassification that explains the observed relationship?'
        review = self.calls.model(CurrentReconciliation, payload, stage='challenging',
            instruction='Check the question now against the retrieved source passages, including opposing search results. supported means a directly relevant structural reconciliation is actually disclosed; contradicted requires an explicit relevant denial/reconciliation ruling it out; not_found means neither is established. Absence of a keyword is not contradicted. Cite exact supplied original passage IDs; do not infer causality or invent a reconciliation.')
        allowed = {p['id'] for p in payload['passages']}
        if not set(review.passage_ids) <= allowed or (review.status != 'not_found' and not review.passage_ids):
            self.now_check = {'status': 'not_found', 'passage_ids': [], 'reason': 'Review could not bind a current reconciliation to exact original passages.'}
        else:
            self.now_check = review.model_dump(mode='json')
        if self.now_check['status'] == 'not_found':
            self.now_check['reason'] = 'No relevant reconciliation was established in the retrieved passages; absence is not proven.'
        self.now_check['searched_queries'] = list(self.opposing_queries)
        self.store.artifact(self.run_id, 'current_falsification_check', self.now_check)

    def angle_hypotheses(self, payload):
        from concurrent.futures import ThreadPoolExecutor, as_completed
        angles = route_angles(self.company, self.facts, self.calculations, [p.text for p in self.passages])
        self.store.artifact(self.run_id, 'angle_router', {'angles': angles, 'parallel_limit': 3})
        selected = [a for a in angles if a['coverage_groups'] == a['required_groups']]
        def investigate(angle):
            scoped = payload | {'research_angle': angle}
            batch = self.calls.model(cited_hypothesis_schema(scoped), scoped, stage='hypothesizing',
                instruction='Research only research_angle. Return at most one candidate with an additional quantified cross-metric or cross-source relationship, not a restatement of management narrative or headline results. Use one compatible reporting lane, supplied verified numbers and registered calculations only. Exclude growth-gap comparisons crossing structural_breaks; prefer post-break recovery. Read peer_benchmark and test whether this is only a sector story. Provide short supporting/opposing search fragments and an observable falsification test. No unsupported causal claims or invented numbers. Empty candidates are allowed when evidence is insufficient.')
            invalid = [h for h in batch.candidates if not supported_percentages(h.statement + ' ' + h.mechanism,
                [f for f in self.facts if f.id in h.fact_ids],
                [c for c in self.calculations if c.id in h.calculation_ids])]
            if invalid and self.budget.remaining_seconds() > 30:
                feedback = scoped | {'numerical_repair': {
                    'previous_candidates': [h.model_dump(mode='json') for h in invalid],
                    'allowed_percentages': [{'calculation_id': str(c.id), 'value': str(c.output_value), 'unit': c.unit}
                        for c in self.calculations if c.available and c.unit in {'percent', 'percentage_points'}],
                    'reason': 'One or more percentages lack an exact linked verified fact or registered calculation.'}}
                self.store.artifact(self.run_id, 'hypothesis_numeric_repair', {'angle': angle['key'], 'attempt': 1})
                batch = self.calls.model(cited_hypothesis_schema(scoped), feedback, stage='hypothesizing',
                    instruction='Repair only the unsupported numerical details of previous_candidates. Every percentage in statement AND mechanism must use its exact supplied verified ratio fact or registered calculation ID. Do not compute new percentages, differences, shares or thresholds in prose, and do not import percentages from unverified context. Remove unsupported numerical detail or return no candidate. Preserve reporting scope, period, definitions and an honestly qualified relationship. No new causal assertion. The repaired candidate must pass the same numerical, comparability, novelty, adversarial and final semantic gates; this is the only repair attempt.')
            return batch
        candidates, missing = [], []
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(investigate, a): a for a in selected[:3]}
            for future in as_completed(futures):
                try:
                    batch = future.result()
                    candidates.extend(batch.candidates)
                    missing.extend(batch.missing_evidence)
                except Exception as exc:
                    missing.append(f'Angle {futures[future]["key"]} did not complete: {type(exc).__name__}')
        unique = {(h.statement, tuple(h.calculation_ids)): h for h in candidates}
        if not selected:
            missing.append('At least two profile-native metric groups with source-bound facts for a routed Track A angle.')
        return HypothesisBatch(candidates=sorted(unique.values(), key=lambda h: h.significance + h.novelty, reverse=True)[:3], missing_evidence=[m[:200] for m in list(dict.fromkeys(missing))[:6]])

    def collect_quarters(self):
        targets = quarter_ends(self.cutoff)
        for year in sorted({d.year for d in targets}, reverse=True):
            if self.budget.remaining_seconds() <= self.analysis_reserve() or self.budget.search_calls >= self.budget.max_search_calls - 5:
                self.limitations.append('Quarterly retrieval stopped at its allowance; missing quarters remain unverified.')
                break
            dates = ' '.join(d.strftime('%B %Y') for d in targets if d.year == year)
            hits = self.search(self.focused_query(f'quarterly financial results investor presentation {dates}'), self.company.verified_ir_domains or None)
            before, revalidated = {d.id for d in self.documents}, set(self.revalidated_documents)
            self.ingest(hits[:2], time_reserve=self.analysis_reserve(), parse_limit=30, document_reserve=self.peer_document_reserve())
            self.extract(limit=2, historical=True, preferred_document_ids=({d.id for d in self.documents} - before) | (self.revalidated_documents - revalidated))
        verified = {f.period_end for f in self.facts}
        self.store.artifact(self.run_id, 'quarterly_coverage', {'requested': [str(d) for d in targets], 'missing': [str(d) for d in targets if d not in verified]})

    def collect_peer_benchmark(self, hypothesis):
        selected = set(hypothesis.fact_ids) | {i for c in self.calculations if c.id in hypothesis.calculation_ids for i in c.input_fact_ids}
        facts = [f for f in self.facts if f.id in selected]
        peers = select_peers(self.company, self.store.search_companies(''), self.company.business_profiles[0])
        from concurrent.futures import ThreadPoolExecutor, as_completed
        observations, bundles, errors = [], [], []
        def collect(peer):
            research = LiveResearch(self.machine, self.run_id, peer, self.cutoff, self.budget, settings=self.settings)
            research.peer_mode = True
            from signal_research.research.peers import peer_search_query
            scopes = {f.scope.value for f in facts}
            research.preferred_scope = next(iter(scopes)) if len(scopes) == 1 else None
            hits = research.search(peer_search_query(peer, facts), peer.verified_ir_domains or None)
            if not hits and self.budget.remaining_seconds() > self.time_reserve(180):
                hits = research.search(peer_search_query(peer, facts, broad=True), peer.verified_ir_domains or None)
            research.ingest(hits[:2], time_reserve=self.time_reserve(150), parse_limit=25)
            research.extract(limit=1, focus_metrics=tuple({f.metric_key for f in facts}))
            return research
        if self.budget.remaining_seconds() > self.time_reserve(180):
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = [pool.submit(collect, peer) for peer in peers.peers]
                for future in as_completed(futures):
                    try:
                        research = future.result()
                        observations.extend(research.facts)
                        bundles.append({'company': research.company.model_dump(mode='json'),
                            'facts': [f.model_dump(mode='json') for f in research.facts],
                            'passages': [p.model_dump(mode='json') for p in research.passages],
                            'documents': [d.model_dump(mode='json') for d in research.documents]})
                        errors.extend(research.limitations)
                    except Exception as exc:
                        errors.append('Peer evidence incomplete: ' + type(exc).__name__)
        else:
            errors.append('Peer collection deferred to preserve final review allowance.')
        self.peer_benchmark = compare_peers(facts, observations) | {'sources': bundles, 'limitations': errors}
        self.store.artifact(self.run_id, 'peer_benchmark', self.peer_benchmark)

    def run(self, plan):
        self.plan_questions = [task.query for task in plan]
        self.load_historical_cache()
        self.stage("discovering", "Searching issuer disclosures and independent sector, regulatory and peer context")
        initial = []
        # Round-robin domains and independent leads so issuer hits cannot consume the entire cap.
        queries = [(t.query, self.company.verified_ir_domains or None) for t in plan[:2]]
        if queries:
            # Locate the underlying disclosures before asking mechanism-specific questions.
            # A literal cutoff day in every query can hide otherwise eligible annual filings.
            queries[0] = (f'"{self.company.legal_name}" "financial results" {self.cutoff.year}', self.company.verified_ir_domains or None)
            if len(queries) > 1:
                queries[1] = (f'"{self.company.legal_name}" "investor presentation" {self.cutoff.year}', self.company.verified_ir_domains or None)
        profile = self.company.business_profiles[0]
        if not self.company.verified_ir_domains:
            # Identity evidence comes from the exchange, not a guessed web domain.
            identity_query = f'"{self.company.legal_name}" "{self.company.isin or self.company.symbols[0]}" website'
            identity_hits = self.search(identity_query, ['nseindia.com', 'bseindia.com'])
            self.ingest(identity_hits[:2], time_reserve=self.time_reserve(300), parse_limit=25)
            queries = [(query, self.company.verified_ir_domains or domains) for query, domains in queries]
        if queries and profile.value == "bank":
            queries[0] = (f'"{self.company.legal_name}" financial results standalone deposits advances {self.cutoff.year}', self.company.verified_ir_domains or None)
        regulator = "RBI" if profile.value in {"bank", "nbfc"} else "IRDAI" if "insurer" in profile.value else "SEBI"
        peers = select_peers(self.company, self.store.search_companies(""), profile)
        context_query = (f'"{self.company.legal_name}" "rating rationale" funding {self.cutoff.year}'
                         if profile.value in {'bank', 'nbfc'} else
                         f'"{self.company.legal_name}" {regulator} {CONTEXT_TERMS[profile]} sector context')
        queries += [(context_query, None)]
        self.store.artifact(self.run_id, "peer_selection", {"peers": [c.model_dump(mode="json") for c in peers.peers], "reasons": peers.reasons, "purpose": "independent context; peer values are not target facts"})
        if peers.peers:
            peer_names = " ".join(f'"{peer.legal_name}"' for peer in peers.peers)
            queries.append((f'"{self.company.legal_name}" {peer_names} {CONTEXT_TERMS[profile]} comparison {self.cutoff.year}', None))
        if self.company.isin or profile.value == "exchange":
            queries.insert(0, (exchange_results_query(self.company), ['nsearchives.nseindia.com']))
        initial = self.search_many(queries)
        hits = [items[i] for i in range(4) for items in initial if len(items) > i]
        if not any(any(domain_matches(urlparse(hit.url).hostname or "", domain)
                       for domain in self.company.verified_ir_domains) for hit in hits):
            hits = [*verified_disclosure_indexes(self.company), *hits]
        self.stage("fetching", "Retrieving original documents; search snippets remain leads")
        self.ingest(hits[:8], time_reserve=self.time_reserve(300), stop_when_balance_ready=profile.value == "bank", stop_when_financial_ready=True,
                    document_reserve=min(6, self.budget.max_fetch_documents // 3))
        if not self.issuer_financial_coverage():
            self.stage("discovering", "Following the issuer website navigation after search leads failed issuer identity checks")
            self.ingest(verified_disclosure_indexes(self.company), time_reserve=self.time_reserve(240),
                        stop_when_financial_ready=True, document_reserve=self.peer_document_reserve())
        if not self.issuer_financial_coverage():
            if self.budget.search_calls < self.budget.max_search_calls and self.budget.fetch_documents < self.budget.max_fetch_documents - 3:
                self.stage("discovering", "Seeking a dated exchange copy when issuer-portal leads lack usable disclosure dates")
                filing_hits = self.search(exchange_results_query(self.company) + ' "INTEGRATED FILING"',
                                          ['nsearchives.nseindia.com'], search_depth='advanced')
                self.stage("fetching", "Retrieving exchange disclosure leads; document identity and publication date still require verification")
                self.ingest(filing_hits[:3], time_reserve=self.time_reserve(240), stop_when_financial_ready=True, document_reserve=3)
        if not self.issuer_financial_coverage() and self.budget.search_calls < self.budget.max_search_calls:
            symbol = self.company.symbols[0]
            filing_hits = self.search(f'"{self.company.legal_name}" "{symbol}" "financial results"',
                                      ['nsearchives.nseindia.com', 'bseindia.com'])
            self.ingest(filing_hits[:3], time_reserve=self.time_reserve(240), document_reserve=3)
        if not self.issuer_financial_coverage():
            # Mechanism queries and combined result queries can return only undated
            # indexes. Spend the remaining bounded search allowance on a precise
            # filing lead before treating that retrieval gap as absent evidence.
            if self.budget.search_calls < self.budget.max_search_calls and self.budget.fetch_documents < self.budget.max_fetch_documents:
                annual_query = f'"{self.company.legal_name}" "annual report" {self.cutoff.year - 1} {self.cutoff.year}'
                self.stage("discovering", "Searching for a dated annual disclosure after initial issuer leads lacked verified publication dates")
                annual_hits = self.search(annual_query, self.company.verified_ir_domains or None)
                self.stage("fetching", "Retrieving the annual disclosure leads within the remaining document and time limits")
                self.ingest(annual_hits[:2], time_reserve=self.time_reserve(240), document_reserve=3)
        self.stage("extracting", "Extracting exact source spans and independently checking metric bindings")
        self.extract()
        if (not has_relationship_evidence(self.facts, self.calculations) and self.budget.search_calls < self.budget.max_search_calls
                and self.budget.fetch_documents < self.budget.max_fetch_documents - 1
                and self.budget.model_calls < self.budget.max_model_calls - 5
                and self.budget.remaining_seconds() > self.time_reserve(180)):
            # A press-release lead can have figures without unambiguous financial
            # scope or columns. Seek an original annual disclosure rather than
            # requiring both "standalone" and "consolidated" in a search result;
            # a valid statement can legitimately contain only one scope.
            self.stage("discovering", "Seeking financial statements after initial figures failed period or scope checks")
            query = f'"{self.company.legal_name}" "annual report" {self.cutoff.year - 1} {self.cutoff.year} filetype:pdf'
            hits = self.search(query, self.company.verified_ir_domains or None)
            self.stage("fetching", "Retrieving underlying statements within the remaining evidence budget")
            self.ingest(hits[:2], time_reserve=self.time_reserve(150), document_reserve=1)
            self.stage("extracting", "Checking newly retrieved statements without relaxing figure bindings")
            self.extract(limit=2)
        self.recover_issuer_identity()
        if not self.calculations:
            if not self.facts:
                eligible_issuer = any(d.document_type.startswith("issuer") and d.cutoff_eligibility == "eligible" for d in self.documents)
                requirement = "verified issuer facts with complete metric, value, period, unit and scope bindings" if eligible_issuer else "an accessible official financial disclosure with verified issuer identity and reporting periods"
                return self.abstain([requirement])
            return self.abstain(["comparable verified facts for a relevant registered calculation"])
        self.collect_operating_metrics()
        self.collect_quarters()
        self.collect_history()
        self.collect_sector_context(peers)
        self.structural_breaks = detect_breaks(self.facts, self.passages, self.documents)
        if any(b['status'].startswith('suspected') for b in self.structural_breaks) and self.budget.remaining_seconds() > self.analysis_reserve():
            event_hits = self.search(self.focused_query('merger amalgamation acquisition scheme of arrangement reclassification restatement filings'), self.company.verified_ir_domains or None)
            self.ingest(event_hits[:2], time_reserve=self.analysis_reserve(), parse_limit=15, document_reserve=self.peer_document_reserve())
            self.structural_breaks = detect_breaks(self.facts, self.passages, self.documents)
        self.store.artifact(self.run_id, 'structural_breaks', {'events': self.structural_breaks})
        self.calculations.extend(c for c in recovery_calculations(self.facts, self.structural_breaks) if c.id not in {v.id for v in self.calculations})
        if not self.calculations:
            return self.abstain(['comparable verified arithmetic after historical-source reconciliation'])
        self.stage("hypothesizing", "Generating and ranking observation-led mechanisms within comparable reporting boundaries")
        payload = self.payload(compact=True)
        batch = self.angle_hypotheses(payload)
        self.store.artifact(self.run_id, "hypotheses", batch.model_dump(mode="json"))
        report = self.investigate_candidates(batch)
        if report:
            return report
        # A failed first angle should produce a bounded research revision rather
        # than an immediate blank discovery. Never retry a stale or refuted thesis
        # merely to obtain a more agreeable verdict.
        revisable = any(d['disposition'] in {'simple_restatement', 'already_covered', 'novelty_unknown', 'withheld'}
                        for d in self.decisions)
        if (revisable and self.budget.search_calls < self.budget.max_search_calls - 4
                and self.budget.fetch_documents < self.budget.max_fetch_documents - 3
                and self.budget.model_calls < self.budget.max_model_calls - 8
                and self.budget.remaining_seconds() > self.time_reserve(240)):
            self.stage('discovering', 'Revising the research angle after the first candidates failed; seeking missing disclosures')
            missing = ' '.join(batch.missing_evidence[:2])[:220]
            query = self.focused_query(missing or CONTEXT_TERMS[self.company.business_profiles[0]]) + ' annual report notes disclosure'
            before = {p.id for p in self.passages}
            hits = self.search(query, self.company.verified_ir_domains or None)
            self.ingest(hits[:2], time_reserve=self.time_reserve(180), parse_limit=25, document_reserve=2)
            if {p.id for p in self.passages} - before:
                self.extract(limit=3, historical=True)
                if self.calculations:
                    revised_payload = self.payload(compact=True) | {'rejected_candidates': self.decisions,
                                                        'challenge_reviews': self.challenge_reviews}
                    self.stage('hypothesizing', 'Testing a revised angle against the expanded evidence and earlier objections')
                    revised = self.calls.model(cited_hypothesis_schema(revised_payload), revised_payload, stage="hypothesizing",
                        instruction='Propose up to three NEW defensible relationships from the expanded verified evidence. Do not repeat rejected candidates or relabel a refuted mechanism. Use one compatible_research_lane, exact registered arithmetic and supplied IDs. Introduce no unverified numbers in the statement or mechanism. Seek a non-obvious cross-metric relationship beyond reported results. Give targeted supporting and opposing search fragments and an observable proposed falsification test. Return no candidates rather than inventing a discovery.')
                    self.store.artifact(self.run_id, 'revised_hypotheses', revised.model_dump(mode='json'))
                    report = self.investigate_candidates(revised)
                    if report:
                        return report
        return self.abstain(batch.missing_evidence or ['a discovery that survives counterevidence and semantic verification'])

    def investigate_candidates(self, batch):
        facts = {f.id for f in self.facts}
        calculations = {c.id for c in self.calculations}
        candidates = sorted([h for h in batch.candidates if set(h.fact_ids) <= facts and set(h.calculation_ids) <= calculations], key=lambda h: h.significance + h.novelty, reverse=True)
        candidate_cap = 3 if self.store.get_summary(self.run_id).mode.value == "deep" else 2
        investigated = 0
        for hypothesis in candidates:
            if not self.current_candidate(hypothesis):
                continue
            hypothesis = hypothesis.model_copy(update={"calculation_ids": complete_calculation_lineage(
                hypothesis.statement + ' ' + hypothesis.mechanism, hypothesis.fact_ids,
                hypothesis.calculation_ids, self.calculations)})
            compatible, reason = compatible_candidate(hypothesis, self.facts, self.calculations)
            if not compatible:
                self.record_decision(hypothesis, 'incomparable', reason)
                self.limitations.append(reason)
                continue
            cited_facts = [f for f in self.facts if f.id in hypothesis.fact_ids]
            cited_calcs = [c for c in self.calculations if c.id in hypothesis.calculation_ids]
            if not supported_percentages(hypothesis.statement + ' ' + hypothesis.mechanism, cited_facts, cited_calcs):
                self.record_decision(hypothesis, 'withheld', 'A numerical claim lacks linked verified inputs.')
                self.limitations.append("Candidate contained a percentage absent from its linked verified facts/calculations; candidate withheld before further retrieval.")
                continue
            if classify_novelty(hypothesis.statement, self.source_titles) == Novelty.ALREADY_COVERED:
                self.record_decision(hypothesis, 'already_covered', 'The candidate repeats a discovered source headline.')
                self.limitations.append("Candidate repeats an existing source headline; seeking additional synthesis.")
                continue
            # Invalid high-ranked candidates must not consume the investigation cap.
            if investigated >= candidate_cap:
                self.record_decision(hypothesis, 'not_investigated', 'The bounded investigation allowance was used by other valid candidates.')
                continue
            iteration = investigated
            investigated += 1
            self.collect_peer_benchmark(hypothesis)
            self.stage("investigating", f"Following candidate {iteration + 1} with a targeted evidence query")
            followup = self.search(self.focused_query(hypothesis.next_query))
            opposing = self.search(self.focused_query(hypothesis.opposing_query), opposing=True)
            self.stage("fetching", "Retrieving targeted supporting and opposing sources")
            previous_documents = {d.id for d in self.documents}
            previously_revalidated = set(self.revalidated_documents)
            self.ingest([*opposing[:3], *followup[:3]], time_reserve=self.time_reserve(120), parse_limit=25)
            self.extract(limit=1, preferred_document_ids=({d.id for d in self.documents} - previous_documents) | (self.revalidated_documents - previously_revalidated))
            if not self.current_candidate(hypothesis):
                continue
            self.recover_context(hypothesis)
            response_allowance = min(self.settings.max_model_output_tokens_per_call,
                self.settings.stage_output_tokens.get('challenging', self.settings.max_model_output_tokens_per_call))
            can_parallel_review = self.budget.max_output_tokens - self.budget.output_tokens >= response_allowance * 2
            if can_parallel_review:
                self.stage("challenging", "Checking current reconciliations and the strongest alternative in parallel")
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=2) as pool:
                    reconciliation = pool.submit(self.check_current_reconciliation, hypothesis)
                    adversarial = pool.submit(self.challenge, hypothesis)
                    reconciliation.result()
                    challenge = adversarial.result()
            else:
                # Preserve full response allowances when a small run budget
                # cannot reserve both independent checks at once.
                self.check_current_reconciliation(hypothesis)
                self.stage("challenging", "Testing the strongest alternative against the verified evidence")
                challenge = self.challenge(hypothesis)
            self.store.artifact(self.run_id, "challenge", challenge.model_dump(mode="json"))
            self.progress(iteration + 1)
            if challenge.refuted:
                self.record_decision(hypothesis, 'refuted', challenge.reason, challenge.relevant_passage_ids)
                self.limitations.append(f"Candidate rejected: {challenge.reason}")
                continue
            relevant = [p for p in self.passages if p.id in challenge.relevant_passage_ids]
            origins = {d.origin_family_id for d in self.documents if d.cutoff_eligibility == "eligible" and d.id in {p.document_id for p in relevant}}
            if len(origins) < 2:
                if self.budget.remaining_seconds() < self.time_reserve(120):
                    self.limitations.append("Independent corroboration remains incomplete; additional retrieval was stopped at the remaining time limit.")
                    self.limitations.append('Only a source-observed or reproducible non-causal Weak finding can publish without independent corroboration.')
                before = len(self.documents)
                self.recover_context(hypothesis, force=True)
                if len(self.documents) > before:
                    self.stage("challenging", "Checking the candidate against newly retrieved independent rating evidence")
                    challenge = self.challenge(hypothesis)
                    self.store.artifact(self.run_id, "challenge", challenge.model_dump(mode="json"))
                    relevant = [p for p in self.passages if p.id in challenge.relevant_passage_ids]
                    origins = {d.origin_family_id for d in self.documents if d.cutoff_eligibility == "eligible" and d.id in {p.document_id for p in relevant}}
                if challenge.refuted:
                    self.record_decision(hypothesis, 'refuted', challenge.reason, challenge.relevant_passage_ids)
                    continue
                if len(origins) < 2:
                    self.limitations.append('Independent corroboration is incomplete; publication is limited to a verified non-causal Weak observation.')
            if challenge.novelty_status != 'additional_supported_synthesis' or not challenge.novelty_rationale:
                self.record_decision(hypothesis, challenge.novelty_status, challenge.novelty_rationale or 'Additional synthesis was not established.', challenge.relevant_passage_ids)
                self.limitations.append('Candidate did not establish additional supported synthesis beyond reported results or published explanations.')
                continue
            self.stage("composing", "Drafting all eight required discovery fields from verified artifacts")
            draft_payload = self.payload(hypothesis, challenge.relevant_passage_ids) | {"hypothesis": hypothesis.model_dump(mode="json"), "challenge": challenge.model_dump(mode="json")}
            draft = self.calls.model(cited_draft_schema(draft_payload), draft_payload, stage="composing", instruction="Write exactly one plain-English, qualified discovery sentence of at most 35 words, naming the entity, the change, one or two verified key numbers with units, and the observed time span; then 3–5 significance statements and the strongest counterargument. timeline_analysis must explain when the relationship first appears in the verified observations and how it developed, citing its actual fact/passage/calculation IDs. Distinguish a bounded observation window from true onset. Set onset_status=unknown and explicitly say onset is not established if only two snapshots or no evidence of emergence exists; never claim a multi-year trend from two endpoints. Every factual statement must cite supplied supporting fact/passage IDs and calculation IDs where numerical. Use full IDs verbatim from the corresponding facts, passages and calculations arrays. Every inferred headline or significance claim needs directly relevant support from at least two independent origin families. With fewer origins, use only source-observed or reproducibly derived claims and disclose that independent corroboration is missing; exchange reposts of issuer material are the same origin. Pure reported figures may use primary source facts. Include independently originated relevant context. State an observable future condition identifying the metric or event, comparison direction, observation window and expected source that would falsify the relationship, with no invented historical numbers or arbitrary numeric threshold. Use the challenged qualification. No investment advice.")
            report = self.compose(draft, challenge, hypothesis.opposing_query)
            if report:
                return report
            # Repair a specific unsupported qualification or observable test only
            # after novelty survived review. Rewording cannot rescue failed novelty.
            if (self.draft_feedback and self.draft_feedback.get('repairable')
                    and self.budget.remaining_seconds() > 180
                    and self.budget.model_calls < self.budget.max_model_calls - 2):
                self.stage('composing', 'Correcting the rejected draft against its independent review; publication still requires a fresh review')
                repair_payload = draft_payload | {'rejected_draft': draft.model_dump(mode='json'),
                                                  'independent_review': self.draft_feedback}
                revised_draft = self.calls.model(cited_draft_schema(repair_payload), repair_payload, stage='composing',
                    instruction='Correct ONLY the specifically unsupported claims or falsification details identified by independent_review (which identifies whether feedback comes from local numerical gates or independent semantic review). Use existing cited verified facts, calculations and source passages. Do not change the approved novelty assessment, invent new facts or claim a historical onset beyond the observations. Keep a qualified one-sentence discovery, 3–5 independently supported significance statements, linked timeline_analysis with honest onset_status, strongest counterargument, and an observable falsification condition with a concrete window and source. Every percentage must link its exact registered calculation or verified ratio fact. The entire result will undergo a new independent review. No investment advice.')
                report = self.compose(revised_draft, challenge, hypothesis.opposing_query)
                if report:
                    return report
            self.record_decision(hypothesis, 'withheld', 'The drafted conclusion failed independent final verification.', challenge.relevant_passage_ids)
        return None

    def compose(self, draft, challenge, opposing_query):
        self.draft_feedback = None
        blocked = break_calculations(self.structural_breaks, self.calculations)
        if set(draft.headline.calculation_ids) & blocked and not set(draft.headline.calculation_ids) - blocked:
            self.limitations.append('Headline growth crosses an unresolved structural break; use a verified post-break relationship instead.')
            return None
        draft = draft.model_copy(update={
            'headline': draft.headline.model_copy(update={'text': format_prose(draft.headline.text)}),
            'why_it_matters': [s.model_copy(update={'text': format_prose(s.text)}) for s in draft.why_it_matters],
            'timeline_analysis': draft.timeline_analysis.model_copy(update={'text': format_prose(draft.timeline_analysis.text)}),
            'counterargument': draft.counterargument.model_copy(update={'text': format_prose(draft.counterargument.text)}),
            'falsification': format_prose(draft.falsification)})
        if set(draft.headline.calculation_ids) & blocked and not set(draft.headline.calculation_ids) - blocked:
            self.limitations.append('Headline growth crosses an unresolved structural break; use a verified post-break relationship instead.')
            return None
        facts, passages, calculations = {f.id: f for f in self.facts}, {p.id: p for p in self.passages}, {c.id: c for c in self.calculations}
        current_check = ([Statement(text=format_prose(self.now_check['reason']), kind=ClaimKind.OBSERVED,
            fact_ids=draft.headline.fact_ids, calculation_ids=draft.headline.calculation_ids,
            passage_ids=self.now_check['passage_ids'])] if self.now_check['status'] in {'supported', 'contradicted'} else [])
        statements = [draft.headline, *draft.why_it_matters, draft.timeline_analysis, *current_check, draft.counterargument]
        finding_boundary = draft.headline.model_copy(update={
            'fact_ids': list({identifier for statement in statements for identifier in statement.fact_ids}),
            'calculation_ids': list({identifier for statement in statements for identifier in statement.calculation_ids}),
        })
        compatible, reason = compatible_candidate(finding_boundary, self.facts, self.calculations)
        if not compatible:
            self.limitations.append('The discovery and its timeline/significance use incompatible reporting boundaries. ' + reason)
            return None
        claims = []
        for statement in statements:
            statement = statement.model_copy(update={'calculation_ids': complete_calculation_lineage(
                statement.text, statement.fact_ids, statement.calculation_ids, self.calculations)})
            if not (statement.fact_ids or statement.calculation_ids):
                self.limitations.append('A financial statement lacked a verified fact or calculation anchor; source-only prose was withheld.')
                return None
            if not set(statement.fact_ids) <= facts.keys() or not set(statement.passage_ids) <= passages.keys() or not set(statement.calculation_ids) <= calculations.keys() or not (statement.fact_ids or statement.passage_ids):
                self.limitations.append("Draft referenced missing evidence and was withheld.")
                return None
            bound_facts = [facts[i] for i in statement.fact_ids]
            bound_calcs = [calculations[i] for i in statement.calculation_ids]
            if not supported_percentages(statement.text, bound_facts, bound_calcs) or not supported_numbers(statement.text, bound_facts, bound_calcs):
                self.draft_feedback = {'repairable': True, 'validation_stage': 'local_numerical_gates',
                    'rejected_statement': statement.text,
                    'reason': 'Remove every financial number absent from this statement’s linked verified facts/calculations. A number quoted in context is not a verified fact. Preserve the supported relationship and all material qualifications; do not replace missing figures with estimates.',
                    'allowed_fact_ids': [str(f.id) for f in bound_facts],
                    'allowed_calculation_ids': [str(c.id) for c in bound_calcs]}
                self.limitations.append('Draft introduced numerical detail without its own linked verified inputs; publication withheld pending a fresh corrected draft and independent review.')
                return None
            compatible, reason = compatible_candidate(statement, self.facts, self.calculations)
            if not compatible:
                self.limitations.append(reason)
                return None
            identifier = uuid5(self.run_id, f"claim:{len(claims)}:{statement.text}")
            claims.append(Claim(id=identifier, run_id=self.run_id, text=statement.text, kind=statement.kind,
                                evidence_links=[EvidenceLink(claim_id=identifier, passage_or_fact_id=i, relation=EvidenceRelation.SUPPORTING, reason="Reviewed source support") for i in [*statement.fact_ids, *statement.passage_ids]], calculation_ids=statement.calculation_ids))
        review = self.calls.model(semantic_review_schema([claim.id for claim in claims]), self.payload(finding_boundary.model_copy(update={"calculation_ids": list({i for c in claims for i in c.calculation_ids})}), required_passage_ids={identifier for statement in statements for identifier in statement.passage_ids}) | {"claims": [c.model_dump(mode="json") for c in claims], "falsification": draft.falsification, "observation_window": draft.falsification_window, "expected_source": draft.falsification_source, "novelty_assessment": challenge.model_dump(mode="json")}, stage="verifying", instruction="Independently verify every claim against ONLY its linked source passages/facts and registered calculations. Check all numbers and qualifiers, metric/date/scope binding, causal overreach and context relevance. Inferred claims must remain qualified. Every supporting link must be relevant and entail the claim in combination. Reject unsupported detail even when a citation ID exists. Return exactly one verdict per claim ID with no duplicates or omissions. Ensure falsification identifies an observable metric or event, comparison direction, concrete observation window and expected source, follows from the relationship, and uses no fabricated historical facts. Independently assess non_obvious_synthesis_supported: ordinary growth summaries, mere headline rewording, and unsupported causal mechanisms do not qualify. Compare the supplied novelty assessment with its linked evidence, and reject historical development claims beyond the observed series. Detect investment recommendations.")
        verdicts = {v.claim_id: v for v in review.verdicts}
        complete_review = len(review.verdicts) == len(claims) and set(verdicts) == {c.id for c in claims}
        self.store.artifact(self.run_id, 'semantic_review', {'claims': [c.model_dump(mode='json') for c in claims],
                                                         'review': review.model_dump(mode='json')})
        if len(review.verdicts) != len(claims) or set(verdicts) != {c.id for c in claims} or review.contains_investment_recommendation or not review.non_obvious_synthesis_supported or not review.falsification_is_observable or any(c.id not in verdicts or not verdicts[c.id].supported for c in claims):
            self.draft_feedback = {'repairable': complete_review and review.non_obvious_synthesis_supported,
                                   **review.model_dump(mode='json')}
            reasons = '; '.join(v.reason for v in review.verdicts if not v.supported)[:600]
            self.limitations.append('Independent semantic review rejected a material statement; candidate withheld.' + (f' Reasons: {reasons}' if reasons else ''))
            return None
        for claim in claims:
            claim.verification_status = VerificationStatus.SUPPORTED
            claim.verification_reasons = [verdicts[claim.id].reason]
        used_calcs = set().union(*(set(c.calculation_ids) for c in claims))
        if not used_calcs:
            return None
        used_facts = set().union(*(set(c.input_fact_ids) for c in self.calculations if c.id in used_calcs))
        used_facts |= {l.passage_or_fact_id for c in claims for l in c.evidence_links if l.passage_or_fact_id in facts}
        used_passages = {facts[i].passage_id for i in used_facts} | {l.passage_or_fact_id for c in claims for l in c.evidence_links if l.passage_or_fact_id in passages}
        used_docs = {passages[i].document_id for i in used_passages}
        documents = [d for d in self.documents if d.id in used_docs]
        if len({f.period_end for f in self.facts if f.id in used_facts}) < 2:
            self.limitations.append("Candidate lacked comparable multi-period evidence; candidate withheld.")
            return None
        from signal_research.evidence.claim_origins import supporting_origins
        if any(c.kind == ClaimKind.INFERRED and len(supporting_origins(c, facts, passages, {d.id: d for d in documents})) < 2
               for c in claims[:-1]):
            self.limitations.append("A material inferred claim lacked independent supporting origins; candidate withheld.")
            return None
        if len(supporting_origins(claims[0], facts, passages, {d.id: d for d in documents})) < (2 if claims[0].kind == ClaimKind.INFERRED else 1):
            self.limitations.append("Headline lacked independently originated supporting evidence; candidate withheld.")
            return None
        origins = {d.origin_family_id for d in documents if d.cutoff_eligibility == "eligible"}
        if not origins or any(d.cutoff_eligibility != "eligible" for d in documents) or not any(d.document_type.startswith("issuer") for d in documents):
            return None
        timeline = [TimelineEvent(id=uuid4(), event_date=f.period_end, date_precision=DatePrecision.DAY,
                                 published_at=next(d.published_at for d in documents if d.id == passages[f.passage_id].document_id),
                                 description=f"{f.metric_key}: {f.value_decimal} {f.unit_normalized} ({f.scope.value})", claim_ids=[c.id for c in claims if any(l.passage_or_fact_id == f.id for l in c.evidence_links)], source_ids=[passages[f.passage_id].document_id]) for f in self.facts if f.id in used_facts]
        rule = FalsificationRule(id=uuid4(), observable_metric_or_event=draft.falsification, operator="observable condition", expected_source_type=draft.falsification_source, interpretation=f"{draft.falsification} Observation window: {draft.falsification_window}", dependencies=list(used_calcs))
        strength = EvidenceStrength.WEAK if challenge.unresolved else EvidenceStrength.STRONG if len(origins) >= 3 else EvidenceStrength.MODERATE
        unknown_publication = sum(d.published_at is None for d in documents)
        if unknown_publication and strength == EvidenceStrength.STRONG:
            strength = EvidenceStrength.MODERATE
        discovery = Discovery(id=uuid4(), discovery_sentence=claims[0].text,
                              why_it_matters=[WhyItMatters(text=c.text, claim_id=c.id) for c in claims[1:1 + len(draft.why_it_matters)]], evidence_claim_ids=[c.id for c in claims],
                              timeline_event_ids=[e.id for e in timeline], calculation_ids=list(used_calcs),
                              counterargument=Counterargument(statement=claims[-1].text, evidence_claim_ids=[claims[-1].id], search_attempted=True, search_summary=f"Searched: {opposing_query}. {challenge.reason}", unresolved=challenge.unresolved),
                              falsification_rules=[rule], evidence_strength=strength,
                              strength_rationale=f"{len(origins)} relevant origin families; registered calculations independently reproduced; " + ("the strongest alternative remains unresolved." if challenge.unresolved else "the tested alternative did not refute the qualified relationship.") +
                              (f" Original publication dates are unknown for {unknown_publication} sources; their current availability is verified by retrieval receipts." if unknown_publication else ""))
        report = ResearchReport(run_id=self.run_id, company=self.company, cutoff=self.cutoff,
                            historical_coverage=" / ".join(sorted({str(f.period_end) for f in self.facts if f.id in used_facts})),
                            source_coverage={"mode": "live", "synthetic": False, "documents_found": len(self.documents), "documents_used": len(documents), "eligible_origin_families": len(origins), "primary_source": True},
                            outcome=ResearchOutcome.DISCOVERY, publication_status=PublicationStatus.PUBLISHED, discoveries=[discovery], limitations=self.limitations,
                            generation_metadata={"pipeline": "extract-bind-calculate-hypothesize-investigate-challenge-review-v2", **self.model_metadata(), "search_queries": self.queries, "research_decisions": self.decisions, "challenge_reviews": self.challenge_reviews, "opposing_queries": self.opposing_queries, "context_searches": self.context_searches, "novelty_status": challenge.novelty_status, "novelty_rationale": challenge.novelty_rationale, "published_explanation": challenge.published_explanation, "non_obvious_synthesis_reviewed": review.non_obvious_synthesis_supported},
                            claims=claims, timeline_events=sorted(timeline, key=lambda e: (str(e.event_date), e.description)), calculations=self.calculations, facts=self.facts, passages=self.passages, documents=self.documents)
        report.source_coverage['historical_series'] = comparable_series(self.facts)
        report.generation_metadata['temporal_reasoning'] = {'text': draft.timeline_analysis.text,
                                                          'claim_id': claims[1 + len(draft.why_it_matters)].id,
                                                          'onset_status': draft.onset_status}
        report.generation_metadata['historical_cache'] = self.history_cache
        reused_ids = {identifier for entry in self.history_cache for identifier in entry['fact_ids']}
        report.generation_metadata['cache_usage'] = {'cold_start': self.settings.cold_start, 'reused': sum(str(f.id) in reused_ids for f in self.facts), 'fresh': sum(str(f.id) not in reused_ids for f in self.facts)}
        report.generation_metadata['structural_breaks'] = self.structural_breaks
        report.generation_metadata['peer_benchmark'] = self.peer_benchmark
        report.generation_metadata['submission_checklist'] = submission_checklist(report)
        if not any(c.id in used_calcs and c.id not in break_calculations(self.structural_breaks, self.calculations)
                   for c in self.calculations):
            self.limitations.append('No verified calculation outside the flagged break interval can support a short headline.')
            return None
        self.write_plain_headline(report)
        peer_done = self.peer_benchmark.get('status') == 'verified'
        supporting_passages = {p.id: p for p in self.passages}
        supporting_docs = {d.id: d for d in self.documents}
        issuer_only = all(supporting_docs[supporting_passages[f.passage_id].document_id].origin_family_id.startswith('issuer:') for f in self.facts)
        strength, trace = evidence_tier(origin_families=origins,
            non_issuer=any(not d.origin_family_id.startswith('issuer:') for d in documents),
            peer_comparison_done=peer_done, unresolved_break=bool(self.structural_breaks) and self.now_check['status'] != 'contradicted',
            counterargument_searched=bool(self.opposing_queries), counterargument_addressed=not challenge.unresolved,
            issuer_only_facts=issuer_only)
        discovery.evidence_strength = strength
        discovery.strength_rationale = 'Evidence tier follows the displayed origin, peer, structural-break and counterargument rules.'
        report.generation_metadata['strength_trace'] = trace
        report.generation_metadata['tiered_publication'] = True
        if len(origins) < 2 and not peer_done:
            discovery.evidence_strength = EvidenceStrength.WEAK
            trace['rating'] = 'Weak'
            trace['caps'].append('Only primary-origin arithmetic was corroborated: non-causal Weak observation only.')
        report.generation_metadata['falsification_tests'] = observable_tests(self.facts, [c for c in self.calculations if c.id in used_calcs], self.passages, self.documents, self.cutoff, self.now_check)
        if current_check:
            report.generation_metadata['falsification_tests']['conditions'][-1]['claim_id'] = str(claims[-2].id)
        report.generation_metadata['timeline_story'] = timeline_story(self.facts, self.calculations, self.passages, self.documents, self.structural_breaks)
        return attest_report(report)

    def write_plain_headline(self, report):
        discovery = report.discoveries[0]
        technical = next(c for c in report.claims if c.text == discovery.discovery_sentence)
        blocked = break_calculations(self.structural_breaks, report.calculations)
        selected = [c for c in report.calculations if c.id in technical.calculation_ids
                    and c.id not in blocked]
        if not selected:
            selected = [c for c in report.calculations if c.id in discovery.calculation_ids
                        and c.id not in blocked]
        selected_facts = [f for f in report.facts if f.id in {i for c in selected for i in c.input_fact_ids}
                          or f.id in {link.passage_or_fact_id for link in technical.evidence_links}]
        if (technical.verification_status == VerificationStatus.SUPPORTED
                and not set(technical.calculation_ids) & blocked
                and not validate_headline(technical.text, report.company.legal_name, selected_facts, selected)):
            # Identical text and lineage already passed the independent semantic
            # review; a second writer and entailment review add no new evidence.
            report.generation_metadata['headline'] = {
                'technical_detail': technical.text, 'technical_claim_id': str(technical.id),
                'claim_id': str(technical.id), 'method': 'already_reviewed_headline', 'validation_errors': []}
            return
        fallback, fallback_calc = template_headline(report.company, selected_facts, selected)
        text, method = fallback, 'verified_arithmetic_template'
        errors = []
        from signal_research.domain.errors import BudgetExceeded
        from signal_research.providers.llm.codecraft_provider import CodeCraftError
        from signal_research.providers.llm.nvidia_provider import NvidiaRequestError
        for attempt in range(3):
            if self.budget.remaining_seconds() < 12:
                break
            try:
                response = self.calls.model(PlainHeadline, {'entity': report.company.legal_name, 'technical_detail': technical.text,
                    'facts': [f.model_dump(mode='json') for f in selected_facts],
                    'calculations': [calculation_context(c, selected_facts) for c in selected], 'errors': errors, 'attempt': attempt},
                    stage='verifying', instruction='Rewrite the already reviewed finding as exactly one plain-English sentence of at most 35 words. Name the entity, the change, one or two key numbers with units, and the observed time span. No jargon or unsupported causality. Use only supplied verified numbers; preserve signs and definitions. Do not lead with a structural-break interval.')
                response.sentence = format_prose(response.sentence)
                errors = validate_headline(response.sentence, report.company.legal_name, selected_facts, selected)
                if errors:
                    continue
                reviewed = self.calls.model(fact_review_schema(1), {'source_text': technical.text,
                    'candidates': [{'index': 0, 'text': response.sentence}]}, stage='verifying',
                    instruction='Check that candidate 0 is fully entailed by the already verified source_text, including its time span, numbers, comparison direction, units and qualifications. Reject new causal claims or removal of material uncertainty. Return one verdict for index 0.')
                if len(reviewed.verdicts) == 1 and reviewed.verdicts[0].index == 0 and reviewed.verdicts[0].supported:
                    text, method = response.sentence, 'independently_reviewed_writer'
                    break
                errors = ['Rewrite was not entailed by the verified technical detail.']
            except (BudgetExceeded, CodeCraftError, NvidiaRequestError):
                break
        if validate_headline(text, report.company.legal_name, selected_facts, selected):
            raise ValueError('No valid source-bound headline could be produced.')
        claim = technical.model_copy(update={'id': uuid5(self.run_id, 'plain-headline:' + text), 'text': text})
        claim.calculation_ids = [c.id for c in selected]
        claim.evidence_links = [link.model_copy(update={'claim_id': claim.id}) for link in claim.evidence_links]
        if method == 'verified_arithmetic_template':
            claim.calculation_ids = [fallback_calc.id]
            claim.kind = ClaimKind.DERIVED
        report.claims.append(claim)
        discovery.discovery_sentence = text
        discovery.evidence_claim_ids.append(claim.id)
        report.generation_metadata['headline'] = {'technical_detail': technical.text, 'technical_claim_id': str(technical.id),
            'claim_id': str(claim.id), 'method': method, 'validation_errors': errors}
