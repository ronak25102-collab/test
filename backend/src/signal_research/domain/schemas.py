from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from .enums import (
    ClaimKind,
    DatePrecision,
    EvidenceRelation,
    EvidenceStrength,
    FactStatus,
    MissingReason,
    PeriodType,
    Profile,
    PublicationStatus,
    ResearchOutcome,
    RunMode,
    RunStatus,
    Scope,
    VerificationStatus,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Company(StrictModel):
    id: UUID
    legal_name: str
    symbols: list[str] = Field(default_factory=list)
    isin: str | None = None
    exchange: str | None = None
    aliases: list[str] = Field(default_factory=list)
    verified_ir_domains: list[str] = Field(default_factory=list)
    business_profiles: list[Profile] = Field(default_factory=list)
    identity_source_ids: list[UUID] = Field(default_factory=list)
    universe_snapshot_age_days: int | None = None


class UniverseSnapshot(StrictModel):
    id: UUID
    source_url: HttpUrl
    fetched_at: datetime
    content_hash: str
    constituents: list[dict[str, Any]]
    membership_effective_date: date | None = None
    is_cached: bool = False


class SourceDocument(StrictModel):
    id: UUID
    canonical_url: HttpUrl
    final_url: HttpUrl
    publisher: str
    origin_family_id: str
    title: str
    document_type: str
    published_at: datetime | None = None
    retrieved_at: datetime
    period_start: date | None = None
    period_end: date | None = None
    content_hash: str
    mime_type: str
    local_object_key: str | None = None
    access_status: str = "ok"
    cutoff_eligibility: str = "eligible"
    cutoff_eligibility_basis: Literal["publication_date", "verified_retrieval", "unknown"] = "publication_date"


class Passage(StrictModel):
    id: UUID
    document_id: UUID
    page_index: int | None = None
    printed_page_label: str | None = None
    section: str | None = None
    table_id: str | None = None
    row_label: str | None = None
    column_label: str | None = None
    text: str
    character_start: int | None = None
    character_end: int | None = None
    extraction_method: str = "html"
    extraction_quality: str = "good"


class Fact(StrictModel):
    id: UUID
    entity_id: UUID
    metric_key: str
    value_raw: str | None = None
    value_decimal: Decimal | None = None
    unit_raw: str | None = None
    unit_normalized: str | None = None
    currency: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    period_type: PeriodType
    scope: Scope
    segment: str = "all"
    accounting_basis: str = "issuer_reported"
    definition_id: str
    passage_id: UUID | None = None
    status: FactStatus = FactStatus.CANDIDATE
    missing_reason: MissingReason | None = None
    restates_fact_id: UUID | None = None
    extraction_confidence: Decimal | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_missingness(self) -> Fact:
        if self.value_decimal is None and self.missing_reason is None:
            raise ValueError("a missing fact must include missing_reason")
        if self.value_decimal is not None and self.missing_reason is not None:
            raise ValueError("a populated fact cannot include missing_reason")
        if self.status == FactStatus.VERIFIED and self.passage_id is None:
            raise ValueError("a verified fact requires a passage")
        return self


class Calculation(StrictModel):
    id: UUID
    formula_id: str
    formula_version: str
    input_fact_ids: list[UUID]
    parameters: dict[str, str | int | Decimal] = Field(default_factory=dict)
    output_value: Decimal | None = None
    unit: str | None = None
    period: str | None = None
    scope: Scope | None = None
    precision: int = 2
    comparability_checks: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    available: bool = True


class EvidenceLink(StrictModel):
    claim_id: UUID
    passage_or_fact_id: UUID
    relation: EvidenceRelation
    reason: str
    entailment_status: VerificationStatus = VerificationStatus.PENDING


class Claim(StrictModel):
    id: UUID
    run_id: UUID
    text: str
    kind: ClaimKind
    material: bool = True
    evidence_links: list[EvidenceLink] = Field(default_factory=list)
    calculation_ids: list[UUID] = Field(default_factory=list)
    verification_status: VerificationStatus = VerificationStatus.PENDING
    verification_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def material_claim_is_traceable(self) -> Claim:
        if self.material and self.verification_status == VerificationStatus.SUPPORTED:
            if not any(x.relation == EvidenceRelation.SUPPORTING for x in self.evidence_links):
                raise ValueError("a supported material claim needs supporting evidence")
        return self


class TimelineEvent(StrictModel):
    id: UUID
    event_date: date | None = None
    date_precision: DatePrecision = DatePrecision.UNKNOWN
    published_at: datetime | None = None
    description: str
    claim_ids: list[UUID] = Field(default_factory=list)
    source_ids: list[UUID] = Field(default_factory=list)


class FalsificationRule(StrictModel):
    id: UUID
    observable_metric_or_event: str
    operator: str
    threshold: Decimal | None = None
    unit: str | None = None
    required_periods: int = 1
    expected_source_type: str
    interpretation: str
    dependencies: list[UUID] = Field(default_factory=list)


class Counterargument(StrictModel):
    statement: str
    evidence_claim_ids: list[UUID] = Field(default_factory=list)
    search_attempted: bool = False
    search_summary: str
    unresolved: bool = False


class WhyItMatters(StrictModel):
    text: str
    claim_id: UUID


class Discovery(StrictModel):
    id: UUID
    discovery_sentence: str
    why_it_matters: list[WhyItMatters] = Field(min_length=3, max_length=5)
    evidence_claim_ids: list[UUID] = Field(min_length=1)
    timeline_event_ids: list[UUID] = Field(min_length=1)
    calculation_ids: list[UUID] = Field(default_factory=list)
    calculation_explanation: str | None = None
    counterargument: Counterargument
    falsification_rules: list[FalsificationRule] = Field(min_length=1)
    evidence_strength: EvidenceStrength
    strength_rationale: str

    @model_validator(mode="after")
    def calculation_requirement(self) -> Discovery:
        if not self.calculation_ids and not self.calculation_explanation:
            raise ValueError("discovery needs a relevant calculation or explicit explanation")
        return self


class Abstention(StrictModel):
    attempted_angles: list[str]
    missing_requirements: list[str]
    strongest_unconfirmed_lead: str | None = None
    next_evidence_needed: list[str]


class ResearchReport(StrictModel):
    schema_version: str = "1.0"
    run_id: UUID
    company: Company
    cutoff: date
    historical_coverage: str
    source_coverage: dict[str, Any]
    outcome: ResearchOutcome
    publication_status: PublicationStatus
    discoveries: list[Discovery] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    generation_metadata: dict[str, Any] = Field(default_factory=dict)
    claims: list[Claim] = Field(default_factory=list)
    timeline_events: list[TimelineEvent] = Field(default_factory=list)
    calculations: list[Calculation] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    documents: list[SourceDocument] = Field(default_factory=list)
    passages: list[Passage] = Field(default_factory=list)
    abstention: Abstention | None = None

    @model_validator(mode="after")
    def validate_report(self) -> ResearchReport:
        if self.publication_status == PublicationStatus.PUBLISHED:
            if self.outcome != ResearchOutcome.DISCOVERY or not self.discoveries:
                raise ValueError("published report needs a discovery outcome")
        if self.outcome == ResearchOutcome.INSUFFICIENT_EVIDENCE:
            if self.discoveries or self.abstention is None:
                raise ValueError("abstention reports cannot contain discoveries")
        claim_ids = {c.id for c in self.claims}
        timeline_ids = {e.id for e in self.timeline_events}
        calc_ids = {c.id for c in self.calculations}
        fact_ids = {f.id for f in self.facts}
        passage_ids = {p.id for p in self.passages}
        for discovery in self.discoveries:
            if not set(discovery.evidence_claim_ids) <= claim_ids:
                raise ValueError("discovery references an unknown claim")
            if not set(discovery.timeline_event_ids) <= timeline_ids:
                raise ValueError("discovery references an unknown timeline event")
            if not set(discovery.calculation_ids) <= calc_ids:
                raise ValueError("discovery references an unknown calculation")
            if not set(discovery.evidence_claim_ids).issubset({c.id for c in self.claims if c.verification_status == VerificationStatus.SUPPORTED}):
                raise ValueError("discovery references an unsupported claim")
        for claim in self.claims:
            for link in claim.evidence_links:
                if link.passage_or_fact_id not in fact_ids | passage_ids:
                    raise ValueError("claim references unknown evidence")
        return self


class ErrorEnvelope(StrictModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class RunCreate(StrictModel):
    company_id: UUID
    as_of: date
    mode: RunMode = RunMode.LIVE
    cold_start: bool = False


class ResolveRequest(StrictModel):
    query: str = Field(min_length=1, max_length=200)


class RunSummary(StrictModel):
    id: UUID
    company: Company
    as_of: date
    mode: RunMode
    cold_start: bool = False
    status: RunStatus
    outcome: ResearchOutcome | None = None
    stage: str
    progress: dict[str, int] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    ended_at: datetime | None = None


class RunEvent(StrictModel):
    sequence: int
    timestamp: datetime
    stage: str
    event_type: str
    public_summary: str
    artifact_ids: list[UUID] = Field(default_factory=list)
    duration_ms: int | None = None
    error_code: str | None = None
