from __future__ import annotations

from dataclasses import dataclass

from signal_research.db.repositories import Store
from signal_research.domain.schemas import Company
from signal_research.research.identity import normalize_name


class EntityResolutionError(ValueError):
    code = "COMPANY_AMBIGUOUS"


@dataclass(frozen=True)
class Resolution:
    company: Company | None
    candidates: list[Company]
    reason: str | None = None


def resolve(store: Store, query: str, refresh: bool = False) -> Resolution:
    candidates = store.search_companies(query)
    if candidates and refresh and any(not c.isin for c in candidates):
        # A matching seed name is not a complete exchange identity. Enrich it
        # from the public directory rather than treating the seed as final.
        from .universe import LISTED_URL, refresh_universe
        try:
            age = store.snapshot_age_days(LISTED_URL)
            if age is None or age > 7:
                store.save_universe_snapshot(refresh_universe(listed=True))
            candidates = store.search_companies(query)
        except Exception:
            pass  # Keep the known entity; exact filing ownership still needs verification.
    if not candidates and refresh:
        from .universe import LISTED_URL, NIFTY_URL, refresh_universe
        try:
            age = store.snapshot_age_days(NIFTY_URL)
            if age is None or age > 7:
                store.save_universe_snapshot(refresh_universe())
            candidates = store.search_companies(query)
            if not candidates:
                age = store.snapshot_age_days(LISTED_URL)
                if age is None or age > 7:
                    store.save_universe_snapshot(refresh_universe(listed=True))
                candidates = store.search_companies(query)
        except Exception as exc:
            return Resolution(None, [], f"Could not verify the entity against the public exchange directory: {exc}")
    if not candidates:
        return Resolution(None, [], "No listed financial-services entity matched the query")
    exact = [c for c in candidates if query.strip().upper() in {s.upper() for s in c.symbols}]
    if not exact:
        exact = [c for c in candidates if normalize_name(query) in
                 {normalize_name(name) for name in [c.legal_name, *c.aliases]}]
    if len(exact) == 1:
        candidates = exact
    if len(candidates) == 1:
        if not candidates[0].business_profiles:
            return Resolution(None, candidates, "Listed financial entity found, but its business profile needs verified disclosure evidence")
        return Resolution(candidates[0], candidates)
    return Resolution(None, candidates, "The query matched multiple entities")
