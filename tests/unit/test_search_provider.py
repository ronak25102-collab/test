from datetime import date

import httpx
import pytest
from signal_research.providers.search.tavily_provider import (
    SearchQuotaExceeded,
    TavilySearchProvider,
)
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


@pytest.mark.parametrize('status', [432,433])
def test_search_plan_rejection_is_typed_and_never_retried(monkeypatch,status):
    requests = []
    def post(url,**kwargs):
        requests.append(url)
        return httpx.Response(status,json={'error':'provider detail'},request=httpx.Request('POST',url))
    monkeypatch.setattr(httpx,'post',post)
    with pytest.raises(SearchQuotaExceeded,match='Tavily search allowance') as failure:
        TavilySearchProvider(Settings(tavily_api_key='private-test-value')).search('test',None,date(2026,10,17),6)
    assert len(requests)==1 and failure.value.code=='SEARCH_PLAN_LIMIT'
    assert 'private-test-value' not in str(failure.value)
