from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from uuid import UUID, uuid4, uuid5

from pydantic import Field

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
from signal_research.extraction.models import ExtractedFactBatch
from signal_research.extraction.validate import validate_candidate
from signal_research.finance.calculations import calculate, numeric_fact
from signal_research.finance.registry import metrics_for_profile
from signal_research.research.integrity import attest_report
from signal_research.research.peer_selector import select_peers
from signal_research.research.report_builder import build_abstention
from signal_research.retrieval.fetch import FetchResult, PublicFetcher
from signal_research.retrieval.metadata import publication_day, source_origin, source_publication
from signal_research.retrieval.passages import bounded_parse_pdf, parse_html, parse_xbrl
from signal_research.worker.calls import DurableCalls


class FactVerdict(StrictModel):
    index: int
    supported: bool
    reason: str


class FactReview(StrictModel):
    verdicts: list[FactVerdict]


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


class ClaimVerdict(StrictModel):
    claim_id: UUID
    supported: bool
    reason: str


class SemanticReview(StrictModel):
    verdicts: list[ClaimVerdict]
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

    def ingest(self, hits):
        fetcher = PublicFetcher(self.settings.data_dir, min(self.settings.source_request_timeout_seconds, self.budget.remaining_seconds()), self.settings.max_source_bytes)
        for hit in hits:
            self.budget.check()
            if self.machine._cancelled(self.run_id):
                return
            if hit.url in self.seen_urls:
                continue
            self.seen_urls.add(hit.url)
            if self.budget.fetch_documents >= self.budget.max_fetch_documents:
                self.limitations.append("Document cap reached; remaining source leads were withheld.")
                break
            fetched = self.calls.invoke(["fetch", hit.url], "fetching", lambda: self.budget.reserve("fetch_documents"),
                                        lambda: (fetcher.fetch(hit.url), {"provider": "public_http"}), asdict, lambda p: FetchResult(**p))
            if not fetched.local_path or not fetched.body_hash:
                self.limitations.append(f"Source unavailable: {hit.url}: {fetched.error}")
                continue
            if fetched.body_hash in {d.content_hash for d in self.documents}:
                continue
            document_id = UUID(bytes=bytes.fromhex(fetched.body_hash[:32]))
            raw = Path(fetched.local_path).read_bytes()
            try:
                if raw.startswith(b"%PDF"):
                    parsed = bounded_parse_pdf(document_id, Path(fetched.local_path), min(self.settings.source_request_timeout_seconds, self.budget.remaining_seconds()))
                elif "xml" in (fetched.content_type or ""):
                    parsed = parse_xbrl(document_id, raw)
                else:
                    parsed = parse_html(document_id, raw)
                for page_index in parsed.blank_page_indexes[:self.settings.max_ocr_pages]:
                    from signal_research.extraction.ocr import ocr_page
                    try:
                        ocr_text = self.calls.invoke(["ocr", fetched.body_hash, page_index], "extracting", lambda: self.budget.reserve("ocr_pages"),
                                                    lambda: (ocr_page(Path(fetched.local_path), page_index, self.settings.data_dir, min(self.settings.source_request_timeout_seconds, self.budget.remaining_seconds())), {"provider": "local_ocr"}))
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
        self.progress()

    def progress(self, checks=0):
        self.store.update_run(self.run_id, progress={"sources_found": len(self.seen_urls), "documents_parsed": len(self.documents), "calculations_completed": len(self.calculations), "counterevidence_checks": checks})

    def extract(self, limit=4):
        profile = self.company.business_profiles[0]
        metrics = metrics_for_profile(profile)
        eligible = {d.id for d in self.documents if d.cutoff_eligibility == "eligible" and d.document_type.startswith("issuer")}
        def score(p):
            return sum(alias.lower() in p.text.lower() for m in metrics for alias in m.aliases)
        passages = sorted([p for p in self.passages if p.id not in self.extracted and p.document_id in eligible], key=score, reverse=True)[:limit]
        for passage in passages:
            self.extracted.add(passage.id)
            batch = self.calls.model(ExtractedFactBatch, {"passage_id": passage.id, "entity": self.company.legal_name,
                                      "allowed_metric_keys": [m.key for m in metrics], "passage_text": passage.text}, "extract", "extracting",
                                      "Extract exact source-backed values. Include an exact evidence_quote that contains the metric, numeric cell, complete dates, currency/scale and standalone/consolidated/segment scope. For tables preserve row and column association. Reject missing scope, definitions and duration starts. Never infer missing units or dates from a financial year label.")
            accepted, candidates, rejected = [], [], []
            for candidate in batch.facts:
                validation = validate_candidate(candidate, passage, self.company.id, profile)
                if validation.fact and validation.fact.period_end <= self.cutoff:
                    accepted.append(validation.fact)
                    candidates.append(candidate)
                else:
                    rejected.append({"metric": candidate.metric_key, "reason": validation.reason or "period exceeds cutoff"})
            if accepted:
                review = self.calls.model(FactReview, {"entity": self.company.legal_name, "source_text": passage.text,
                                           "candidates": [c.model_dump(mode="json") for c in candidates]}, "extract", "normalizing",
                                           "Independently check every indexed candidate. A value appearing somewhere in a passage is insufficient. Verify the exact metric/value/date/column binding, issuer identity (reject peer/subsidiary values), scope, unit, currency, period type, segment and definition. supported=false for ambiguity. Return one verdict per zero-based index.")
                verdicts = {v.index: v for v in review.verdicts}
                accepted = [fact for i, fact in enumerate(accepted) if i in verdicts and verdicts[i].supported]
            self.facts.extend(accepted)
            self.store.artifact(self.run_id, "fact_extraction", {"passage_id": passage.id, "accepted": [f.model_dump(mode="json") for f in accepted], "rejected": rejected})
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
        return {"company": self.company.model_dump(mode="json"), "cutoff": self.cutoff,
                "facts": [f.model_dump(mode="json") for f in self.facts],
                "calculations": [c.model_dump(mode="json") for c in self.calculations],
                "passages": [{"id": p.id, "document_id": p.document_id, "text": p.text} for p in self.passages if next(d for d in self.documents if d.id == p.document_id).cutoff_eligibility == "eligible"]}

    def abstain(self, reasons):
        report = build_abstention(self.run_id, self.company, self.cutoff, self.documents, self.passages, self.facts, reasons, mode="live")
        report.limitations += self.limitations
        report.generation_metadata["search_queries"] = self.queries
        return report

    def run(self, plan):
        self.stage("discovering", "Searching issuer disclosures and independent sector, regulatory and peer context")
        initial = []
        # Round-robin domains and independent leads so issuer hits cannot consume the entire cap.
        queries = [(t.query, self.company.verified_ir_domains or None) for t in plan[:2]]
        profile = self.company.business_profiles[0]
        regulator = "RBI" if profile.value in {"bank", "nbfc"} else "IRDAI" if "insurer" in profile.value else "SEBI"
        peers = select_peers(self.company, self.store.search_companies(""), profile)
        peer_names = ", ".join(c.legal_name for c in peers.peers)
        queries += [(f'"{self.company.legal_name}" {regulator} {profile.value} sector context {peer_names}', None)]
        self.store.artifact(self.run_id, "peer_selection", {"peers": [c.model_dump(mode="json") for c in peers.peers], "reasons": peers.reasons, "purpose": "independent context; peer values are not target facts"})
        for query, domains in queries:
            initial.append(self.search(query, domains))
        hits = [items[i] for i in range(4) for items in initial if len(items) > i]
        self.stage("fetching", "Retrieving original documents; search snippets remain leads")
        self.ingest(hits)
        self.stage("extracting", "Extracting exact source spans and independently checking metric bindings")
        self.extract()
        if not self.calculations:
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
            followup = self.search(hypothesis.next_query)
            opposing = self.search(hypothesis.opposing_query, opposing=True)
            self.stage("fetching", "Retrieving targeted supporting and opposing sources")
            self.ingest([*opposing[:3], *followup[:3]])
            self.extract(limit=2)
            self.stage("challenging", "Testing the strongest alternative and revising or rejecting the mechanism")
            challenge = self.calls.model(Challenge, self.payload() | {"hypothesis": hypothesis.model_dump(mode="json"), "opposing_query": hypothesis.opposing_query}, stage="challenging", instruction="Challenge the proposed mechanism using all evidence. Mark refuted if contradicted. Mark unresolved if scope, acquisitions, seasonality or missing evidence could explain the relationship. Select only directly relevant eligible source passage IDs; lack of search results does not establish absence of counterevidence. Retain only a qualified observation if the stronger inference fails.")
            self.store.artifact(self.run_id, "challenge", challenge.model_dump(mode="json"))
            self.progress(iteration + 1)
            if challenge.refuted:
                self.limitations.append(f"Candidate rejected: {challenge.reason}")
                continue
            relevant = [p for p in self.passages if p.id in challenge.relevant_passage_ids]
            origins = {d.origin_family_id for d in self.documents if d.cutoff_eligibility == "eligible" and d.id in {p.document_id for p in relevant}}
            if len(origins) < 2:
                self.limitations.append("Candidate lacked independently originated relevant evidence.")
                continue
            self.stage("composing", "Drafting all eight required discovery fields from verified artifacts")
            draft = self.calls.model(DiscoveryDraft, self.payload() | {"hypothesis": hypothesis.model_dump(mode="json"), "challenge": challenge.model_dump(mode="json")}, stage="composing", instruction="Write a qualified discovery headline, 3–5 significance statements and the strongest counterargument. Every factual statement must cite supplied supporting fact/passage IDs and calculation IDs where numerical. Include independently originated relevant context. State an observable future condition that would falsify the relationship, with no invented numeric threshold. Use the challenged qualification. No investment advice.")
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
                            generation_metadata={"pipeline": "extract-bind-calculate-hypothesize-investigate-challenge-review", "model_id": self.settings.openai_model_research, "search_queries": self.queries},
                            claims=claims, timeline_events=timeline, calculations=[c for c in self.calculations if c.id in used_calcs], facts=[f for f in self.facts if f.id in used_facts], passages=[p for p in self.passages if p.id in used_passages], documents=documents))
