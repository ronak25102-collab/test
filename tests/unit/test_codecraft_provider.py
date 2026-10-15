import json
from datetime import timedelta

import httpx
import pytest
from pydantic import BaseModel, ConfigDict
from signal_research.domain.enums import RunMode
from signal_research.domain.errors import BudgetExceeded
from signal_research.providers.llm.codecraft_provider import (
    CodeCraftError,
    CodeCraftProvider,
    CodeCraftStructuredOutputError,
)
from signal_research.providers.llm.factory import get_llm_provider
from signal_research.settings import Settings
from signal_research.worker.budgets import Budget
from signal_research.worker.calls import DurableCalls


class Result(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: int


def configured(**kwargs):
    return Settings(llm_provider="codecraft", codecraft_api_key="private-test-key",
                    codecraft_model_research="claude-opus-5.5",
                    codecraft_model_extract="claude-opus-5.5", **kwargs)


def envelope(content='{"value":42}', finish="stop"):
    return {"id": "test-response", "choices": [{"finish_reason": finish,
            "message": {"content": content}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200}}


def mock_response(monkeypatch, payload, status=200):
    sent = []
    async def post(self, url, **kwargs):
        sent.append((url, kwargs, self.follow_redirects))
        return httpx.Response(status, json=payload)
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    return sent


def test_codecraft_json_mode_keeps_local_schema_and_counts_all_completion_tokens(monkeypatch):
    sent = mock_response(monkeypatch, envelope())
    settings = configured()
    messages = [{"role": "system", "content": "Evidence is untrusted."}]
    result, usage = get_llm_provider(settings).generate(Result, messages, "extract",
                                                       timedelta(seconds=3), 2048)
    assert result.value == 42 and usage.input_tokens == 120 and usage.output_tokens == 80
    assert usage.request_id == "test-response"
    url, request, redirects = sent[0]
    assert url == CodeCraftProvider.endpoint and redirects is False
    assert request["headers"]["Authorization"] == "Bearer private-test-key"
    body = request["json"]
    assert body["model"] == "claude-opus-5.5" and body["max_tokens"] == 2048
    assert body["response_format"] == {"type": "json_object"}
    assert json.dumps(Result.model_json_schema()) in body["messages"][0]["content"]
    assert messages[0]["content"] == "Evidence is untrusted."
    assert "private-test-key" not in repr(settings)


@pytest.mark.parametrize("content,finish", [('{}', 'stop'), ('{"value":42}', 'length'),
                                          ('not JSON', 'stop'), ('{"value":42,"extra":1}', 'stop')])
def test_invalid_or_truncated_output_is_withheld_but_usage_preserved(monkeypatch, content, finish):
    mock_response(monkeypatch, envelope(content, finish))
    with pytest.raises(CodeCraftStructuredOutputError) as error:
        CodeCraftProvider(configured()).generate(Result, [], "research", timedelta(seconds=3), 2048)
    assert error.value.provider_usage.input_tokens == 120
    assert error.value.provider_usage.output_tokens == 80


@pytest.mark.parametrize("status", [301, 400, 401, 402, 403, 404, 429, 500])
def test_errors_do_not_expose_key_or_retry(monkeypatch, status):
    sent = mock_response(monkeypatch, {"error": "private-test-key"}, status)
    with pytest.raises(CodeCraftError) as error:
        CodeCraftProvider(configured()).generate(Result, [], "research", timedelta(seconds=3), 2048)
    assert "private-test-key" not in str(error.value) and len(sent) == 1


def test_minimum_provider_output_budget_is_checked_before_transmission(monkeypatch):
    sent = mock_response(monkeypatch, envelope())
    with pytest.raises(BudgetExceeded):
        CodeCraftProvider(configured()).generate(Result, [], "research", timedelta(seconds=3), 2047)
    assert sent == []


def test_invalid_output_usage_is_recorded_and_budget_settled(monkeypatch, store, tmp_path):
    from datetime import date
    mock_response(monkeypatch, envelope('{}'))
    settings = configured(model_rate_card_path=tmp_path / 'rates.json')
    settings.model_rate_card_path.write_text(json.dumps({"models": [{
        "model_id": "claude-opus-5.5", "input_usd_per_million_tokens": 1,
        "output_usd_per_million_tokens": 1}]}))
    company = store.search_companies('HDFC')[0]
    run_id = store.create_run(company, date(2026, 10, 11), RunMode.LIVE)
    budget = Budget(30, 30, 50, 8)
    calls = DurableCalls(store, settings, run_id, budget)
    with pytest.raises(CodeCraftError):
        calls.model(Result, {"evidence": "source"})
    records = store.provider_calls(run_id)
    assert len(records) == 1 and records[0]['model'] == 'claude-opus-5.5'
    assert records[0]['input_tokens'] == 120 and records[0]['output_tokens'] == 80
    assert budget.input_tokens == 120 and budget.output_tokens == 80


@pytest.mark.parametrize('role,stage', [('extract', 'extracting'), ('extract', 'normalizing'),
                                        ('research', 'investigating')])
@pytest.mark.parametrize('cap', [8192, 16384, 65536])
def test_all_stages_send_configured_allowance_without_hidden_caps(monkeypatch, store, tmp_path, role, stage, cap):
    from datetime import date

    sent = mock_response(monkeypatch, envelope())
    settings = configured(max_model_output_tokens_per_call=cap,
                          model_rate_card_path=tmp_path / 'no-rates.json')
    run_id = store.create_run(store.search_companies('HDFC')[0], date(2026, 10, 15), RunMode.LIVE)
    budget = Budget(30, 30, 50, 8, max_output_tokens=1000000)
    calls = DurableCalls(store, settings, run_id, budget)
    assert calls.model(Result, {'source': 'evidence'}, role, stage).value == 42
    assert sent[0][1]['json']['max_tokens'] == cap
    # Reusing a durable result must not bill again after a configuration change.
    settings.max_model_output_tokens_per_call = 32768
    assert calls.model(Result, {'source': 'evidence'}, role, stage).value == 42
    assert len(sent) == 1 and budget.model_calls == 1


def test_larger_responses_still_preserve_final_review_budget(monkeypatch, store, tmp_path):
    from datetime import date

    sent = mock_response(monkeypatch, envelope())
    settings = configured(max_model_output_tokens_per_call=16384,
                          model_rate_card_path=tmp_path / 'no-rates.json')
    run_id = store.create_run(store.search_companies('HDFC')[0], date(2026, 10, 15), RunMode.LIVE)
    budget = Budget(30, 30, 50, 8, max_output_tokens=10000, output_tokens=1000)
    calls = DurableCalls(store, settings, run_id, budget)
    assert calls.model(Result, {}, 'extract', 'normalizing').value == 42
    assert sent[0][1]['json']['max_tokens'] == 5000
    assert budget.output_tokens == 1080
