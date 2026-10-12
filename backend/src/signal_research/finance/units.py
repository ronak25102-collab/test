from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class ParsedNumber:
    raw: str
    value: Decimal | None
    unit: str | None
    missing_reason: str | None = None


_SCALE = {
    "rupees": (Decimal("1"), "INR"),
    "inr": (Decimal("1"), "INR"),
    "lakh": (Decimal("100000"), "INR"),
    "lakhs": (Decimal("100000"), "INR"),
    "crore": (Decimal("10000000"), "INR"),
    "crores": (Decimal("10000000"), "INR"),
    "million": (Decimal("1000000"), "INR"),
    "millions": (Decimal("1000000"), "INR"),
    "billion": (Decimal("1000000000"), "INR"),
    "billions": (Decimal("1000000000"), "INR"),
}


def parse_numeric(raw: str | None, unit: str | None = None) -> ParsedNumber:
    """Parse Indian grouping, parentheses and source missing markers.

    A dash is missing, never zero. The original text is always preserved.
    """
    original = "" if raw is None else str(raw).strip()
    if not original or original.lower() in {"-", "—", "–", "na", "n/a", "nm", "not disclosed"}:
        return ParsedNumber(original, None, unit, "not_disclosed")
    text = original.replace("₹", "").replace("%", "").strip()
    text = re.sub(r"[†*‡#,\s]", "", text)
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    multiplier = Decimal("1")
    canonical = unit
    lowered = text.lower()
    for label, (scale, currency) in _SCALE.items():
        if lowered.endswith(label):
            text = text[: -len(label)].strip()
            multiplier = scale
            canonical = "INR" if (unit or "").lower() in {"inr", "rupees", ""} else unit
            break
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        return ParsedNumber(original, None, unit, "ambiguous")
    if not value.is_finite():
        return ParsedNumber(original, None, unit, "ambiguous")
    if negative:
        value = -value
    if unit and unit.lower() in {"inr crore", "inr_crore", "₹ crore"}:
        value *= Decimal("10000000")
        canonical = "INR"
    elif unit and unit.lower() in {"inr lakh", "inr_lakh"}:
        value *= Decimal("100000")
        canonical = "INR"
    elif unit and unit.lower() in {"percent", "%"}:
        canonical = "percent"
    elif unit and unit.lower() in {"bps", "basis points"}:
        canonical = "bps"
    return ParsedNumber(original, value * multiplier, canonical or unit)


def to_inr_crore(value: Decimal, unit: str) -> Decimal:
    normalized = unit.lower().replace("_", " ")
    if normalized in {"inr crore", "crore", "inr_crore"}:
        return value
    if normalized in {"inr lakh", "lakh"}:
        return value / Decimal("100")
    if normalized in {"inr million", "million"}:
        return value / Decimal("10")
    if normalized in {"inr billion", "billion"}:
        return value * Decimal("100")
    if normalized in {"inr trillion", "trillion", "inr lakh crore", "lakh crore"}:
        return value * Decimal("100000")
    if normalized in {"inr thousand", "inr thousands", "thousand", "thousands"}:
        return value / Decimal("10000")
    if normalized in {"inr", "rupees"}:
        return value / Decimal("10000000")
    raise ValueError(f"unsupported monetary unit: {unit}")


def percentage_change(current: Decimal, prior: Decimal) -> Decimal:
    if prior <= 0:
        raise ValueError("ordinary percentage growth requires a positive base")
    return (current / prior - Decimal("1")) * Decimal("100")


def display_decimal(value: Decimal | None, places: int = 2) -> str | None:
    if value is None:
        return None
    return f"{value:.{places}f}"
