from __future__ import annotations

import re
from dataclasses import asdict
from datetime import UTC, datetime
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
from signal_research.extraction.bank_tables import (
    comparative_bank_batch,
    month_end_columns,
    scope_in_text,
    subsidiary_only,
)
from signal_research.extraction.dates import (
    declared_duration_periods,
    explicit_duration_ranges,
    source_dates,
)
from signal_research.extraction.financial_tables import financial_table_batch
from signal_research.extraction.models import ExtractedFactBatch, source_fact_batch_schema
from signal_research.extraction.validate import validate_candidate
from signal_research.finance.calculations import calculate, numeric_fact
from signal_research.finance.registry import metrics_for_profile
from signal_research.research.calculation_context import calculation_context
from signal_research.research.context import diverse_context, exact_excerpt, relevance
from signal_research.research.history import (
    comparable_series,
    has_relationship_evidence,
    needs_history,
)
from signal_research.research.identity import (
    foreign_cover_identity,
    identity_aliases,
    issuer_cover_identity,
    issuer_named,
    issuer_symbol_reference,
)
from signal_research.research.integrity import attest_report
from signal_research.research.novelty import Novelty, classify_novelty
from signal_research.research.numeric_claims import (
    complete_calculation_lineage,
    supported_percentages,
)
from signal_research.research.peer_selector import select_peers
from signal_research.research.report_builder import build_abstention
from signal_research.research.sector import CONTEXT_TERMS, extraction_instruction
from signal_research.retrieval.disclosures import (
    embedded_disclosures,
    issuer_navigation,
    linked_disclosures,
    verified_disclosure_indexes,
)
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
    falsification: str = Field(max_length=500)
    falsification_window: str = Field(min_length=5, max_length=300)
    falsification_source: str = Field(min_length=5, max_length=300)


def cited_draft_schema(payload):
    """Give the provider an explicit choice of existing evidence identifiers."""
    limits = {'fact_ids': 8, 'passage_ids': 6, 'calculation_ids': 6}
    fields = {name: (list[UUID], Field(max_length=limits[name], json_schema_extra={"items": {
        "type": "string", "enum": [str(item["id"]) for item in payload[source]]}}))
        for name, source in (("fact_ids", "facts"), ("passage_ids", "passages"), ("calculation_ids", "calculations"))}
    statement = create_model("CitedStatement", __base__=Statement, **fields)
    return create_model("DiscoveryDraft", __base__=DiscoveryDraft, headline=(statement, ...),
        counterargument=(statement, ...), why_it_matters=(list[statement], Field(min_length=3, max_length=5)))


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
                                       comparability_checks=result.comparability_checks))
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
    return results


class LiveResearch:
    def __init__(self, machine, run_id, company, cutoff, budget):
        self.machine, self.store, self.settings = machine, machine.store, machine.settings
        self.run_id, self.company, self.cutoff, self.budget = run_id, company, cutoff, budget
        self.calls = DurableCalls(self.store, self.settings, run_id, budget)
        self.documents, self.passages, self.facts, self.calculations = [], [], [], []
        self.seen_urls, self.extracted, self.queries, self.limitations = set(), set(), [], []
        self.source_titles = []
        self.evidence_iteration = 0
        self.decisions = []

    def time_reserve(self, seconds):
        """Scale stage allowances to the configured total research deadline."""
        return min(seconds, self.settings.max_run_seconds * seconds / 900)

    def stage(self, status, summary):
        from signal_research.domain.enums import RunStatus
        self.machine._set_stage(self.run_id, RunStatus(status), f"live_{status}", summary)

    def search(self, query, domains=None, opposing=False):
        self.queries.append(query)
        hits = self.calls.search(query, domains, self.cutoff, "challenging" if opposing else "discovering")
        self.source_titles.extend(hit.title for hit in hits if hit.title)
        # Search metadata ranks retrieval leads only. It never verifies issuer
        # identity, a publication date or a financial figure.
        financial_search = bool(re.search(r'financial results|financial statements|annual report|investor presentation', query.replace('"', ''), re.I))
        annual_search = bool(re.search(r'annual report', query.replace('"', ''), re.I))
        # Filter before callers take their bounded slice. Otherwise previously
        # fetched releases can occupy both slots and hide a new useful document.
        fresh_hits = [hit for hit in hits if hit.url not in self.seen_urls]
        return sorted(fresh_hits, key=lambda hit: (
            not bool(re.search(r'\bsubsidiar(?:y|ies)\b', re.sub(r'[-_/]+', ' ', unquote(hit.url)), re.I)) if financial_search else False,
            bool(re.search(r'annual[-_\s]+report|integrated[-_\s]+report|(?:^|[^a-z])iar(?:[^a-z]|$)', unquote(hit.url) + ' ' + hit.title, re.I)) if annual_search else False,
            bool(re.search(r'(?:un)?audited[-_\s]+financial[-_\s]+results|statement[-_\s]+of[-_\s]+assets|balance[-_\s]+sheet', unquote(hit.url) + ' ' + hit.title, re.I)) if financial_search else False,
            issuer_named(hit.title, self.company),
            issuer_named(hit.title + " " + hit.snippet, self.company),
            bool(re.search(r"\.pdf(?:[/?#]|$)", hit.url, re.I)),
            bool(re.search(r"financial\s+results|investor\s+presentation", hit.title, re.I))), reverse=True)

    def ingest(self, hits, *, time_reserve=0, parse_limit=None, stop_when_balance_ready=False, document_reserve=0):
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
            if self.budget.fetch_documents >= self.budget.max_fetch_documents - document_reserve:
                self.limitations.append("Document cap reached; remaining source leads were withheld.")
                break
            fetcher = PublicFetcher(self.settings.data_dir, min(self.settings.source_request_timeout_seconds, max(.1, self.budget.remaining_seconds() - time_reserve)), self.settings.max_source_bytes)
            fetched = self.calls.invoke(["fetch", hit.url], "fetching", lambda: self.budget.reserve("fetch_documents"),
                                        lambda: (fetcher.fetch(hit.url), {"provider": "public_http"}), asdict, lambda p: FetchResult(**p))
            if not fetched.local_path or not fetched.body_hash:
                self.limitations.append(f"Source unavailable: {hit.url}: {fetched.error}")
                continue
            if fetched.body_hash in {d.content_hash for d in self.documents}:
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
                for page_index in prioritized_ocr_pages(parsed)[:self.settings.max_ocr_pages]:
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
                        self.limitations.append(f"OCR page {page_index + 1} withheld: {exc}")
            except Exception as exc:
                self.limitations.append(f"Source parse failed: {hit.url}: {exc}")
                continue
            text = "\n".join(p.text for p in parsed.passages)
            published = source_publication(raw, text)
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
            identified = (issuer_cover_identity(text[:3000], self.company) or issuer_named(text[:3000], self.company)
                          or issuer_symbol_reference(text, self.company))
            if raw.startswith(b"%PDF") and foreign_cover_identity(text, self.company):
                identified = False
            portal_host = urlparse(fetched.final_url or hit.url).hostname or ''
            shared_portal = any(other.id != self.company.id and
                               any(domain_matches(portal_host, domain) for domain in other.verified_ir_domains)
                               for other in self.store.search_companies(''))
            if shared_portal:
                identified = issuer_cover_identity(text[:3000], self.company) and not foreign_cover_identity(text, self.company)
            if not identified and self.company.business_profiles[0].value == 'bank':
                # A branded bank presentation can use an acronym cover, while
                # its comparative SOLO/GROUP table explicitly binds the issuer.
                # The binder checks target aliases, scope, dates and columns.
                identified = any(comparative_bank_batch(p, self.company) for p in parsed.passages)
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
            if stop_when_balance_ready and kind.startswith("issuer") and document.cutoff_eligibility == "eligible":
                # Enough explicit comparative balances can enter independent
                # extraction review now; remaining annual-report leads must not
                # consume the time needed to challenge and verify the findings.
                batches = [comparative_bank_batch(p, self.company) for p in parsed.passages]
                if any(batch and len(batch.facts) >= 4 and all(f.period_end <= self.cutoff for f in batch.facts) for batch in batches):
                    break
        self.progress()

    def progress(self, checks=0):
        self.store.update_run(self.run_id, progress={"sources_found": len(self.seen_urls), "documents_parsed": len(self.documents), "calculations_completed": len(self.calculations), "counterevidence_checks": checks})

    def financial_passage(self, passage):
        aliases = [alias for metric in metrics_for_profile(self.company.business_profiles[0])
                   for alias in (*metric.aliases, metric.key.replace('_', ' '))]
        return bool(re.search(r'\d', passage.text) and any(
            re.search(r'\b' + re.escape(alias) + r'\b', passage.text, re.I) for alias in aliases))

    def issuer_financial_coverage(self):
        eligible = {d.id for d in self.documents if d.cutoff_eligibility == 'eligible' and d.document_type.startswith('issuer')}
        return any(p.document_id in eligible and self.financial_passage(p) for p in self.passages)

    def extraction_model(self, passage, schema, payload, *args):
        from signal_research.providers.llm.nvidia_provider import NvidiaStructuredOutputError

        try:
            return self.calls.model(schema, payload, *args)
        except NvidiaStructuredOutputError as exc:
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

    def extract(self, limit=4):
        profile = self.company.business_profiles[0]
        metrics = metrics_for_profile(profile)
        eligible = {d.id for d in self.documents if d.cutoff_eligibility == "eligible" and d.document_type.startswith("issuer")}
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
            periods = [period for period in source_dates(p.text) if period <= self.cutoff]
            periods.extend(period for _, period in month_end_columns(p.text) if period <= self.cutoff)
            latest_period = max(periods).toordinal() if periods else 0
            return (bindings and dates and unit_header, bindings and dates, rows > 0 if profile.value == "bank" else financial_rows > 0, p.extraction_method not in {"pdf_table", "html_table"}, rows if profile.value == "bank" else financial_rows, latest_period, published[p.document_id], labels)
        ranked = sorted([p for p in self.passages if p.id not in self.extracted and p.document_id in eligible and
                         not subsidiary_only(p.text) and self.financial_passage(p)], key=score, reverse=True)
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
        for passage in passages:
            self.extracted.add(passage.id)
            identity_passages = [p for p in self.passages if p.document_id == passage.document_id and p.page_index in {None, 0, 1}][:4]
            identity_passages = [p for p in identity_passages if issuer_cover_identity(p.text, self.company)
                                 or issuer_symbol_reference(p.text, self.company)]
            issuer_bound = bool(identity_passages)
            batch = comparative_bank_batch(passage, self.company, document_issuer_verified=issuer_bound) if profile.value == "bank" else None
            if batch is None:
                batch = financial_table_batch(passage, self.company, profile, document_issuer_verified=issuer_bound)
            extraction_method = "explicit_comparative_columns" if batch else "model"
            if batch is None:
                dates = sorted(set(source_dates(passage.text)) | {period for _, period in month_end_columns(passage.text)})
                batch = self.extraction_model(passage, source_fact_batch_schema([m.key for m in metrics], passage.id, dates), {"passage_id": passage.id, "entity": self.company.legal_name,
                                      "source_period_columns": [{"label": label, "period_end": str(period)} for label, period in month_end_columns(passage.text)],
                                      "source_declared_durations": [*declared_duration_periods(passage.text), *explicit_duration_ranges(passage.text)],
                                      "document_identity_passages": [{"id": p.id, "text": p.text[:1600]} for p in identity_passages if issuer_named(p.text, self.company)],
                                      "allowed_metric_keys": [m.key for m in metrics],
                                      "allowed_metric_definitions": [{"key": m.key, "period_type": "instant" if m.kind == "stock" else "duration"} for m in metrics],
                                      "passage_text": passage.text}, "extract", "extracting",
                                      extraction_instruction(profile) + " Supplied source_declared_durations normalize an explicit duration and full end date; use only the matching start/end pair. Never use the period of a different column or metric.")
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
                                           "candidates": [c.model_dump(mode="json") | {"index": i} for i, c in enumerate(candidates)]}, "extract", "normalizing",
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
            elif len({fact.metric_key for fact in self.facts}) >= 2 and len(derive_calculations(self.facts)) >= 2:
                # Comparable verified measures are enough to investigate an angle.
                # Preserve the remaining call/time allowance for counterevidence
                # and semantic review instead of extracting unrelated report pages.
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
        self.progress()
        # Persist the whole reviewed state, including an empty state after a
        # conflict invalidates earlier figures. Recovery must never resurrect
        # figures from an older snapshot or pretend a discovery was established.
        from signal_research.research.verifier import verify_report
        snapshot = self.abstain(["Investigation did not finish; retained observations do not establish a discovery."])
        snapshot.outcome = ResearchOutcome.PARTIAL
        verify_report(snapshot)
        self.store.checkpoint(self.run_id, "evidence_collected", self.evidence_iteration, snapshot.model_dump(mode="json"))
        self.evidence_iteration += 1

    def payload(self, hypothesis=None, required_passage_ids=()):
        documents = {d.id: d for d in self.documents if d.cutoff_eligibility == "eligible"}
        used = {fact.passage_id for fact in self.facts}
        supporting = [p for p in self.passages if p.id in used and p.document_id in documents]
        context = [p for p in self.passages if p.document_id in documents and
                   not documents[p.document_id].document_type.startswith("issuer")]
        identities = [*identity_aliases(self.company.legal_name), *self.company.aliases, *self.company.symbols]
        question = (hypothesis.statement + ' ' + hypothesis.mechanism if hypothesis else
                    CONTEXT_TERMS[self.company.business_profiles[0]])
        def context_score(passage):
            return relevance(passage.text, identities, question)
        # Keep only cited issuer spans plus bounded original context. Sending an
        # entire annual report again would exhaust the token cap before analysis.
        bounded_context = diverse_context(context, documents, identities, question)
        used_documents = {p.document_id for p in supporting}
        qualifiers = [p for p in self.passages if p.document_id in used_documents and p.id not in used and
            re.search(r'\bmerger|amalgamation|restatement|reclassification|scope\s+of\s+consolidation|change\s+in\s+accounting', p.text, re.I)]
        qualifiers.sort(key=context_score, reverse=True)
        required = [p for p in self.passages if p.id in required_passage_ids and p.document_id in documents]
        selected = list({p.id: p for p in [*supporting, *qualifiers[:2], *bounded_context, *required]}.values())
        source_spans = []
        for passage in selected:
            anchors = [f.value_raw for f in self.facts if f.passage_id == passage.id]
            excerpt = exact_excerpt(passage.text, anchors, question,
                                    limit=max(2000, len(passage.text)) if anchors else 2000)
            source_spans.append({"id": passage.id, "document_id": passage.document_id,
                                 **excerpt})
        selected_documents = {p.document_id for p in selected}
        return {"company": self.company.model_dump(mode="json"), "cutoff": self.cutoff,
                "facts": [{key: value for key, value in f.model_dump(mode="json").items() if key in {
                    "id", "entity_id", "metric_key", "value_raw", "value_decimal", "unit_normalized", "currency",
                    "period_start", "period_end", "period_type", "scope", "segment", "definition_id", "passage_id"}} for f in self.facts],
                "calculations": [calculation_context(c, self.facts) for c in self.calculations],
                "documents": [{"id": d.id, "title": d.title, "publisher": d.publisher,
                               "published_at": d.published_at, "origin_family_id": d.origin_family_id,
                               "document_type": d.document_type} for d in documents.values() if d.id in selected_documents],
                "passages": source_spans,
                "historical_series": comparable_series(self.facts),
                "coverage_note": "Passages may be exact bounded excerpts. Omitted text is not evidence of absence. Full passages remain in the report; verified facts retain their independently reviewed bindings."}

    def abstain(self, reasons):
        report = build_abstention(self.run_id, self.company, self.cutoff, self.documents, self.passages, self.facts, reasons, mode="live")
        report.limitations += self.limitations
        report.generation_metadata["search_queries"] = self.queries
        report.generation_metadata["research_decisions"] = self.decisions
        report.source_coverage['historical_series'] = comparable_series(self.facts)
        # A withheld hypothesis must not discard independently verified arithmetic.
        report.calculations = self.calculations
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
                    'reason': reason, 'fact_ids': hypothesis.fact_ids,
                    'calculation_ids': hypothesis.calculation_ids,
                    'passage_ids': list(passage_ids), 'published': False}
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
        if not self.calculations or not needs_history(self.facts):
            return
        if (self.budget.search_calls >= self.budget.max_search_calls - 4
                or self.budget.fetch_documents >= self.budget.max_fetch_documents - 3
                or self.budget.model_calls >= self.budget.max_model_calls - 6
                or self.budget.remaining_seconds() <= self.time_reserve(210)):
            self.limitations.append('Historical coverage remains two snapshots or less; further collection would consume final verification allowance.')
            return
        oldest = min(f.period_end.year for f in self.facts if f.period_end)
        self.stage('discovering', 'Seeking earlier comparable disclosures and changes in reporting boundaries')
        hits = self.search(f'"{self.company.legal_name}" "annual report" {oldest - 1} {oldest}',
                           self.company.verified_ir_domains or None)
        self.ingest(hits[:1], time_reserve=self.time_reserve(180), parse_limit=25, document_reserve=3)
        self.extract(limit=1)
        self.store.artifact(self.run_id, 'historical_coverage', {'series': comparable_series(self.facts)})
        if needs_history(self.facts):
            self.limitations.append('Only one or two comparable snapshots were verified; trend onset and sustained historical development are not established.')

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
        if self.budget.search_calls >= self.budget.max_search_calls or self.budget.fetch_documents >= self.budget.max_fetch_documents:
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
        return self.calls.model(schema, payload, stage="challenging", instruction="Challenge the proposed mechanism using all evidence. Check every stated percentage against its specific registered calculation, input dates and scope; reject invented numbers and reversed arithmetic. Mark refuted if contradicted. Mark unresolved if scope, acquisitions, seasonality or missing evidence could explain the relationship. Select only directly relevant eligible source passage IDs. relevant_passage_ids must contain full IDs from the passages array only, never fact or calculation IDs. Distinguish a qualified arithmetic observation from an unproven causal mechanism; unresolved mechanism evidence does not refute reproducible arithmetic. Lack of search results does not establish absence of counterevidence. Retain only a qualified observation if the stronger inference fails. Assess novelty using the supplied original passages: identify the published explanation and describe the additional cross-metric or cross-source synthesis. Different headline wording is not novelty. Mark simple_restatement for ordinary reported results, already_covered if the relationship is already explained by the sources, and novelty_unknown when evidence is insufficient. historical_series describes observed coverage; two snapshots cannot establish onset, a sustained trend or causality.")

    def run(self, plan):
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
        for query, domains in queries:
            initial.append(self.search(query, domains))
        hits = [items[i] for i in range(4) for items in initial if len(items) > i]
        if not any(any(domain_matches(urlparse(hit.url).hostname or "", domain)
                       for domain in self.company.verified_ir_domains) for hit in hits):
            hits = [*verified_disclosure_indexes(self.company), *hits]
        self.stage("fetching", "Retrieving original documents; search snippets remain leads")
        self.ingest(hits, time_reserve=self.time_reserve(300), stop_when_balance_ready=profile.value == "bank",
                    document_reserve=min(6, self.budget.max_fetch_documents // 3))
        if not self.issuer_financial_coverage():
            if self.budget.search_calls < self.budget.max_search_calls and self.budget.fetch_documents < self.budget.max_fetch_documents - 3:
                self.stage("discovering", "Seeking a dated exchange copy when issuer-portal leads lack usable disclosure dates")
                filing_hits = self.search(f'"{self.company.legal_name}" "financial results" {self.cutoff.year} filetype:pdf', ['nseindia.com', 'bseindia.com'])
                self.stage("fetching", "Retrieving exchange disclosure leads; document identity and publication date still require verification")
                self.ingest(filing_hits[:2], time_reserve=self.time_reserve(240), document_reserve=3)
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
                requirement = "verified issuer facts with complete metric, value, period, unit and scope bindings" if eligible_issuer else "dated official issuer financial disclosures"
                return self.abstain([requirement])
            return self.abstain(["comparable verified facts for a relevant registered calculation"])
        self.collect_history()
        if not self.calculations:
            return self.abstain(['comparable verified arithmetic after historical-source reconciliation'])
        self.stage("hypothesizing", "Generating and ranking observation-led mechanisms with explicit tests")
        payload = self.payload()
        batch = self.calls.model(cited_hypothesis_schema(payload), payload, instruction="Propose up to three non-obvious relationships grounded in the calculations. Separate observation from mechanism. Give concise web-search fragments of at most twelve words, not conditional questions. The opposing query must seek documented reclassification, seasonality, regulation, acquisitions, scope changes or the strongest alternative. Reject pure latest-results summaries; investigate cross-metric or segment relationships with historical development. Use supplied fact/calculation IDs only. Copy numerical changes from output_display; retain their signs and ordered input roles. Read growth_gap as first metric YoY growth minus second metric YoY growth, not the change in that gap over time. Do not invent, estimate or mentally calculate a new percentage, ratio or differential. advances_as_reported is a balance-sheet label, not verified gross loans or an official credit-deposit ratio. Prefer cross-metric relationships over restating headline results. Return no candidates if nothing defensible exists.")
        self.store.artifact(self.run_id, "hypotheses", batch.model_dump(mode="json"))
        facts = {f.id for f in self.facts}
        calculations = {c.id for c in self.calculations}
        candidates = sorted([h for h in batch.candidates if set(h.fact_ids) <= facts and set(h.calculation_ids) <= calculations], key=lambda h: h.significance + h.novelty, reverse=True)
        candidate_cap = 3 if self.store.get_summary(self.run_id).mode.value == "deep" else 2
        for iteration, hypothesis in enumerate(candidates[:candidate_cap]):
            if not self.current_candidate(hypothesis):
                continue
            hypothesis = hypothesis.model_copy(update={"calculation_ids": complete_calculation_lineage(
                hypothesis.statement + ' ' + hypothesis.mechanism, hypothesis.fact_ids,
                hypothesis.calculation_ids, self.calculations)})
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
            self.stage("investigating", f"Following candidate {iteration + 1} with a targeted evidence query")
            followup = self.search(self.focused_query(hypothesis.next_query))
            opposing = self.search(self.focused_query(hypothesis.opposing_query), opposing=True)
            self.stage("fetching", "Retrieving targeted supporting and opposing sources")
            self.ingest([*opposing[:3], *followup[:3]], time_reserve=self.time_reserve(120), parse_limit=25)
            self.extract(limit=2)
            if not self.current_candidate(hypothesis):
                continue
            self.recover_context(hypothesis)
            self.stage("challenging", "Testing the strongest alternative and revising or rejecting the mechanism")
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
                    continue
                before = len(self.documents)
                self.recover_context(hypothesis, force=True)
                if len(self.documents) > before:
                    self.stage("challenging", "Checking the candidate against newly retrieved independent rating evidence")
                    challenge = self.challenge(hypothesis)
                    self.store.artifact(self.run_id, "challenge", challenge.model_dump(mode="json"))
                    relevant = [p for p in self.passages if p.id in challenge.relevant_passage_ids]
                    origins = {d.origin_family_id for d in self.documents if d.cutoff_eligibility == "eligible" and d.id in {p.document_id for p in relevant}}
                if challenge.refuted or len(origins) < 2:
                    self.limitations.append("Candidate lacked independently originated relevant evidence or was refuted by the additional check.")
                    self.record_decision(hypothesis, 'withheld', challenge.reason, challenge.relevant_passage_ids)
                    continue
            if challenge.novelty_status != 'additional_supported_synthesis' or not challenge.novelty_rationale:
                self.record_decision(hypothesis, challenge.novelty_status, challenge.novelty_rationale or 'Additional synthesis was not established.', challenge.relevant_passage_ids)
                self.limitations.append('Candidate did not establish additional supported synthesis beyond reported results or published explanations.')
                continue
            self.stage("composing", "Drafting all eight required discovery fields from verified artifacts")
            draft_payload = self.payload(hypothesis, challenge.relevant_passage_ids) | {"hypothesis": hypothesis.model_dump(mode="json"), "challenge": challenge.model_dump(mode="json")}
            draft = self.calls.model(cited_draft_schema(draft_payload), draft_payload, stage="composing", instruction="Write a qualified discovery headline, 3–5 significance statements and the strongest counterargument. Every factual statement must cite supplied supporting fact/passage IDs and calculation IDs where numerical. Use full IDs verbatim from the corresponding facts, passages and calculations arrays. Every inferred headline or significance claim needs directly relevant support from at least two independent origin families; exchange reposts of issuer material are the same origin. Pure reported figures may use primary source facts. Include independently originated relevant context. State an observable future condition identifying the metric or event, comparison direction, observation window and expected source that would falsify the relationship, with no invented historical numbers or arbitrary numeric threshold. Use the challenged qualification. No investment advice.")
            report = self.compose(draft, challenge, hypothesis.opposing_query)
            if report:
                return report
            self.record_decision(hypothesis, 'withheld', 'The drafted conclusion failed independent final verification.', challenge.relevant_passage_ids)
        return self.abstain(batch.missing_evidence or ["a discovery that survives counterevidence and semantic verification"])

    def compose(self, draft, challenge, opposing_query):
        facts, passages, calculations = {f.id: f for f in self.facts}, {p.id: p for p in self.passages}, {c.id: c for c in self.calculations}
        statements = [draft.headline, *draft.why_it_matters, draft.counterargument]
        claims = []
        for statement in statements:
            if not set(statement.fact_ids) <= facts.keys() or not set(statement.passage_ids) <= passages.keys() or not set(statement.calculation_ids) <= calculations.keys() or not (statement.fact_ids or statement.passage_ids):
                self.limitations.append("Draft referenced missing evidence and was withheld.")
                return None
            identifier = uuid5(self.run_id, f"claim:{len(claims)}:{statement.text}")
            claims.append(Claim(id=identifier, run_id=self.run_id, text=statement.text, kind=statement.kind,
                                evidence_links=[EvidenceLink(claim_id=identifier, passage_or_fact_id=i, relation=EvidenceRelation.SUPPORTING, reason="Reviewed source support") for i in [*statement.fact_ids, *statement.passage_ids]], calculation_ids=statement.calculation_ids))
        review = self.calls.model(semantic_review_schema([claim.id for claim in claims]), self.payload(required_passage_ids={identifier for statement in statements for identifier in statement.passage_ids}) | {"claims": [c.model_dump(mode="json") for c in claims], "falsification": draft.falsification, "observation_window": draft.falsification_window, "expected_source": draft.falsification_source, "novelty_assessment": challenge.model_dump(mode="json")}, stage="verifying", instruction="Independently verify every claim against ONLY its linked source passages/facts and registered calculations. Check all numbers and qualifiers, metric/date/scope binding, causal overreach and context relevance. Inferred claims must remain qualified. Every supporting link must be relevant and entail the claim in combination. Reject unsupported detail even when a citation ID exists. Return exactly one verdict per claim ID with no duplicates or omissions. Ensure falsification identifies an observable metric or event, comparison direction, concrete observation window and expected source, follows from the relationship, and uses no fabricated historical facts. Independently assess non_obvious_synthesis_supported: ordinary growth summaries, mere headline rewording, and unsupported causal mechanisms do not qualify. Compare the supplied novelty assessment with its linked evidence, and reject historical development claims beyond the observed series. Detect investment recommendations.")
        verdicts = {v.claim_id: v for v in review.verdicts}
        if len(review.verdicts) != len(claims) or set(verdicts) != {c.id for c in claims} or review.contains_investment_recommendation or not review.non_obvious_synthesis_supported or not review.falsification_is_observable or any(c.id not in verdicts or not verdicts[c.id].supported for c in claims):
            self.limitations.append("Independent semantic review rejected a material statement; candidate withheld.")
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
        if len(supporting_origins(claims[0], facts, passages, {d.id: d for d in documents})) < 2:
            self.limitations.append("Headline lacked independently originated supporting evidence; candidate withheld.")
            return None
        origins = {d.origin_family_id for d in documents if d.cutoff_eligibility == "eligible"}
        if len(origins) < 2 or any(d.cutoff_eligibility != "eligible" for d in documents) or not any(d.document_type.startswith("issuer") for d in documents):
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
                              why_it_matters=[WhyItMatters(text=c.text, claim_id=c.id) for c in claims[1:-1]], evidence_claim_ids=[c.id for c in claims],
                              timeline_event_ids=[e.id for e in timeline], calculation_ids=list(used_calcs),
                              counterargument=Counterargument(statement=claims[-1].text, evidence_claim_ids=[claims[-1].id], search_attempted=True, search_summary=f"Searched: {opposing_query}. {challenge.reason}", unresolved=challenge.unresolved),
                              falsification_rules=[rule], evidence_strength=strength,
                              strength_rationale=f"{len(origins)} relevant origin families; registered calculations independently reproduced; " + ("the strongest alternative remains unresolved." if challenge.unresolved else "the tested alternative did not refute the qualified relationship.") +
                              (f" Original publication dates are unknown for {unknown_publication} sources; their current availability is verified by retrieval receipts." if unknown_publication else ""))
        return attest_report(ResearchReport(run_id=self.run_id, company=self.company, cutoff=self.cutoff,
                            historical_coverage=" / ".join(sorted({str(f.period_end) for f in self.facts if f.id in used_facts})),
                            source_coverage={"mode": "live", "synthetic": False, "documents_found": len(self.documents), "documents_used": len(documents), "eligible_origin_families": len(origins), "primary_source": True},
                            outcome=ResearchOutcome.DISCOVERY, publication_status=PublicationStatus.PUBLISHED, discoveries=[discovery], limitations=self.limitations,
                            generation_metadata={"pipeline": "extract-bind-calculate-hypothesize-investigate-challenge-review-v2", "provider": self.settings.llm_provider, "model_id": self.settings.model_for_role("research"), "search_queries": self.queries, "research_decisions": self.decisions, "novelty_status": challenge.novelty_status, "novelty_rationale": challenge.novelty_rationale, "published_explanation": challenge.published_explanation, "non_obvious_synthesis_reviewed": review.non_obvious_synthesis_supported},
                            claims=claims, timeline_events=timeline, calculations=[c for c in self.calculations if c.id in used_calcs], facts=[f for f in self.facts if f.id in used_facts], passages=[p for p in self.passages if p.id in used_passages], documents=documents))
