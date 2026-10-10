from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid5

from signal_research.domain.enums import FactStatus, Profile
from signal_research.domain.schemas import Fact, Passage
from signal_research.finance.registry import METRICS
from signal_research.finance.units import parse_numeric, to_inr_crore

from .bank_tables import month_end_columns, scope_in_text, subsidiary_only
from .models import ExtractedFactCandidate


@dataclass(frozen=True)
class FactValidation:
    fact: Fact | None
    reason: str | None = None


def date_in_text(value: date | None, text: str, *, allow_month_end: bool = False) -> bool:
    if value is None:
        return False
    normalized = re.sub(r"(?<=\d)(?:st|nd|rd|th)\b", "", text.lower())
    normalized = re.sub(r"[,.]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    formats = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y")
    for fmt in formats:
        expected = re.sub(r"[,.]", " ", value.strftime(fmt).lower())
        expected = re.sub(r"\s+", " ", expected).lstrip("0")
        if re.search(r"(?<!\w)0?" + re.escape(expected) + r"(?!\w)", normalized):
            return True
    return allow_month_end and any(period == value for _, period in month_end_columns(text))


def numeric_token_present(raw: str, text: str) -> bool:
    value = parse_numeric(raw).value
    if value is None:
        return False
    return any(parse_numeric(token).value == value for token in re.findall(r"(?<![\w.])(?:\(?-?\d[\d,]*(?:\.\d+)?\)?)(?![\w.])", text))


def validate_candidate(
    candidate: ExtractedFactCandidate,
    passage: Passage,
    entity_id: UUID,
    profile: Profile,
    entity_name: str | None = None,
) -> FactValidation:
    metric = METRICS.get(candidate.metric_key)
    if metric is None:
        return FactValidation(None, "metric is not registered")
    if profile not in metric.profiles:
        return FactValidation(None, "metric is not permitted for the routed profile")
    expected_period_type = "instant" if metric.kind == "stock" else "duration"
    if candidate.period_type.value != expected_period_type:
        return FactValidation(None, "period type does not match the registered metric definition")
    if candidate.period_type.value == "instant" and candidate.period_start is not None:
        return FactValidation(None, "an instant balance cannot have a duration start")
    if candidate.passage_id != passage.id:
        return FactValidation(None, "candidate points to a different passage")
    text = passage.text
    if candidate.evidence_quote:
        if candidate.evidence_quote not in passage.text:
            return FactValidation(None, "evidence quote is not an exact source span")
        text = candidate.evidence_quote
    lowered = text.lower()
    if subsidiary_only(text):
        return FactValidation(None, "passage reports a subsidiary or sponsored bank, not issuer totals")
    aliases = (*metric.aliases, metric.key.replace("_", " "))
    if not any(re.search(r"\b" + re.escape(alias.lower()) + r"\b", lowered) for alias in aliases):
        return FactValidation(None, "metric label is absent from the cited span")
    if not numeric_token_present(candidate.value_raw, text):
        return FactValidation(None, "raw value does not occur in the cited passage")
    if candidate.metric_key == "gross_advances" and re.search(r"\bnet\s+advances\b", text, re.I) and not re.search(r"\bgross\s+(?:advances|loans)\b", text, re.I):
        return FactValidation(None, "net advances cannot establish gross advances")
    if not date_in_text(candidate.period_end, text, allow_month_end=profile == Profile.BANK and candidate.period_type.value == "instant"):
        return FactValidation(None, "period end is absent from the cited span")
    if candidate.period_type.value == "duration" and not date_in_text(candidate.period_start, text):
        return FactValidation(None, "duration start is absent from the cited span")
    if not scope_in_text(candidate.scope, text):
        return FactValidation(None, "scope is absent from the cited span")
    if candidate.segment != "all" and candidate.segment.lower() not in lowered:
        return FactValidation(None, "segment is absent from the cited span")
    if entity_name and entity_name.lower() not in passage.text.lower():
        return FactValidation(None, "entity is absent from the cited passage")
    parsed = parse_numeric(candidate.value_raw)
    if parsed.value is None:
        return FactValidation(None, parsed.missing_reason or "value could not be parsed")
    unit = (candidate.unit_raw or "").lower()
    value = parsed.value
    if metric.unit == "INR_crore":
        scale = next((s for s in ("crore", "lakh", "million", "billion", "thousand", "rupees") if re.search(r"\b" + s + r"s?\b", unit)), None)
        if scale is None and re.fullmatch(r"(?:(?:inr|rs\.?|\u20b9)\s*)?(?:in\s*)?['\u2018\u2019]?000", unit.strip()):
            scale = "thousand"
        if scale is None and re.search(r"\bcr\b", unit):
            scale = "crore"
        source_scale = scale if scale != "crore" else "(?:crores?|cr)"
        source_thousands = scale == "thousand" and bool(re.search(r"\bin\s*['\u2018\u2019]?000\b", lowered))
        if not scale or not (source_thousands or re.search(r"\b" + source_scale + r"s?\b", lowered)):
            return FactValidation(None, "monetary scale is absent from the source")
        value = to_inr_crore(value, "INR " + scale if scale != "rupees" else "rupees")
    if metric.unit == "percent" and (not any(token in unit for token in ("%", "percent")) or not any(token in lowered for token in ("%", "percent"))):
        return FactValidation(None, "percentage value lacks an explicit percentage or ratio label")
    if metric.unit == "INR_crore":
        currency = candidate.currency or ("INR" if "inr" in unit or "₹" in unit else None)
        if currency != "INR" or not re.search(r"\b(inr|rs|rupees)\b|₹", lowered):
            return FactValidation(None, "monetary value lacks explicit INR currency")
    else:
        currency = candidate.currency
    fact = Fact(
        id=uuid5(passage.id, f"{entity_id}|{candidate.metric_key}|{candidate.period_start}|{candidate.period_end}|{candidate.scope}|{candidate.segment}|{parsed.value}"),
        entity_id=entity_id,
        metric_key=candidate.metric_key,
        value_raw=candidate.value_raw,
        value_decimal=value,
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
