from datetime import date

import pytest
from signal_research.domain.enums import RunMode
from signal_research.research.live import LiveResearch
from signal_research.worker.budgets import Budget
from signal_research.worker.machine import ResearchMachine


def test_cold_start_policy_is_durable_and_does_not_read_history(store, settings, monkeypatch):
    company = store.search_companies('HDFCBANK')[0]
    rid = store.create_run(company, date(2026, 10, 15), RunMode.LIVE, 'cold-request', cold_start=True)
    assert store.get_summary(rid).cold_start
    with pytest.raises(ValueError, match='cache policy'):
        store.create_run(company, date(2026, 10, 15), RunMode.LIVE, 'cold-request', cold_start=False)
    settings.cold_start = True
    research = LiveResearch(ResearchMachine(store, settings), rid, company, date(2026, 10, 15), Budget(10, 10, 10, 0))
    monkeypatch.setattr(store, 'historical_reports', lambda *a: pytest.fail('Cold rehearsal must not read previous reports'))
    research.load_historical_cache()
    assert research.facts == [] and research.history_cache == []
