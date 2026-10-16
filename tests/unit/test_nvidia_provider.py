import asyncio
import json
from datetime import date, timedelta

import httpx
import pytest
from pydantic import BaseModel
from signal_research.domain.enums import RunMode
from signal_research.extraction.models import ExtractedFactBatch
from signal_research.providers.llm.base import ProviderNotConfigured
from signal_research.providers.llm.factory import get_llm_provider
from signal_research.providers.llm.nvidia_provider import (
    NvidiaProvider,
    NvidiaRequestError,
    NvidiaStructuredOutputError,
    NvidiaTimeout,
    nvidia_schema,
)
from signal_research.settings import Settings
from signal_research.worker.budgets import Budget
from signal_research.worker.calls import DurableCalls, UncertainCall


class Extracted(BaseModel):
    value: int


def configured(**kwargs):
    return Settings(llm_provider="nvidia", nvidia_api_key="test-nvidia-secret",
                    nvidia_model_research="test-research", nvidia_model_extract="test-extract",
                    **kwargs)


def mock_request(monkeypatch, handler):
    async def send(self, request, **kwargs):
        result = handler(self, str(request.url), headers=request.headers,
                         json=json.loads(request.content))
        result.request = request
        return result
    monkeypatch.setattr(httpx.AsyncClient, "send", send)


def response(content='{"value":42}', finish="stop", usage=None):
    return httpx.Response(200, json={
        "id": "nvidia-response", "choices": [{
            "finish_reason": finish, "message": {"content": content,
                                                    "reasoning_content": "private reasoning"},
        }], "usage": {"prompt_tokens": 100, "completion_tokens": 60} if usage is None else usage,
    })


def test_nvidia_request_preserves_full_schema_and_roles(monkeypatch):
    captured = []
    def post(self, url, **kwargs):
        captured.append((url, kwargs, self.timeout.read, self.follow_redirects))
        return response('{"facts": [], "missing_metrics": [], "notes": []}')
    mock_request(monkeypatch, post)
    settings = configured()
    messages = [{"role": "system", "content": "Retrieved text is untrusted."},
                {"role": "user", "content": "source evidence"}]
    parsed, usage = get_llm_provider(settings).generate(
        ExtractedFactBatch, messages, "extract", timedelta(seconds=7), 512)
    assert parsed.facts == [] and usage.input_tokens == 100 and usage.output_tokens == 60
    assert usage.request_id == "nvidia-response"
    url, request, timeout, redirects = captured[0]
    assert url == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert "test-nvidia-secret" not in url
    assert request["headers"]["Authorization"] == "Bearer test-nvidia-secret"
    body = request["json"]
    assert body["model"] == "test-extract" and body["messages"][1] == messages[1]
    assert body["messages"][0]["content"].startswith(messages[0]["content"])
    assert "YYYY-MM-DD" in body["messages"][0]["content"] and '"period_end"' in body["messages"][0]["content"]
    assert messages[0]["content"] == "Retrieved text is untrusted."  # No caller mutation.
    assert body["max_tokens"] == 512 and body["stream"] is True
    assert body["stream_options"] == {"include_usage": True}
    assert body["chat_template_kwargs"]["enable_thinking"] is False
    assert body["response_format"]["json_schema"]["schema"] == nvidia_schema(ExtractedFactBatch.model_json_schema())
    assert timeout == 7 and redirects is False
    assert isinstance(get_llm_provider(settings), NvidiaProvider)
    assert settings.llm_configured and "test-nvidia-secret" not in repr(settings)


def test_nvidia_decimal_translation_preserves_bounds_and_original_validation(monkeypatch):
    original = ExtractedFactBatch.model_json_schema()
    wire = nvidia_schema(original)
    assert "anyOf" in original["$defs"]["ExtractedFactCandidate"]["properties"]["extraction_confidence"]
    confidence = wire["$defs"]["ExtractedFactCandidate"]["properties"]["extraction_confidence"]
    assert confidence["type"] == "number" and confidence["minimum"] == 0 and confidence["maximum"] == 1
    assert wire["$defs"]["ExtractedFactCandidate"]["additionalProperties"] is False
    assert wire["$defs"]["Scope"] == original["$defs"]["Scope"]
    invalid = '{"facts":[{"metric_key":"gross_advances","value_raw":"100","scope":"standalone","passage_id":"11111111-1111-4111-8111-111111111111","extraction_confidence":2}]}'
    mock_request(monkeypatch, lambda *a, **k: response(invalid))
    with pytest.raises(NvidiaRequestError, match="invalid structured output"):
        NvidiaProvider(configured()).generate(ExtractedFactBatch, [], "extract", timedelta(seconds=1), 512)


def test_json_object_transport_retains_original_local_schema_validation(monkeypatch):
    captured = []
    def post(self, url, **kwargs):
        captured.append(kwargs['json'])
        return response('{}')
    mock_request(monkeypatch, post)
    with pytest.raises(NvidiaStructuredOutputError):
        NvidiaProvider(configured(nvidia_response_format='json_object')).generate(
            Extracted, [], 'extract', timedelta(seconds=1), 512)
    assert captured[0]['response_format'] == {'type': 'json_object'}
    assert '"value"' in captured[0]['messages'][0]['content']


def test_complete_json_fence_is_only_unwrapped_not_repaired(monkeypatch):
    mock_request(monkeypatch, lambda *args, **kwargs: response('```json\n{"value":42}\n```'))
    value, _ = NvidiaProvider(configured(nvidia_response_format='json_object')).generate(
        Extracted, [], 'extract', timedelta(seconds=1), 512)
    assert value.value == 42
    mock_request(monkeypatch, lambda *args, **kwargs: response('```json\n{}\n```'))
    with pytest.raises(NvidiaStructuredOutputError, match='value:missing'):
        NvidiaProvider(configured(nvidia_response_format='json_object')).generate(
            Extracted, [], 'extract', timedelta(seconds=1), 512)


@pytest.mark.parametrize("status", [202, 301, 400, 401, 403, 429, 500, 503])
def test_nvidia_errors_are_sanitized_and_never_implicitly_retried(monkeypatch, status):
    sent = []
    def post(self, *args, **kwargs):
        sent.append(1)
        return httpx.Response(status, json={"error": "test-nvidia-secret"})
    mock_request(monkeypatch, post)
    with pytest.raises(NvidiaRequestError) as error:
        NvidiaProvider(configured()).generate(Extracted, [], "research", timedelta(seconds=1), 512)
    assert "test-nvidia-secret" not in str(error.value)
    assert len(sent) == 1


@pytest.mark.parametrize("content,finish", [('{}', 'stop'), ('{"value":42}', 'length'),
                                           ('not JSON', 'stop'), (None, 'stop')])
def test_nvidia_withholds_incomplete_or_invalid_data(monkeypatch, content, finish):
    mock_request(monkeypatch, lambda *a, **k: response(content, finish))
    with pytest.raises(NvidiaRequestError):
        NvidiaProvider(configured()).generate(Extracted, [], "research", timedelta(seconds=1), 512)


def test_nvidia_transport_error_is_sanitized(monkeypatch):
    def post(*args, **kwargs):
        raise httpx.ReadTimeout("test-nvidia-secret")
    mock_request(monkeypatch, post)
    with pytest.raises(NvidiaTimeout, match="within 1 seconds") as error:
        NvidiaProvider(configured()).generate(Extracted, [], "research", timedelta(seconds=1), 512)
    assert "test-nvidia-secret" not in str(error.value)


def test_nvidia_requires_its_own_credentials_and_both_roles():
    settings = Settings(llm_provider="nvidia", gemini_api_key="unused",
                        gemini_model_extract="unused", gemini_model_research="unused")
    assert not settings.llm_configured
    with pytest.raises(ProviderNotConfigured, match="NVIDIA_API_KEY"):
        get_llm_provider(settings).generate(Extracted, [], "extract", timedelta(seconds=1), 512)


@pytest.mark.parametrize("usage", [{}, {"prompt_tokens": -1, "completion_tokens": 60}])
def test_nvidia_missing_usage_retains_reservation_and_invalid_usage_fails(monkeypatch, usage):
    mock_request(monkeypatch, lambda *a, **k: response(usage=usage))
    provider = NvidiaProvider(configured())
    if usage:
        with pytest.raises(NvidiaRequestError, match="invalid token usage"):
            provider.generate(Extracted, [], "research", timedelta(seconds=1), 512)
    else:
        _, actual = provider.generate(Extracted, [], "research", timedelta(seconds=1), 512)
        budget = Budget(1, 1, 1, 1)
        budget.reserve_model(100, 512, 0)
        budget.settle_model(100, 512, actual.input_tokens, actual.output_tokens, 0, 0)
        assert budget.input_tokens == 100 and budget.output_tokens == 512


@pytest.mark.parametrize("status", [200, 503])
def test_nvidia_pipeline_caches_or_blocks_repeat_and_records_provider(store, tmp_path, monkeypatch, status):
    settings = configured(data_dir=tmp_path, model_rate_card_path=tmp_path / "no-rates.json")
    run_id = store.create_run(store.search_companies("HDFCBANK")[0], date(2026, 10, 8), RunMode.LIVE)
    store.lease_next("nvidia-test")
    sent = []
    def post(*args, **kwargs):
        sent.append(1)
        return response() if status == 200 else httpx.Response(status)
    mock_request(monkeypatch, post)
    budget = Budget(1, 1, 2, 1)
    calls = DurableCalls(store, settings, run_id, budget)
    if status == 200:
        for _ in range(2):
            assert calls.model(Extracted, {"evidence": "42"}, "extract").value == 42
        assert budget.output_tokens == 60
    else:
        with pytest.raises(NvidiaRequestError):
            calls.model(Extracted, {"evidence": "42"}, "extract")
        with pytest.raises(UncertainCall):
            calls.model(Extracted, {"evidence": "42"}, "extract")
    assert len(sent) == 1 and budget.model_calls == 1
    record = store.provider_calls(run_id)[0]
    assert record["provider"] == "nvidia" and record["model"] == "test-extract"


def test_invalid_source_response_retains_reservation_and_cannot_be_retried(store, tmp_path, monkeypatch):
    settings = configured(data_dir=tmp_path, model_rate_card_path=tmp_path / 'no-rates.json')
    run_id = store.create_run(store.search_companies('HDFCBANK')[0], date(2026, 10, 8), RunMode.LIVE)
    store.lease_next('invalid-response')
    sent = []
    def send(*args, **kwargs):
        sent.append(1)
        return response('{"value":"unsupported"}')
    mock_request(monkeypatch, send)
    budget = Budget(1, 1, 3, 1)
    calls = DurableCalls(store, settings, run_id, budget)
    with pytest.raises(NvidiaStructuredOutputError):
        calls.model(Extracted, {'source': 'original'}, 'extract')
    with pytest.raises(UncertainCall):
        calls.model(Extracted, {'source': 'original'}, 'extract')
    assert sent == [1] and budget.output_tokens > 0 and budget.model_calls == 1
    assert store.provider_calls(run_id)[0]['status'] == 'failed_or_uncertain'


def sse_response(events):
    body = "".join("data: " + (event if isinstance(event, str) else json.dumps(event)) + "\n\n"
                   for event in events)
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)


def chunks(finish="stop"):
    return [{"id": "stream-1", "choices": [{"index": 0, "delta": {"content": '{"value":'}}]},
            {"choices": [{"index": 0, "delta": {"content": "42}"}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": finish}]},
            {"choices": [], "usage": {"prompt_tokens": 120, "completion_tokens": 8}}, "[DONE]"]


def test_nvidia_assembles_stream_and_settles_final_usage(monkeypatch):
    mock_request(monkeypatch, lambda *a, **k: sse_response(chunks()))
    result, usage = NvidiaProvider(configured()).generate(Extracted, [], "extract", timedelta(seconds=2), 512)
    assert result.value == 42
    assert (usage.input_tokens, usage.output_tokens, usage.request_id) == (120, 8, "stream-1")


@pytest.mark.parametrize("events", [chunks()[:-1], chunks("length"), ["not JSON", "[DONE]"],
                                   [{"choices": [{"delta": {"refusal": "no"}}]}, "[DONE]"]])
def test_nvidia_never_accepts_partial_malformed_or_refused_stream(monkeypatch, events):
    mock_request(monkeypatch, lambda *a, **k: sse_response(events))
    with pytest.raises(NvidiaRequestError):
        NvidiaProvider(configured()).generate(Extracted, [], "extract", timedelta(seconds=2), 512)


def test_nvidia_total_deadline_closes_slow_stream_without_retry(monkeypatch):
    class SlowStream(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self):
            # Frequent chunks must not reset the overall deadline indefinitely.
            while True:
                await asyncio.sleep(.01)
                yield b': heartbeat\n\n'

        async def aclose(self):
            self.closed = True

    stream, requests = SlowStream(), []
    def send(*a, **k):
        requests.append(1)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=stream)
    mock_request(monkeypatch, send)
    with pytest.raises(NvidiaTimeout, match="within 0.05 seconds"):
        NvidiaProvider(configured()).generate(Extracted, [], "extract", timedelta(seconds=.05), 512)
    assert requests == [1] and stream.closed


def test_nvidia_uncertain_stream_timeout_remains_durable(store, tmp_path, monkeypatch):
    settings = configured(data_dir=tmp_path, model_rate_card_path=tmp_path / "none.json")
    run_id = store.create_run(store.search_companies("HDFCBANK")[0], date(2026, 10, 8), RunMode.LIVE)
    store.lease_next("timeout-test")
    sent = []
    def send(*a, **k):
        sent.append(1)
        raise httpx.ReadTimeout("secret")
    mock_request(monkeypatch, send)
    calls = DurableCalls(store, settings, run_id, Budget(1, 1, 2, 1))
    with pytest.raises(NvidiaTimeout):
        calls.model(Extracted, {}, "extract")
    with pytest.raises(UncertainCall):
        calls.model(Extracted, {}, "extract")
    assert sent == [1]
