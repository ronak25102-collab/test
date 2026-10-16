from concurrent.futures import ThreadPoolExecutor

from signal_research.domain.errors import BudgetExceeded
from signal_research.worker.budgets import Budget


def test_parallel_reservations_cannot_overrun_the_shared_budget():
    budget = Budget(5, 5, 5, 0)
    def reserve(_):
        try:
            budget.reserve('search_calls')
            return 1
        except BudgetExceeded:
            return 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(40))) == 5
    assert budget.snapshot()['search_calls'] == 5


def test_provider_deadline_preserves_the_optional_extraction_reserve(store, settings, monkeypatch):
    from datetime import UTC, date, datetime, timedelta

    from pydantic import BaseModel
    from signal_research.domain.enums import RunMode
    from signal_research.providers.llm.openai_provider import OpenAIProvider
    from signal_research.worker.calls import DurableCalls
    settings.allow_unknown_cost = True
    settings.openai_api_key = 'test'
    settings.openai_model_extract = settings.openai_model_research = 'test-model'
    settings.stage_request_seconds = {}
    settings.stage_output_tokens = {'normalizing': 2048}
    settings.model_request_timeout_seconds = 300
    rid = store.create_run(store.search_companies('HDFCBANK')[0], date(2026, 10, 16), RunMode.LIVE)
    store.lease_next('reserved-window')
    budget = Budget(5, 5, 5, 0, deadline=datetime.now(UTC) + timedelta(seconds=100))
    calls = DurableCalls(store, settings, rid, budget)
    calls.deadline_reserve_seconds = 90
    class Answer(BaseModel):
        supported: bool
    def generate(self, schema, messages, role, deadline, outputs):
        assert 0 < deadline.total_seconds() <= 10
        assert outputs == 2048
        return schema(supported=True), type('Usage', (), {'input_tokens': 10, 'output_tokens': 10})()
    monkeypatch.setattr(OpenAIProvider, 'generate', generate)
    assert calls.model(Answer, {}, role='extract', stage='normalizing').supported


def test_tiny_remaining_window_does_not_send_or_reserve_provider_request(store, settings, monkeypatch):
    from datetime import UTC, date, datetime, timedelta

    import pytest
    from pydantic import BaseModel
    from signal_research.domain.enums import RunMode
    from signal_research.providers.llm.openai_provider import OpenAIProvider
    from signal_research.worker.calls import DurableCalls
    settings.allow_unknown_cost = True
    settings.openai_api_key = 'test'
    settings.openai_model_research = 'test-model'
    rid = store.create_run(store.search_companies('HDFCBANK')[0], date(2026, 10, 16), RunMode.LIVE)
    store.lease_next('tiny-window')
    budget = Budget(5, 5, 5, 0, deadline=datetime.now(UTC) + timedelta(seconds=1))
    class Answer(BaseModel):
        supported: bool
    def unexpected(*args, **kwargs):
        raise AssertionError('No request should be sent')
    monkeypatch.setattr(OpenAIProvider, 'generate', unexpected)
    with pytest.raises(BudgetExceeded, match='no request sent'):
        DurableCalls(store, settings, rid, budget).model(Answer, {}, stage='composing')
    assert budget.model_calls == 0
    assert store.provider_calls(rid) == []
