from datetime import date

import httpx
import pytest
from signal_research.providers.search.tavily_provider import TavilySearchProvider
from signal_research.settings import Settings


@pytest.mark.parametrize("domains,topic", [(["issuer.example"], "general"), (None, "general")])
def test_issuer_search_uses_broad_index_and_retains_cutoff(monkeypatch, domains, topic):
    requests = []
    def post(url, **kwargs):
        requests.append(kwargs["json"])
        return httpx.Response(200, json={"results": []}, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", post)
    assert TavilySearchProvider(Settings(tavily_api_key="test-only")).search(
        '"Example Company" annual report 2026', domains, date(2026, 10, 8), 6,
    ) == []
    assert requests[0]["topic"] == topic
    assert requests[0]["search_depth"] == "basic"
    assert requests[0]["end_date"] == "2026-10-08"
    assert requests[0]["include_domains"] == (domains or [])
