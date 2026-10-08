from __future__ import annotations

from dataclasses import dataclass

from signal_research.db.repositories import Store
from signal_research.domain.schemas import Company


class EntityResolutionError(ValueError):
    code = "COMPANY_AMBIGUOUS"


@dataclass(frozen=True)
class Resolution:
    company: Company | None
    candidates: list[Company]
    reason: str | None = None


def resolve(store: Store, query: str) -> Resolution:
    candidates = store.search_companies(query)
    if not candidates:
        return Resolution(None, [], "No listed financial-services entity matched the query")
    if len(candidates) == 1:
        return Resolution(candidates[0], candidates)
    exact = [c for c in candidates if query.strip().upper() in {s.upper() for s in c.symbols}]
    if len(exact) == 1:
        return Resolution(exact[0], candidates)
    return Resolution(None, candidates, "The query matched multiple entities")
