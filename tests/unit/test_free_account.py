import pytest
from signal_research.evidence.duplicates import near_duplicate
from signal_research.providers.search.account import FreeQuotaUnavailable, remaining_free_credits


def test_quota_checks_are_shared_and_searches_reserve_conservatively(tmp_path, monkeypatch):
    from signal_research.providers.search.account import free_account_usage
    from signal_research.settings import Settings
    requests = []
    def fetch(settings):
        requests.append(True)
        return 2
    monkeypatch.setattr('signal_research.providers.search.account.fetch_free_account_usage', fetch)
    settings = Settings(data_dir=tmp_path, tavily_api_key='test-only')
    assert free_account_usage(settings) == 2
    assert free_account_usage(settings, reserve=1) == 2
    assert free_account_usage(settings, reserve=1) == 1
    with pytest.raises(FreeQuotaUnavailable):
        free_account_usage(settings, reserve=1)
    assert len(requests) == 1


def test_free_quota_exhaustion_and_key_limits():
    payload = {"account": {"current_plan": "Researcher", "plan_limit": 1000, "plan_usage": 128},
               "key": {"limit": None, "usage": 128}}
    assert remaining_free_credits(payload) == 872
    payload["key"]["limit"] = 130
    assert remaining_free_credits(payload) == 2
    payload["account"]["plan_usage"] = 1000
    assert remaining_free_credits(payload) == 0


def test_stale_provider_usage_cannot_refund_uncertain_search_reservations(tmp_path, monkeypatch):
    import sqlite3

    from signal_research.providers.search.account import free_account_usage
    from signal_research.settings import Settings
    monkeypatch.setattr('signal_research.providers.search.account.fetch_free_account_usage', lambda _: 5)
    settings = Settings(data_dir=tmp_path, tavily_api_key='test-only')
    assert free_account_usage(settings, reserve=1) == 5
    with sqlite3.connect(tmp_path / 'free-quota.db') as connection:
        connection.execute('UPDATE quota SET verified=0')
    assert free_account_usage(settings) == 4


@pytest.mark.parametrize('account', [{}, {'current_plan': 'Project'},
    {'current_plan': 'Researcher', 'plan_limit': True, 'plan_usage': 0}])
def test_unverified_or_paid_plan_is_rejected(account):
    with pytest.raises(FreeQuotaUnavailable):
        remaining_free_credits({'account': account})


def test_duplicate_comparison_is_bounded_and_not_just_shared_branding():
    report = ' '.join(f'financial word{i}' for i in range(15000))
    assert near_duplicate(report, report + ' Republished with permission')
    assert not near_duplicate(report, 'Unrelated publisher reporting a different financial event')
