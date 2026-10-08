from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SearchHit:
    url: str
    title: str
    snippet: str
    rank: int
    provider: str
    published_at: date | None = None


class SearchProvider:
    def search(self, query: str, domains: list[str] | None, as_of: date, max_results: int) -> list[SearchHit]:
        raise NotImplementedError
