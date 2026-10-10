from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, create_model

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


def source_fact_batch_schema(metric_keys: list[str], passage_id: UUID, period_dates: list[date] | None = None):
    """Keep the original passage; constrain generation to registered source bindings."""
    from signal_research.finance.registry import METRICS

    candidate = create_model("SourceFactCandidate", __base__=ExtractedFactCandidate,
        evidence_quote=(type(None), None),
        metric_key=(str, Field(json_schema_extra={"enum": metric_keys})),
        passage_id=(UUID, Field(json_schema_extra={"enum": [str(passage_id)]})))
    date_fields = {}
    if period_dates is not None:
        date_fields["period_end"] = (date, Field(json_schema_extra={"enum": [str(d) for d in period_dates]})) if period_dates else (type(None), None)
    stocks = [key for key in metric_keys if METRICS[key].kind == "stock"]
    durations = [key for key in metric_keys if METRICS[key].kind != "stock"]
    variants = []
    if stocks:
        variants.append(create_model("InstantSourceFact", __base__=candidate,
            **date_fields,
            metric_key=(Literal[tuple(stocks)], ...),
            period_type=(Literal[PeriodType.INSTANT], PeriodType.INSTANT), period_start=(type(None), None)))
    if durations:
        variants.append(create_model("DurationSourceFact", __base__=candidate,
            **date_fields,
            metric_key=(Literal[tuple(durations)], ...),
            period_type=(Literal[PeriodType.DURATION], PeriodType.DURATION), period_start=(date, ...)))
    fact_type = variants[0] if len(variants) == 1 else variants[0] | variants[1]
    return create_model("ExtractedFactBatch", __base__=ExtractedFactBatch,
        facts=(list[fact_type], Field(default_factory=list, max_length=6)))
