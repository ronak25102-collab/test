from __future__ import annotations

from decimal import Decimal

from signal_research.domain.schemas import Fact


def fact_value(fact: Fact) -> Decimal | None:
    return fact.value_decimal


def is_missing(fact: Fact) -> bool:
    return fact.value_decimal is None
