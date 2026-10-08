from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from signal_research.domain.enums import PeriodType, Scope
from signal_research.domain.schemas import StrictModel


class ExtractedFactCandidate(StrictModel):
    evidence_quote: str | None = None
    metric_key: str
    value_raw: str
    unit_raw: str | None = None
    currency: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    period_type: PeriodType = PeriodType.INSTANT
    scope: Scope
    segment: str = "all"
    passage_id: UUID
    extraction_confidence: Decimal = Field(ge=0, le=1)


class ExtractedFactBatch(StrictModel):
    facts: list[ExtractedFactCandidate] = Field(default_factory=list, max_length=20)
    missing_metrics: list[str] = Field(default_factory=list, max_length=30)
    notes: list[str] = Field(default_factory=list, max_length=10)
