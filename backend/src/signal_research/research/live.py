from __future__ import annotations

import re
from dataclasses import asdict
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
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
from signal_research.extraction.bank_tables import (
    comparative_bank_batch,
    month_end_columns,
    scope_in_text,
    subsidiary_only,
)
from signal_research.extraction.dates import source_dates
from signal_research.extraction.models import source_fact_batch_schema
from signal_research.extraction.validate import validate_candidate
from signal_research.finance.calculations import calculate, numeric_fact
from signal_research.finance.registry import metrics_for_profile
from signal_research.research.integrity import attest_report
from signal_research.research.peer_selector import select_peers
from signal_research.research.report_builder import build_abstention
from signal_research.retrieval.disclosures import linked_disclosures, verified_disclosure_indexes
from signal_research.retrieval.fetch import FetchResult, PublicFetcher
from signal_research.retrieval.metadata import publication_day, source_origin, source_publication
from signal_research.retrieval.passages import bounded_parse_pdf, parse_html, parse_xbrl
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
    statement: str
    mechanism: str
    fact_ids: list[UUID] = Field(min_length=1)
    calculation_ids: list[UUID] = Field(min_length=1)
    next_query: str
    opposing_query: str
    falsification: str
    significance: int = Field(ge=0, le=5)
    novelty: int = Field(ge=0, le=5)


class HypothesisBatch(StrictModel):
    candidates: list[Hypothesis] = Field(max_length=3)
    missing_evidence: list[str]


class Challenge(StrictModel):
    refuted: bool
    unresolved: bool
    strongest_alternative: str
    reason: str
    relevant_passage_ids: list[UUID]


class Statement(StrictModel):
    text: str
    kind: ClaimKind
    fact_ids: list[UUID]
    passage_ids: list[UUID]
    calculation_ids: list[UUID]


class DiscoveryDraft(StrictModel):
    headline: Statement
    why_it_matters: list[Statement] = Field(min_length=3, max_length=5)
    counterargument: Statement
    falsification: str


def cited_draft_schema(payload):
    """Give the provider an explicit choice of existing evidence identifiers."""
    fields = {name: (list[UUID], Field(json_schema_extra={"items": {
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
                pairs.append((current, prior))
    for a, b in pairs:
        if a.metric_key != "gross_advances":
            continue
        for c, d in pairs:
            if c.metric_key == "deposits":
                add("growth_gap", [a, b, c, d])
                add("ldr_change", [a, b, c, d])
                add("loan_to_deposit", [a, c])
    for numerator, denominator, formula in (("vnb", "ape", "vnb_to_ape"), ("fee_revenue", "average_aum", "fee_yield")):
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

    def stage(self, status, summary):
        from signal_research.domain.enums import RunStatus
        self.machine._set_stage(self.run_id, RunStatus(status), f"live_{status}", summary)

    def search(self, query, domains=None, opposing=False):
        self.queries.append(query)
        return self.calls.search(query, domains, self.cutoff, "challenging" if opposing else "discovering")

    def ingest(self, hits, *, time_reserve=0, parse_limit=None, stop_when_balance_ready=False):
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
            if self.budget.fetch_documents >= self.budget.max_fetch_documents:
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
            if depth == 0 and fetched.content_type == "text/html":
                leads = linked_disclosures(raw, fetched.final_url or hit.url, self.company.verified_ir_domains, issuer_name=self.company.legal_name)
                queue[:0] = [(lead, 1) for lead in leads if lead.url not in self.seen_urls]
            try:
                if raw.startswith(b"%PDF"):
                    parsed = bounded_parse_pdf(document_id, Path(fetched.local_path), min(self.settings.pdf_parse_timeout_seconds, parse_limit or self.settings.pdf_parse_timeout_seconds, max(.1, self.budget.remaining_seconds() - time_reserve)))
                elif "xml" in (fetched.content_type or ""):
                    parsed = parse_xbrl(document_id, raw)
                else:
                    parsed = parse_html(document_id, raw)
                for page_index in parsed.blank_page_indexes[:self.settings.max_ocr_pages]:
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
            publisher, origin, kind = source_origin(fetched.final_url or hit.url, self.company, hit.title, text)
            for existing in self.documents:
                existing_text = "\n".join(p.text for p in self.passages if p.document_id == existing.id)
                if len(text) > 100 and SequenceMatcher(None, text[:20000], existing_text[:20000], autojunk=False).ratio() >= .9:
                    origin = existing.origin_family_id
            document = SourceDocument(id=document_id, canonical_url=hit.url, final_url=fetched.final_url or hit.url,
                                      publisher=publisher, origin_family_id=origin, title=hit.title or parsed.title, document_type=kind,
                                      published_at=published, retrieved_at=datetime.now(UTC), content_hash=fetched.body_hash,
                                      mime_type=fetched.content_type or "application/octet-stream", local_object_key=fetched.local_path,
                                      cutoff_eligibility="eligible" if published and publication_day(published) <= self.cutoff else "ineligible" if published else "unknown")
            self.documents.append(document)
            self.passages.extend(parsed.passages)
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
            return (bindings and dates, rows > 0, p.extraction_method not in {"pdf_table", "html_table"}, rows, published[p.document_id], labels)
        ranked = sorted([p for p in self.passages if p.id not in self.extracted and p.document_id in eligible and not subsidiary_only(p.text)], key=score, reverse=True)
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
            batch = comparative_bank_batch(passage, self.company) if profile.value == "bank" else None
            extraction_method = "explicit_comparative_columns" if batch else "model"
            if batch is None:
                dates = sorted(set(source_dates(passage.text)) | {period for _, period in month_end_columns(passage.text)})
                batch = self.calls.model(source_fact_batch_schema([m.key for m in metrics], passage.id, dates), {"passage_id": passage.id, "entity": self.company.legal_name,
                                      "source_period_columns": [{"label": label, "period_end": str(period)} for label, period in month_end_columns(passage.text)],
                                      "allowed_metric_keys": [m.key for m in metrics],
                                      "allowed_metric_definitions": [{"key": m.key, "period_type": "instant" if m.kind == "stock" else "duration"} for m in metrics],
                                      "passage_text": passage.text}, "extract", "extracting",
                                      "Extract at most six complete source-backed facts, preferring comparable balances from current and prior-year columns. Net advances are not gross advances: omit them when only gross_advances is registered. Do not confuse interest earned on advances with advances balances or NPA amounts with percentages. Use segment='all' for issuer totals. Every period_end must match its own column; supplied source_period_columns normalize explicit comparative month-end headers. SBI SOLO denotes standalone SBI and SBI GROUP consolidated SBI. Stock balances use instant period_type and null period_start. A rupee symbol means INR; in '000 means thousand rupees; in Crores means INR crore. Copy raw cells without converting scale. Set evidence_quote=null to retain the complete source passage verbatim. Preserve row, column and scope association. Reject missing scope, definitions and duration starts. Never infer dates from FY or quarter labels. Omit incomplete facts; never invent placeholder or NA facts.")
            accepted, candidates, rejected = [], [], []
            for candidate in batch.facts:
                validation = validate_candidate(candidate, passage, self.company.id, profile)
                if validation.fact and validation.fact.period_end <= self.cutoff:
                    accepted.append(validation.fact)
                    candidates.append(candidate)
                else:
                    rejected.append({"metric": candidate.metric_key, "reason": validation.reason or "period exceeds cutoff"})
            if accepted:
                review = self.calls.model(fact_review_schema(len(candidates)), {"entity": self.company.legal_name, "source_text": passage.text,
                                           "candidates": [c.model_dump(mode="json") | {"index": i} for i, c in enumerate(candidates)]}, "extract", "normalizing",
                                           f"Independently check every indexed candidate. A value appearing somewhere in a passage is insufficient. Verify exact metric/value/date/column binding, issuer identity (reject peer/subsidiary values), scope, unit, currency, period type, segment and definition. Comparative balance-sheet headers Jun 25 and Dec 25 mean the last calendar day of June and December 2025, respectively. SBI SOLO denotes standalone SBI and SBI GROUP consolidated SBI; keep the two column groups separate and never treat net advances as gross advances. supported=false for ambiguity. Return exactly {len(candidates)} verdicts, one per explicit candidate index from 0 to {len(candidates) - 1}. Preserve those indices. Compare against each candidate's own current or prior period_end column. Each reason must be one brief sentence of at most 300 characters. Do not repeat candidates or add verdicts.")
                verdicts = {v.index: v for v in review.verdicts}
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

    def payload(self):
        documents = {d.id: d for d in self.documents if d.cutoff_eligibility == "eligible"}
        used = {fact.passage_id for fact in self.facts}
        supporting = [p for p in self.passages if p.id in used and p.document_id in documents]
        context = [p for p in self.passages if p.document_id in documents and
                   not documents[p.document_id].document_type.startswith("issuer")]
        metrics = metrics_for_profile(self.company.business_profiles[0])
        identities = [self.company.legal_name, *self.company.symbols]
        if self.company.legal_name == "State Bank of India":
            identities.append("SBI")
        def context_score(passage):
            text = passage.text.lower()
            issuer = any(re.search(r"\b" + re.escape(name.lower()) + r"\b", text) for name in identities)
            return (issuer, sum(alias.lower() in text for metric in metrics for alias in metric.aliases))
        context.sort(key=context_score, reverse=True)
        # Keep only cited issuer spans plus bounded original context. Sending an
        # entire annual report again would exhaust the token cap before analysis.
        bounded_context, counts = [], {}
        for passage in context:
            if counts.get(passage.document_id, 0) >= 2:
                continue
            bounded_context.append(passage)
            counts[passage.document_id] = counts.get(passage.document_id, 0) + 1
            if len(bounded_context) == 4:
                break
        return {"company": self.company.model_dump(mode="json"), "cutoff": self.cutoff,
                "facts": [f.model_dump(mode="json") for f in self.facts],
                "calculations": [c.model_dump(mode="json") for c in self.calculations],
                "passages": [{"id": p.id, "document_id": p.document_id, "text": p.text} for p in supporting + bounded_context]}

    def abstain(self, reasons):
        report = build_abstention(self.run_id, self.company, self.cutoff, self.documents, self.passages, self.facts, reasons, mode="live")
        report.limitations += self.limitations
        report.generation_metadata["search_queries"] = self.queries
        # A withheld hypothesis must not discard independently verified arithmetic.
        report.calculations = self.calculations
        return report

    def focused_query(self, query):
        prefix = f'"{self.company.legal_name}"'
        return query if self.company.legal_name.lower() in query.lower() else f"{prefix} {query}"

    def recover_context(self, hypothesis, force=False):
        """Search original independent reports before giving up on a candidate."""
        if self.budget.search_calls >= self.budget.max_search_calls or self.budget.fetch_documents >= self.budget.max_fetch_documents:
            return
        context_texts = [" ".join(p.text.lower() for p in self.passages if p.document_id == d.id)
                         for d in self.documents if d.document_type == "public_context" and d.cutoff_eligibility == "eligible"]
        if not force and any(self.company.legal_name.lower() in text or ("deposit" in text and "loan" in text) for text in context_texts):
            return
        self.stage("discovering", "Searching original independent rating reports to corroborate the funding observation")
        domains = ["icra.in", "crisil.com", "crisilratings.com", "indiaratings.co.in", "fitchratings.com"]
        query = f'"{self.company.legal_name}" credit rating deposits advances funding liquidity {self.cutoff.year}'
        hits = self.search(query, domains)
        self.stage("fetching", "Retrieving independent rating reports within the remaining source budget")
        self.ingest(hits[:3], time_reserve=120, parse_limit=25)

    def challenge(self, hypothesis):
        return self.calls.model(Challenge, self.payload() | {"hypothesis": hypothesis.model_dump(mode="json"), "opposing_query": hypothesis.opposing_query}, stage="challenging", instruction="Challenge the proposed mechanism using all evidence. Mark refuted if contradicted. Mark unresolved if scope, acquisitions, seasonality or missing evidence could explain the relationship. Select only directly relevant eligible source passage IDs. relevant_passage_ids must contain full IDs from the passages array only, never fact or calculation IDs. Distinguish a qualified arithmetic observation from an unproven causal mechanism; unresolved mechanism evidence does not refute reproducible arithmetic. Lack of search results does not establish absence of counterevidence. Retain only a qualified observation if the stronger inference fails.")

    def run(self, plan):
        self.stage("discovering", "Searching issuer disclosures and independent sector, regulatory and peer context")
        initial = []
        # Round-robin domains and independent leads so issuer hits cannot consume the entire cap.
        queries = [(t.query, self.company.verified_ir_domains or None) for t in plan[:2]]
        if queries:
            # Locate the underlying disclosures before asking mechanism-specific questions.
            # A literal cutoff day in every query can hide otherwise eligible annual filings.
            queries[0] = (f'"{self.company.legal_name}" annual report financial results investor presentation {self.cutoff.year}', self.company.verified_ir_domains or None)
        profile = self.company.business_profiles[0]
        if queries and profile.value == "bank":
            queries[0] = (f'"{self.company.legal_name}" financial results standalone deposits advances {self.cutoff.year}', self.company.verified_ir_domains or None)
        regulator = "RBI" if profile.value in {"bank", "nbfc"} else "IRDAI" if "insurer" in profile.value else "SEBI"
        peers = select_peers(self.company, self.store.search_companies(""), profile)
        queries += [(f'"{self.company.legal_name}" {regulator} {profile.value} deposits funding sector context', None)]
        self.store.artifact(self.run_id, "peer_selection", {"peers": [c.model_dump(mode="json") for c in peers.peers], "reasons": peers.reasons, "purpose": "independent context; peer values are not target facts"})
        for query, domains in queries:
            initial.append(self.search(query, domains))
        hits = [*verified_disclosure_indexes(self.company),
                *[items[i] for i in range(4) for items in initial if len(items) > i]]
        self.stage("fetching", "Retrieving original documents; search snippets remain leads")
        self.ingest(hits, time_reserve=240 if profile.value == "bank" else 0, stop_when_balance_ready=profile.value == "bank")
        if not any(d.document_type.startswith("issuer") and d.cutoff_eligibility == "eligible" for d in self.documents):
            # Mechanism queries and combined result queries can return only undated
            # indexes. Spend the remaining bounded search allowance on a precise
            # filing lead before treating that retrieval gap as absent evidence.
            if self.budget.search_calls < self.budget.max_search_calls and self.budget.fetch_documents < self.budget.max_fetch_documents:
                annual_query = f'"{self.company.legal_name}" "annual report" {self.cutoff.year - 1} {self.cutoff.year}'
                self.stage("discovering", "Searching for a dated annual disclosure after initial issuer leads lacked verified publication dates")
                annual_hits = self.search(annual_query, self.company.verified_ir_domains or None)
                self.stage("fetching", "Retrieving the annual disclosure leads within the remaining document and time limits")
                self.ingest(annual_hits)
        self.stage("extracting", "Extracting exact source spans and independently checking metric bindings")
        self.extract()
        if not self.calculations:
            if not self.facts:
                eligible_issuer = any(d.document_type.startswith("issuer") and d.cutoff_eligibility == "eligible" for d in self.documents)
                requirement = "verified issuer facts with complete metric, value, period, unit and scope bindings" if eligible_issuer else "dated official issuer financial disclosures"
                return self.abstain([requirement])
            return self.abstain(["comparable verified facts for a relevant registered calculation"])
        self.stage("hypothesizing", "Generating and ranking observation-led mechanisms with explicit tests")
        batch = self.calls.model(HypothesisBatch, self.payload(), instruction="Propose up to three non-obvious relationships grounded in the calculations. Separate observation from mechanism. Give an evidence query and an opposing query targeting reclassification, seasonality, regulation, scope changes or another strongest alternative. Use supplied fact/calculation IDs only. Prefer cross-metric relationships over restating headline results. Return no candidates if nothing defensible exists.")
        self.store.artifact(self.run_id, "hypotheses", batch.model_dump(mode="json"))
        facts = {f.id for f in self.facts}
        calculations = {c.id for c in self.calculations}
        candidates = sorted([h for h in batch.candidates if set(h.fact_ids) <= facts and set(h.calculation_ids) <= calculations], key=lambda h: h.significance + h.novelty, reverse=True)
        candidate_cap = 3 if self.store.get_summary(self.run_id).mode.value == "deep" else 2
        for iteration, hypothesis in enumerate(candidates[:candidate_cap]):
            self.stage("investigating", f"Following candidate {iteration + 1} with a targeted evidence query")
            followup = self.search(self.focused_query(hypothesis.next_query))
            opposing = self.search(self.focused_query(hypothesis.opposing_query), opposing=True)
            self.stage("fetching", "Retrieving targeted supporting and opposing sources")
            self.ingest([*opposing[:3], *followup[:3]], time_reserve=120, parse_limit=25)
            self.extract(limit=2)
            self.recover_context(hypothesis)
            self.stage("challenging", "Testing the strongest alternative and revising or rejecting the mechanism")
            challenge = self.challenge(hypothesis)
            self.store.artifact(self.run_id, "challenge", challenge.model_dump(mode="json"))
            self.progress(iteration + 1)
            if challenge.refuted:
                self.limitations.append(f"Candidate rejected: {challenge.reason}")
                continue
            relevant = [p for p in self.passages if p.id in challenge.relevant_passage_ids]
            origins = {d.origin_family_id for d in self.documents if d.cutoff_eligibility == "eligible" and d.id in {p.document_id for p in relevant}}
            if len(origins) < 2:
                if self.budget.remaining_seconds() < 120:
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
                    continue
            self.stage("composing", "Drafting all eight required discovery fields from verified artifacts")
            draft_payload = self.payload() | {"hypothesis": hypothesis.model_dump(mode="json"), "challenge": challenge.model_dump(mode="json")}
            draft = self.calls.model(cited_draft_schema(draft_payload), draft_payload, stage="composing", instruction="Write a qualified discovery headline, 3–5 significance statements and the strongest counterargument. Every factual statement must cite supplied supporting fact/passage IDs and calculation IDs where numerical. Use full IDs verbatim from the corresponding facts, passages and calculations arrays. Include independently originated relevant context. State an observable future condition that would falsify the relationship, with no invented numeric threshold. Use the challenged qualification. No investment advice.")
            report = self.compose(draft, challenge, hypothesis.opposing_query)
            if report:
                return report
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
        review = self.calls.model(SemanticReview, self.payload() | {"claims": [c.model_dump(mode="json") for c in claims], "falsification": draft.falsification}, stage="verifying", instruction="Independently verify every claim against ONLY its linked source passages/facts and registered calculations. Check all numbers and qualifiers, metric/date/scope binding, causal overreach and context relevance. Inferred claims must remain qualified. Every supporting link must be relevant and entail the claim in combination. Reject unsupported detail even when a citation ID exists. Return one verdict per claim ID. Ensure falsification is observable, follows from the relationship, and uses no fabricated historical facts. Detect investment recommendations.")
        verdicts = {v.claim_id: v for v in review.verdicts}
        if review.contains_investment_recommendation or not review.falsification_is_observable or any(c.id not in verdicts or not verdicts[c.id].supported for c in claims):
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
        origins = {d.origin_family_id for d in documents if d.cutoff_eligibility == "eligible"}
        if len(origins) < 2 or any(d.cutoff_eligibility != "eligible" for d in documents) or not any(d.document_type.startswith("issuer") for d in documents):
            return None
        timeline = [TimelineEvent(id=uuid4(), event_date=f.period_end, date_precision=DatePrecision.DAY,
                                 published_at=next(d.published_at for d in documents if d.id == passages[f.passage_id].document_id),
                                 description=f"{f.metric_key}: {f.value_decimal} {f.unit_normalized} ({f.scope.value})", claim_ids=[c.id for c in claims if any(l.passage_or_fact_id == f.id for l in c.evidence_links)], source_ids=[passages[f.passage_id].document_id]) for f in self.facts if f.id in used_facts]
        rule = FalsificationRule(id=uuid4(), observable_metric_or_event=draft.falsification, operator="observable condition", expected_source_type="comparable issuer disclosure or regulatory announcement", interpretation=draft.falsification, dependencies=list(used_calcs))
        strength = EvidenceStrength.WEAK if challenge.unresolved else EvidenceStrength.STRONG if len(origins) >= 3 else EvidenceStrength.MODERATE
        discovery = Discovery(id=uuid4(), discovery_sentence=claims[0].text,
                              why_it_matters=[WhyItMatters(text=c.text, claim_id=c.id) for c in claims[1:-1]], evidence_claim_ids=[c.id for c in claims],
                              timeline_event_ids=[e.id for e in timeline], calculation_ids=list(used_calcs),
                              counterargument=Counterargument(statement=claims[-1].text, evidence_claim_ids=[claims[-1].id], search_attempted=True, search_summary=f"Searched: {opposing_query}. {challenge.reason}", unresolved=challenge.unresolved),
                              falsification_rules=[rule], evidence_strength=strength,
                              strength_rationale=f"{len(origins)} relevant origin families; registered calculations independently reproduced; " + ("the strongest alternative remains unresolved." if challenge.unresolved else "the tested alternative did not refute the qualified relationship."))
        return attest_report(ResearchReport(run_id=self.run_id, company=self.company, cutoff=self.cutoff,
                            historical_coverage=" / ".join(sorted({str(f.period_end) for f in self.facts if f.id in used_facts})),
                            source_coverage={"mode": "live", "synthetic": False, "documents_found": len(self.documents), "documents_used": len(documents), "eligible_origin_families": len(origins), "primary_source": True},
                            outcome=ResearchOutcome.DISCOVERY, publication_status=PublicationStatus.PUBLISHED, discoveries=[discovery], limitations=self.limitations,
                            generation_metadata={"pipeline": "extract-bind-calculate-hypothesize-investigate-challenge-review", "provider": self.settings.llm_provider, "model_id": self.settings.model_for_role("research"), "search_queries": self.queries},
                            claims=claims, timeline_events=timeline, calculations=[c for c in self.calculations if c.id in used_calcs], facts=[f for f in self.facts if f.id in used_facts], passages=[p for p in self.passages if p.id in used_passages], documents=documents))
