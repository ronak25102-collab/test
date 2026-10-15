import json
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from pydantic import BaseModel
from signal_research.domain.enums import RunMode
from signal_research.domain.errors import BudgetExceeded
from signal_research.providers.llm.base import ProviderNotConfigured, ProviderUsage
from signal_research.providers.llm.codecraft_provider import (
    CodeCraftCreditsExhausted,
    CodeCraftError,
)
from signal_research.providers.llm.nvidia_provider import NvidiaProvider
from signal_research.research.readiness import live_readiness
from signal_research.settings import Settings
from signal_research.worker.budgets import Budget
from signal_research.worker.calls import DurableCalls, UncertainCall


class Result(BaseModel):
    value: int


@pytest.fixture
def pipeline(store, tmp_path):
    settings = Settings(llm_provider='codecraft', codecraft_api_key='primary-test',
        codecraft_secondary_api_keys=['backup-one-test', 'backup-two-test'],
        codecraft_model_extract='cc-extract', codecraft_model_research='cc-research',
        codecraft_nvidia_fallback=True, nvidia_api_key='nvidia-test',
        nvidia_model_extract='nv-extract', nvidia_model_research='nv-research',
        tavily_api_key='search-test', search_usd_per_credit=0,
        model_rate_card_path=tmp_path / 'rates.json')
    settings.model_rate_card_path.write_text(json.dumps({'provider': 'codecraft', 'models': [
        {'model_id': model, 'input_usd_per_million_tokens': rate,
         'output_usd_per_million_tokens': rate}
        for model, rate in [('cc-extract', 8), ('cc-research', 8), ('nv-extract', 2), ('nv-research', 2)]
    ]}))
    run_id = store.create_run(store.search_companies('HDFC')[0], date(2026, 10, 15), RunMode.LIVE)
    store.lease_next('failover-test')
    return DurableCalls(store, settings, run_id, Budget(30, 30, 50, 8, max_output_tokens=1000000))


def codecraft_success():
    return httpx.Response(200, json={'choices': [{'finish_reason': 'stop',
        'message': {'content': '{"value":42}'}}],
        'usage': {'prompt_tokens': 120, 'completion_tokens': 80}})


def install_http(monkeypatch, handler):
    sent = []
    async def post(self, url, **kwargs):
        key = kwargs['headers']['Authorization'].removeprefix('Bearer ')
        sent.append(key)
        return handler(key)
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    return sent


def test_ordered_credit_failover_to_nvidia_and_resume_reuses_result(pipeline, monkeypatch):
    sent = install_http(monkeypatch, lambda _: httpx.Response(402))
    nvidia = []
    def generate(self, schema, messages, role, deadline, outputs):
        nvidia.append((self.settings.llm_provider, self.settings.model_for_role(role)))
        return schema(value=42), ProviderUsage(input_tokens=120, output_tokens=80)
    monkeypatch.setattr(NvidiaProvider, 'generate', generate)
    for _ in range(2):
        assert pipeline.model(Result, {'evidence': 'bounded'}, 'extract').value == 42
    assert sent == ['primary-test', 'backup-one-test', 'backup-two-test']
    assert nvidia == [('nvidia', 'nv-extract')]
    records = pipeline.store.provider_calls(pipeline.run_id)
    assert [r['status'] for r in records] == ['rejected_http_402'] * 3 + ['ok']
    assert all(r['input_tokens'] == r['output_tokens'] == 0 for r in records[:3])
    assert all(float(r['estimated_cost_usd']) == 0 for r in records[:3])
    assert records[-1]['provider'] == 'nvidia' and records[-1]['model'] == 'nv-extract'
    assert pipeline.budget.model_calls == 4
    assert pipeline.budget.input_tokens == 120 and pipeline.budget.output_tokens == 80
    assert pipeline.budget.reserved_cost_usd == pytest.approx(200 * 2 / 1_000_000)
    events = pipeline.store.get_events(pipeline.run_id)
    assert len([e for e in events if e.event_type == 'provider_fallback']) == 3
    public = json.dumps(pipeline.store.artifacts(pipeline.run_id), default=str) + str(events) + str(records)
    for secret in ['primary-test', 'backup-one-test', 'backup-two-test', 'nvidia-test']:
        assert secret not in public and secret not in repr(pipeline.settings)
    assert 'codecraft_secondary_api_keys' not in pipeline.settings.model_dump()


def test_exhausted_primary_is_skipped_for_new_payloads_and_other_model_role(pipeline, monkeypatch):
    sent = install_http(monkeypatch, lambda key: httpx.Response(402) if key == 'primary-test' else codecraft_success())
    assert pipeline.model(Result, {'evidence': 'one'}, 'extract').value == 42
    resumed = DurableCalls(pipeline.store, pipeline.settings, pipeline.run_id, pipeline.budget)
    assert resumed.model(Result, {'evidence': 'two'}, 'research').value == 42
    assert sent == ['primary-test', 'backup-one-test', 'backup-one-test']


@pytest.mark.parametrize('status', [400, 401, 403, 404, 429, 500, 503])
def test_rate_access_and_provider_errors_never_rotate_keys(pipeline, monkeypatch, status):
    sent = install_http(monkeypatch, lambda _: httpx.Response(status))
    with pytest.raises(CodeCraftError):
        pipeline.model(Result, {})
    with pytest.raises(UncertainCall):
        pipeline.model(Result, {})
    assert sent == ['primary-test']
    assert pipeline.budget.model_calls == 1 and pipeline.budget.output_tokens > 0


@pytest.mark.parametrize('finish', ['stop', 'length'])
def test_invalid_or_truncated_evidence_does_not_rotate_keys(pipeline, monkeypatch, finish):
    response = codecraft_success().json()
    response['choices'][0].update(finish_reason=finish, message={'content': '{}'})
    sent = install_http(monkeypatch, lambda _: httpx.Response(200, json=response))
    with pytest.raises(CodeCraftError):
        pipeline.model(Result, {})
    assert sent == ['primary-test']
    assert pipeline.budget.input_tokens == 120 and pipeline.budget.output_tokens == 80


def test_uncertain_backup_stays_pinned_even_after_another_operation_exhausts_it(pipeline, monkeypatch):
    def handler(key):
        if key == 'primary-test':
            return httpx.Response(402)
        raise httpx.ReadTimeout('response may have been billed')
    sent = install_http(monkeypatch, handler)
    with pytest.raises(CodeCraftError):
        pipeline.model(Result, {'operation': 'uncertain'})
    # A distinct operation later receives an explicit credit rejection for that
    # backup, then succeeds with the next key. The first operation is still unsafe.
    sent_later = install_http(monkeypatch, lambda key: httpx.Response(402) if key == 'backup-one-test' else codecraft_success())
    assert pipeline.model(Result, {'operation': 'other'}).value == 42
    resumed = DurableCalls(pipeline.store, pipeline.settings, pipeline.run_id, pipeline.budget)
    with pytest.raises(UncertainCall):
        resumed.model(Result, {'operation': 'uncertain'})
    assert sent == ['primary-test', 'backup-one-test']
    assert sent_later == ['backup-one-test', 'backup-two-test']


def test_all_codecraft_keys_exhausted_stops_without_retransmission(pipeline, monkeypatch):
    pipeline.settings.codecraft_nvidia_fallback = False
    sent = install_http(monkeypatch, lambda _: httpx.Response(402))
    for payload in ({}, {}, {'new': 'operation'}):
        with pytest.raises(CodeCraftCreditsExhausted):
            pipeline.model(Result, payload)
    assert sent == ['primary-test', 'backup-one-test', 'backup-two-test']
    assert pipeline.budget.input_tokens == pipeline.budget.output_tokens == 0


@pytest.mark.parametrize('stop', ['deadline', 'calls', 'cancelled'])
def test_failover_still_respects_shared_limits_and_cancellation(pipeline, monkeypatch, stop):
    def handler(key):
        if stop == 'deadline':
            pipeline.budget.deadline = datetime.now(UTC) - timedelta(seconds=1)
        elif stop == 'calls':
            pipeline.budget.max_model_calls = 1
        else:
            pipeline.store.request_cancel(pipeline.run_id)
        return httpx.Response(402)
    sent = install_http(monkeypatch, handler)
    with pytest.raises((BudgetExceeded, RuntimeError)):
        pipeline.model(Result, {})
    assert sent == ['primary-test']


def test_duplicate_keys_are_deduplicated(pipeline):
    pipeline.settings.codecraft_secondary_api_keys = ['primary-test', ' backup-one-test ', 'backup-one-test']
    routes = pipeline.settings.model_routes()
    assert [slot for slot, _ in routes] == ['codecraft:0', 'codecraft:1', 'nvidia']


def test_readiness_requires_fallback_models_and_prices(pipeline, monkeypatch):
    assert live_readiness(pipeline.settings)['ready']
    assert live_readiness(pipeline.settings)['codecraft_backup_keys'] == 2
    pipeline.settings.nvidia_api_key = ''
    assert not live_readiness(pipeline.settings)['ready']
    pipeline.settings.nvidia_api_key = 'nvidia-test'
    card = json.loads(pipeline.settings.model_rate_card_path.read_text())
    card['models'] = card['models'][:2]
    pipeline.settings.model_rate_card_path.write_text(json.dumps(card))
    assert not live_readiness(pipeline.settings)['ready']
    pipeline.rates = {r['model_id']: r for r in card['models']}
    sent = install_http(monkeypatch, lambda _: httpx.Response(402))
    with pytest.raises(ProviderNotConfigured, match='rate card'):
        pipeline.model(Result, {})
    assert len(sent) == 3
