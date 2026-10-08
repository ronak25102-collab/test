from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID, uuid4

from signal_research.domain.enums import FactStatus, Profile
from signal_research.domain.schemas import Fact, Passage
from signal_research.finance.registry import METRICS
from signal_research.finance.units import parse_numeric

from .models import ExtractedFactCandidate


@dataclass(frozen=True)
class FactValidation:
    fact: Fact | None
    reason: str | None = None


def _digits(value: str) -> str:
    return re.sub(r"[^0-9.]", "", value)


def validate_candidate(
    candidate: ExtractedFactCandidate,
    passage: Passage,
    entity_id: UUID,
    profile: Profile,
) -> FactValidation:
    metric = METRICS.get(candidate.metric_key)
    if metric is None:
        return FactValidation(None, "metric is not registered")
    if profile not in metric.profiles:
        return FactValidation(None, "metric is not permitted for the routed profile")
    if candidate.passage_id != passage.id:
        return FactValidation(None, "candidate points to a different passage")
    normalized_text = _digits(passage.text)
    normalized_value = _digits(candidate.value_raw)
    if not normalized_value or normalized_value not in normalized_text:
        return FactValidation(None, "raw value does not occur in the cited passage")
    parsed = parse_numeric(candidate.value_raw)
    if parsed.value is None:
        return FactValidation(None, parsed.missing_reason or "value could not be parsed")
    unit = (candidate.unit_raw or "").lower()
    if metric.unit == "INR_crore" and "crore" not in unit and "cr" not in unit:
        return FactValidation(None, "monetary value lacks an explicit crore scale")
    if metric.unit == "percent" and not any(token in unit for token in ("%", "percent", "ratio")):
        return FactValidation(None, "percentage value lacks an explicit percentage or ratio label")
    if metric.unit == "INR_crore":
        currency = candidate.currency or ("INR" if "inr" in unit or "₹" in unit else None)
        if currency != "INR":
            return FactValidation(None, "monetary value lacks explicit INR currency")
    else:
        currency = candidate.currency
    fact = Fact(
        id=uuid4(),
        entity_id=entity_id,
        metric_key=candidate.metric_key,
        value_raw=candidate.value_raw,
        value_decimal=parsed.value,
        unit_raw=candidate.unit_raw,
        unit_normalized=metric.unit,
        currency=currency,
        period_start=candidate.period_start,
        period_end=candidate.period_end,
        period_type=candidate.period_type,
        scope=candidate.scope,
        segment=candidate.segment,
        definition_id=f"{candidate.metric_key}_as_reported_v1",
        passage_id=passage.id,
        status=FactStatus.VERIFIED,
        extraction_confidence=candidate.extraction_confidence,
    )
    return FactValidation(fact)
