from __future__ import annotations

from decimal import Decimal

from signal_research.finance.units import parse_numeric


def normalize_fact_value(value_raw: str, unit_raw: str | None) -> tuple[Decimal | None, str | None]:
    """Return the source-scale numeric value and a normalized unit hint.

    Monetary facts remain in their disclosed scale. Converting INR crore to
    rupees here would make the dashboard harder to audit, so the metric
    registry determines the canonical display unit.
    """
    parsed = parse_numeric(value_raw)
    if parsed.value is None:
        return None, parsed.missing_reason
    return parsed.value, unit_raw
