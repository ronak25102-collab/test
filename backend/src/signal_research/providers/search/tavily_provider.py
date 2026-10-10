from __future__ import annotations

from datetime import date, datetime
from email.utils import parsedate_to_datetime

import httpx

from signal_research.settings import Settings

from .base import SearchHit, SearchProvider


class SearchNotConfigured(RuntimeError):
    code = "PROVIDER_NOT_CONFIGURED"


class TavilySearchProvider(SearchProvider):
    endpoint = "https://api.tavily.com/search"

    def __init__(self, settings: Settings):
        self.settings = settings

    def search(self, query: str, domains: list[str] | None, as_of: date, max_results: int) -> list[SearchHit]:
        if not self.settings.tavily_api_key:
            raise SearchNotConfigured("TAVILY_API_KEY is not configured")
        # Official filings require the broad index; finance news alone can omit issuer sites.
        # General search includes original rating reports and regulatory PDFs.
        # Finance-only results repeatedly returned unrelated blocked news pages.
        topic = "general"
        response = httpx.post(self.endpoint, json={"api_key": self.settings.tavily_api_key, "query": query, "include_domains": domains or [], "max_results": min(max_results, 10), "search_depth": "basic", "topic": topic, "end_date": as_of.isoformat(), "include_published_date": True}, timeout=self.settings.source_request_timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        hits = []
        for index, item in enumerate(payload.get("results", []), 1):
            published = item.get("published_date")
            published_at = None
            if published:
                try:
                    published_at = datetime.fromisoformat(published.replace("Z", "+00:00")).date()
                except ValueError:
                    try:
                        published_at = parsedate_to_datetime(published).date()
                    except (TypeError, ValueError, OverflowError):
                        published_at = None
            hits.append(SearchHit(url=item["url"], title=item.get("title", ""), snippet=item.get("content", ""), rank=index, provider="tavily", published_at=published_at))
        return hits
