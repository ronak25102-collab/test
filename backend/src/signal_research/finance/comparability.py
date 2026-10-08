from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ComparableKey:
    entity_id: str
    scope: str
    segment: str
    definition_id: str
    currency: str | None
    period_type: str


@dataclass(frozen=True)
class Comparability:
    eligible: bool
    reasons: tuple[str, ...]


def check_comparability(
    left: dict,
    right: dict,
    *,
    require_same_period_length: bool = True,
) -> Comparability:
    reasons: list[str] = []
    for key in ("scope", "segment", "definition_id", "currency", "period_type"):
        if left.get(key) != right.get(key):
            reasons.append(f"{key} mismatch")
    if require_same_period_length:
        left_days = _days(left.get("period_start"), left.get("period_end"))
        right_days = _days(right.get("period_start"), right.get("period_end"))
        if left_days is not None and right_days is not None and left_days != right_days:
            reasons.append("period length mismatch")
    if left.get("entity_id") != right.get("entity_id") and not left.get("peer_comparison"):
        reasons.append("different entity without peer-comparison permission")
    return Comparability(not reasons, tuple(reasons))


def _days(start: date | None, end: date | None) -> int | None:
    if start is None or end is None:
        return None
    return (end - start).days


def scope_key(fact: dict) -> ComparableKey:
    return ComparableKey(
        str(fact["entity_id"]),
        str(fact["scope"]),
        str(fact.get("segment", "all")),
        str(fact["definition_id"]),
        fact.get("currency"),
        str(fact["period_type"]),
    )
