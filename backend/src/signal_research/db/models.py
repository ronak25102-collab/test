from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base


def now_utc() -> datetime:
    return datetime.now(UTC)


class CompanyModel(Base):
    __tablename__ = "companies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(300), index=True)
    symbols: Mapped[list[str]] = mapped_column(JSON, default=list)
    isin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(40), nullable=True)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    verified_ir_domains: Mapped[list[str]] = mapped_column(JSON, default=list)
    business_profiles: Mapped[list[str]] = mapped_column(JSON, default=list)
    identity_source_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class UniverseSnapshotModel(Base):
    __tablename__ = "universe_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_url: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    constituents: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    membership_effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_cached: Mapped[bool] = mapped_column(Boolean, default=False)


class ResearchRunModel(Base):
    __tablename__ = "research_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    as_of: Mapped[date] = mapped_column(Date, index=True)
    mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), index=True)
    outcome: Mapped[str | None] = mapped_column(String(40), nullable=True)
    stage: Mapped[str] = mapped_column(String(30), default="queued")
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    budget_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    progress_json: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    lease_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fencing_token: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True, unique=True)
    # Progress, leases and history only need the run metadata. Large evidence
    # payloads are loaded explicitly when a report or export is requested.
    report_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, deferred=True)
    report_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    company: Mapped[CompanyModel] = relationship()
    __table_args__ = (Index("ix_run_owner_created_at", "owner_user_id", "created_at"),)


class RunEventModel(Base):
    __tablename__ = "run_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    stage: Mapped[str] = mapped_column(String(30))
    event_type: Mapped[str] = mapped_column(String(50))
    public_summary: Mapped[str] = mapped_column(Text)
    artifact_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    __table_args__ = (UniqueConstraint("run_id", "sequence", name="uq_run_event_sequence"),)


class SourceDocumentModel(Base):
    __tablename__ = "source_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    canonical_url: Mapped[str] = mapped_column(Text)
    final_url: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str] = mapped_column(String(300))
    origin_family_id: Mapped[str] = mapped_column(String(300), index=True)
    title: Mapped[str] = mapped_column(Text)
    document_type: Mapped[str] = mapped_column(String(50))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    local_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_status: Mapped[str] = mapped_column(String(40), default="ok")
    cutoff_eligibility: Mapped[str] = mapped_column(String(30), default="eligible")
    cutoff_eligibility_basis: Mapped[str] = mapped_column(String(30), default="publication_date")


class PassageModel(Base):
    __tablename__ = "passages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"), index=True)
    page_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    printed_page_label: Mapped[str | None] = mapped_column(String(30), nullable=True)
    section: Mapped[str | None] = mapped_column(Text, nullable=True)
    table_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    row_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    column_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    character_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    character_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(30))
    extraction_quality: Mapped[str] = mapped_column(String(30))
    __table_args__ = (Index("ix_passage_document_text", "document_id"),)


class FactModel(Base):
    __tablename__ = "facts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    metric_key: Mapped[str] = mapped_column(String(100), index=True)
    value_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_decimal: Mapped[Numeric | None] = mapped_column(Numeric(38, 12), nullable=True)
    unit_raw: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit_normalized: Mapped[str | None] = mapped_column(String(100), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_type: Mapped[str] = mapped_column(String(20))
    scope: Mapped[str] = mapped_column(String(30))
    segment: Mapped[str] = mapped_column(String(200), default="all")
    accounting_basis: Mapped[str] = mapped_column(String(100))
    definition_id: Mapped[str] = mapped_column(String(200), index=True)
    passage_id: Mapped[str | None] = mapped_column(ForeignKey("passages.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    missing_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    restates_fact_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    __table_args__ = (Index("ix_fact_comparability", "entity_id", "scope", "segment", "definition_id", "currency", "period_type"),)


class CalculationModel(Base):
    __tablename__ = "calculations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), index=True)
    formula_id: Mapped[str] = mapped_column(String(100))
    formula_version: Mapped[str] = mapped_column(String(30))
    input_fact_ids: Mapped[list[str]] = mapped_column(JSON)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output_value: Mapped[Numeric | None] = mapped_column(Numeric(38, 12), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    period: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str | None] = mapped_column(String(30), nullable=True)
    precision: Mapped[int] = mapped_column(Integer, default=2)
    comparability_checks: Mapped[list[str]] = mapped_column(JSON, default=list)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list)
    available: Mapped[bool] = mapped_column(Boolean, default=True)


class StageCheckpointModel(Base):
    __tablename__ = "stage_checkpoints"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), index=True)
    stage: Mapped[str] = mapped_column(String(30))
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    input_hash: Mapped[str] = mapped_column(String(64))
    output_artifact_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    schema_version: Mapped[str] = mapped_column(String(30))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (UniqueConstraint("run_id", "stage", "iteration", name="uq_checkpoint"),)


class ProviderCallModel(Base):
    __tablename__ = "provider_calls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), index=True)
    stage: Mapped[str] = mapped_column(String(30))
    request_hash: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    search_credits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[Numeric | None] = mapped_column(Numeric(20, 8), nullable=True)
    cost_status: Mapped[str] = mapped_column(String(30), default="unknown")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30))
    __table_args__ = (UniqueConstraint("run_id", "request_hash", "attempt", name="uq_provider_idempotency"),)


class ArtifactModel(Base):
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), index=True)
    # Durable failover keys include a route signature and credential slot.
    kind: Mapped[str] = mapped_column(String(128), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    schema_version: Mapped[str] = mapped_column(String(30), default="1.0")


class ClaimModel(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("research_runs.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(30))
    material: Mapped[bool] = mapped_column(Boolean)
    verification_status: Mapped[str] = mapped_column(String(30))
    verification_reasons: Mapped[list[str]] = mapped_column(JSON)


class EvidenceLinkModel(Base):
    __tablename__ = "evidence_links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), index=True)
    fact_id: Mapped[str | None] = mapped_column(ForeignKey("facts.id"), nullable=True)
    passage_id: Mapped[str | None] = mapped_column(ForeignKey("passages.id"), nullable=True)
    relation: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    entailment_status: Mapped[str] = mapped_column(String(30))


class CalculationInputModel(Base):
    __tablename__ = "calculation_inputs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    calculation_id: Mapped[str] = mapped_column(ForeignKey("calculations.id"), index=True)
    fact_id: Mapped[str] = mapped_column(ForeignKey("facts.id"))
    position: Mapped[int] = mapped_column(Integer)


class ClaimCalculationModel(Base):
    __tablename__ = "claim_calculations"
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), primary_key=True)
    calculation_id: Mapped[str] = mapped_column(ForeignKey("calculations.id"), primary_key=True)


class WorkerHeartbeatModel(Base):
    __tablename__ = "worker_heartbeats"
    owner: Mapped[str] = mapped_column(String(100), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
