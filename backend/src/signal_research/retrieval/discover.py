from __future__ import annotations

from datetime import date

from signal_research.providers.search.base import SearchHit, SearchProvider


def discover_sources(provider: SearchProvider, queries: list[str], domains: list[str], as_of: date, max_queries: int = 6) -> list[SearchHit]:
    """Run bounded lead discovery and deduplicate URLs before fetching."""
    hits: list[SearchHit] = []
    seen: set[str] = set()
    for query in queries[:max_queries]:
        for hit in provider.search(query, domains, as_of, 6):
            if hit.url not in seen:
                seen.add(hit.url)
                hits.append(hit)
    return hits
