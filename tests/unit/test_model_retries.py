import json
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from pydantic import BaseModel
from signal_research.db.models import ProviderCallModel
from signal_research.domain.enums import RunMode
from signal_research.domain.errors import BudgetExceeded
from signal_research.providers.llm.gemini_provider import GeminiRequestError, GeminiUnavailable
from signal_research.settings import Settings
from signal_research.worker.budgets import Budget
from signal_research.worker.calls import DurableCalls, UncertainCall
from sqlalchemy import select


class Result(BaseModel):
    value: int


@pytest.fixture
def pipeline(store, tmp_path, monkeypatch):
    settings = Settings(llm_provider="gemini", gemini_api_key="test-secret",
                        gemini_model_research="test-model", data_dir=tmp_path,
                        model_rate_card_path=tmp_path / "rates.json",
                        max_model_output_tokens_per_call=400)
    settings.model_rate_card_path.write_text(json.dumps({"models": [{
        "model_id": "test-model", "input_usd_per_million_tokens": 1,
        "output_usd_per_million_tokens": 2,
    }]}))
    run_id = store.create_run(store.search_companies("HDFCBANK")[0], date(2026, 10, 8), RunMode.LIVE)
    store.lease_next("retry-test")
    monkeypatch.setattr("signal_research.worker.calls.sleep", lambda seconds: None)
    monkeypatch.setattr("signal_research.worker.calls.uniform", lambda *args: 0)
    return DurableCalls(store, settings, run_id, Budget(2, 2, 3, 1, max_output_tokens=850))


def install_responses(monkeypatch, responses):
    sent = []
    def post(self, url, **kwargs):
        sent.append(kwargs["json"])
        item = responses[len(sent) - 1]
        if isinstance(item, Exception):
            raise item
        return item
    monkeypatch.setattr(httpx.Client, "post", post)
    return sent


def success():
    return httpx.Response(200, json={
        "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": '{"value":42}'}]}}],
        "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 60},
    })


def attempts(pipeline):
    with pipeline.store.session_factory() as session:
        rows = session.scalars(select(ProviderCallModel).where(
            ProviderCallModel.run_id == str(pipeline.run_id)).order_by(ProviderCallModel.id)).all()
        return [(row.attempt, row.status, row.model) for row in rows]


def test_explicit_503_retries_once_and_resume_reuses_result(pipeline, monkeypatch):
    sent = install_responses(monkeypatch, [httpx.Response(503), success()])
    delays = []
    monkeypatch.setattr("signal_research.worker.calls.sleep", delays.append)
    assert pipeline.model(Result, {"data": "evidence"}).value == 42
    assert len(sent) == 2 and sent[0] == sent[1]
    assert delays == [2]
    assert pipeline.budget.model_calls == 2
    assert pipeline.budget.output_tokens == 460  # Rejected reservation remains charged.
    rejected_input = pipeline.budget.input_tokens - 100
    assert pipeline.budget.reserved_cost_usd == pytest.approx((rejected_input + 100 + 460 * 2) / 1_000_000)
    assert attempts(pipeline) == [(1, "rejected_http_503", "test-model"), (2, "ok", "test-model")]
    # Remaining allowance is now smaller than the original request. Stable planning
    # still finds the saved second attempt without billing or reserving again.
    resumed = DurableCalls(pipeline.store, pipeline.settings, pipeline.run_id, pipeline.budget)
    assert resumed.model(Result, {"data": "evidence"}).value == 42
    assert len(sent) == 2 and pipeline.budget.model_calls == 2


def test_persistent_503_stops_at_limit_and_is_not_resent_on_resume(pipeline, monkeypatch):
    sent = install_responses(monkeypatch, [httpx.Response(503), httpx.Response(503)])
    for _ in range(2):
        with pytest.raises(GeminiUnavailable):
            pipeline.model(Result, {"data": "evidence"})
    assert len(sent) == 2 and pipeline.budget.model_calls == 2
    assert attempts(pipeline) == [(1, "rejected_http_503", "test-model"), (2, "rejected_http_503", "test-model")]


@pytest.mark.parametrize("failure", [httpx.ReadTimeout("lost response"), httpx.ConnectError("connection failed")])
def test_uncertain_transport_failure_is_never_retried(pipeline, monkeypatch, failure):
    sent = install_responses(monkeypatch, [failure])
    with pytest.raises(GeminiRequestError, match="transport failed"):
        pipeline.model(Result, {"data": "evidence"})
    # Even with no remaining allowance, resume must recognize the uncertain call.
    pipeline.budget.max_output_tokens = pipeline.budget.output_tokens
    with pytest.raises(UncertainCall):
        pipeline.model(Result, {"data": "evidence"})
    assert len(sent) == 1 and pipeline.budget.model_calls == 1


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500])
def test_other_http_errors_are_not_retried(pipeline, monkeypatch, status):
    sent = install_responses(monkeypatch, [httpx.Response(status)])
    with pytest.raises(GeminiRequestError):
        pipeline.model(Result, {"data": "evidence"})
    assert len(sent) == 1 and attempts(pipeline) == [(1, "failed_or_uncertain", "test-model")]


@pytest.mark.parametrize("limit", ["model_calls", "output_tokens", "cost_usd"])
def test_retry_cannot_exceed_budgets(pipeline, monkeypatch, limit):
    sent = install_responses(monkeypatch, [httpx.Response(503)])
    if limit == "model_calls":
        pipeline.budget.max_model_calls = 1
    elif limit == "output_tokens":
        pipeline.budget.max_output_tokens = 600
    else:
        # Let the first request reserve, then prevent any further reservation.
        def sleep(seconds):
            pipeline.budget.max_cost_usd = pipeline.budget.reserved_cost_usd
        monkeypatch.setattr("signal_research.worker.calls.sleep", sleep)
    with pytest.raises(BudgetExceeded):
        pipeline.model(Result, {"data": "evidence"})
    assert len(sent) == 1 and pipeline.budget.model_calls == 1


def test_short_remaining_deadline_prevents_retry_wait(pipeline, monkeypatch):
    sent = install_responses(monkeypatch, [httpx.Response(503)])
    pipeline.budget.deadline = datetime.now(UTC) + timedelta(seconds=1)
    monkeypatch.setattr("signal_research.worker.calls.sleep", lambda seconds: pytest.fail("deadline too short to wait"))
    with pytest.raises(GeminiUnavailable):
        pipeline.model(Result, {"data": "evidence"})
    assert len(sent) == 1


def test_retry_can_be_disabled(pipeline, monkeypatch):
    pipeline.settings.gemini_max_attempts = 1
    sent = install_responses(monkeypatch, [httpx.Response(503)])
    with pytest.raises(GeminiUnavailable):
        pipeline.model(Result, {"data": "evidence"})
    assert len(sent) == 1


def test_successful_first_request_is_cached_after_allowance_changes(pipeline, monkeypatch):
    pipeline.settings.max_model_output_tokens_per_call = 8192
    sent = install_responses(monkeypatch, [success()])
    for _ in range(2):
        assert pipeline.model(Result, {"data": "evidence"}).value == 42
    assert len(sent) == 1
