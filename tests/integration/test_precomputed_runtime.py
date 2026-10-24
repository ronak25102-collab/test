"""Playback mechanics use explicitly synthetic temporary reports, never research fixtures."""
import json
import socket
from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from signal_research.domain.enums import RunMode
from signal_research.main import create_app
from signal_research.precomputed import runtime
from signal_research.precomputed.builder import FIXTURE_DIR, read_json
from signal_research.precomputed.catalog import PrecomputedUnavailable, load_report
from signal_research.precomputed.guard import (
    PrecomputedNetworkForbidden,
    offline_playback,
    require_network_allowed,
)
from signal_research.research.report_builder import build_synthetic_report
from signal_research.research.verifier import verify_report
from signal_research.settings import Settings
from signal_research.worker.machine import ResearchMachine


@pytest.fixture
def offline_app(tmp_path):
    settings = Settings(pipeline_mode="precomputed", replay_duration_seconds=120,
                        database_url=f"sqlite:///{tmp_path / 'offline.db'}", data_dir=tmp_path,
                        precomputed_dir=tmp_path / "fixtures", auto_start_worker=False)
    settings.precomputed_dir.mkdir()
    app = create_app(settings)
    with TestClient(app) as client:
        company = app.state.store.search_companies("HDFCBANK")[0]
        report = build_synthetic_report(uuid4(), company, date(2026, 10, 8))
        verify_report(report)
        (settings.precomputed_dir / "HDFCBANK.json").write_text(report.model_dump_json(), encoding="utf-8")
        (settings.precomputed_dir / "index.json").write_text(json.dumps({"companies": [{"symbol": "HDFCBANK"}]}), encoding="utf-8")
        yield client, app.state.store, settings, report


def forbid_network(*args, **kwargs):
    raise AssertionError("outbound network attempted during playback")


def fake_clock(monkeypatch, store, run_id, initial=0, on_sleep=None):
    clock = {"elapsed": initial}

    def now():
        return runtime.aware(store.get_summary(run_id).started_at) + timedelta(seconds=clock["elapsed"])

    def sleep(seconds):
        assert not store.has_report(run_id), "report was published before the full duration"
        if on_sleep:
            on_sleep(clock["elapsed"])
        clock["elapsed"] += seconds

    monkeypatch.setattr(runtime, "now", now)
    monkeypatch.setattr(runtime.time, "sleep", sleep)
    monkeypatch.setattr(socket, "create_connection", forbid_network)
    monkeypatch.setattr(socket, "getaddrinfo", forbid_network)
    return clock


def test_playback_duration_zero_network_remap_and_endpoints(offline_app, monkeypatch):
    client, store, settings, fixture = offline_app
    assert client.get("/api/v1/health/configuration").json()["ready"]
    response = client.post("/api/v1/runs", json={"company_id": str(fixture.company.id), "as_of": "2026-10-08"}, headers={"Idempotency-Key": "offline-once"})
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    assert client.post("/api/v1/runs", json={"company_id": str(fixture.company.id), "as_of": "2026-10-08"}, headers={"Idempotency-Key": "offline-once"}).json()["run_id"] == run_id
    assert client.get(f"/api/v1/runs/{run_id}/report").status_code == 409
    assert str(store.lease_next("offline-worker")) == run_id
    clock = fake_clock(monkeypatch, store, run_id)
    ResearchMachine(store, settings).process(run_id)
    assert clock["elapsed"] >= 120
    report = store.get_report(run_id)
    assert report is not None
    verify_report(report)
    assert report.run_id != fixture.run_id
    assert {f.id for f in report.facts}.isdisjoint(f.id for f in fixture.facts)
    assert report.generation_metadata["mode"] == "precomputed"
    assert report.generation_metadata["models_used"] == []
    assert report.generation_metadata["precomputed_provenance"]["source_verification_digest"] == fixture.generation_metadata["verification_digest"]
    assert store.get_summary(run_id).budget["model_calls"] == 0
    assert client.get(f"/api/v1/runs/{run_id}/report").status_code == 200
    for claim in report.claims:
        assert client.get(f"/api/v1/claims/{claim.id}?run_id={run_id}").status_code == 200
    for calculation in report.calculations:
        assert client.get(f"/api/v1/calculations/{calculation.id}?run_id={run_id}").status_code == 200
    for document in report.documents:
        assert client.get(f"/api/v1/documents/{document.id}/passages?run_id={run_id}").status_code == 200
    for suffix in ("report.html", "report.json", "facts.csv", "evidence.zip"):
        assert client.get(f"/api/v1/runs/{run_id}/exports/{suffix}").status_code == 200
    assert client.get("/api/v1/runs/history").json()["items"][0]["id"] == run_id
    events = client.get(f"/api/v1/runs/{run_id}/events").json()["items"]
    assert [e["sequence"] for e in events] == list(range(1, len(events) + 1))
    assert not any("Searching" in e["public_summary"] for e in events)


def test_cancel_resume_retains_start_and_duration(offline_app, monkeypatch):
    _, store, settings, fixture = offline_app
    run_id = store.create_run(fixture.company, fixture.cutoff, RunMode.LIVE)
    assert store.lease_next("first") == run_id
    clock = fake_clock(monkeypatch, store, run_id, on_sleep=lambda elapsed: store.request_cancel(run_id) if elapsed >= 20 else None)
    ResearchMachine(store, settings).process(run_id)
    started = store.get_summary(run_id).started_at
    assert store.get_summary(run_id).status == "cancelled"
    assert not store.has_report(run_id)
    store.resume(run_id)
    store.lease_next("resumed")
    fake_clock(monkeypatch, store, run_id, initial=clock["elapsed"])
    settings.replay_duration_seconds = 0
    resumed = {"last": 0}
    original_remap = runtime.remap_report

    def checked_remap(*args):
        resumed["last"] = args[3]
        return original_remap(*args)

    monkeypatch.setattr(runtime, "remap_report", checked_remap)
    ResearchMachine(store, settings).process(run_id)
    assert store.get_summary(run_id).started_at == started
    assert resumed["last"] >= 120
    assert store.has_report(run_id)
    markers = [e.event_type for e in store.get_events(run_id) if e.event_type.startswith("precomputed_step_")]
    assert len(markers) == len(set(markers))


def test_wrong_issuer_and_early_cutoff_never_substitute(offline_app):
    client, store, settings, fixture = offline_app
    with pytest.raises(PrecomputedUnavailable):
        load_report(settings, fixture.company, date(2025, 1, 1))
    company = store.search_companies("ICICIBANK")[0]
    response = client.post("/api/v1/runs", json={"company_id": str(company.id), "as_of": "2026-10-08"})
    assert response.status_code == 404
    assert response.json()["code"] == "UNSUPPORTED_SECTOR"


def test_guard_blocks_every_provider_and_fetch(tmp_path):
    from signal_research.providers.llm.codecraft_provider import CodeCraftProvider
    from signal_research.providers.llm.gemini_provider import GeminiProvider
    from signal_research.providers.llm.nvidia_provider import NvidiaProvider
    from signal_research.providers.llm.openai_provider import OpenAIProvider
    from signal_research.providers.search.account import fetch_free_account_usage
    from signal_research.providers.search.tavily_provider import TavilySearchProvider
    from signal_research.retrieval.fetch import PublicFetcher

    settings = Settings(pipeline_mode="precomputed")
    with offline_playback():
        for provider in (CodeCraftProvider, GeminiProvider, NvidiaProvider, OpenAIProvider):
            with pytest.raises(PrecomputedNetworkForbidden):
                provider(settings).generate(None, [], "research", timedelta(seconds=1), 10)
        with pytest.raises(PrecomputedNetworkForbidden):
            TavilySearchProvider(settings).search("test", [], date.today(), 1)
        with pytest.raises(PrecomputedNetworkForbidden):
            PublicFetcher(tmp_path).fetch("https://example.com")
        with pytest.raises(PrecomputedNetworkForbidden):
            fetch_free_account_usage(settings)
    require_network_allowed()


@pytest.mark.parametrize('symbol', [entry['symbol'] for entry in
                                  read_json(FIXTURE_DIR / 'index.json')['companies']])
def test_real_fixture_report_evidence_exports_and_history(symbol, tmp_path, monkeypatch):
    settings = Settings(pipeline_mode='precomputed', replay_duration_seconds=120,
        database_url=f'sqlite:///{tmp_path / "real.db"}', data_dir=tmp_path)
    app = create_app(settings)
    with TestClient(app) as client:
        # Preserve the socket type used by Windows' local event-loop transport;
        # reject network connection attempts and DNS instead of replacing it.
        monkeypatch.setattr(socket.socket, 'connect', forbid_network)
        monkeypatch.setattr(socket.socket, 'connect_ex', forbid_network)
        monkeypatch.setattr(socket, 'getaddrinfo', forbid_network)
        resolved = client.post('/api/v1/companies/resolve', json={'query': symbol.lower()})
        assert resolved.status_code == 200
        company = resolved.json()['resolved']
        response = client.post('/api/v1/runs', json={'company_id': company['id'],
            'as_of': '2026-10-24'}, headers={'Idempotency-Key': symbol})
        assert response.status_code == 202
        run_id = response.json()['run_id']
        store = app.state.store
        assert str(store.lease_next('offline-real-fixture')) == run_id
        elapsed = {'value': 0}

        def clock():
            return runtime.aware(store.get_summary(run_id).started_at) + timedelta(seconds=elapsed['value'])

        def sleep(seconds):
            assert not store.has_report(run_id)
            elapsed['value'] += max(5, seconds)

        monkeypatch.setattr(runtime, 'now', clock)
        monkeypatch.setattr(runtime.time, 'sleep', sleep)
        # An already accepted precomputed run stays offline across a settings
        # change; execution policy and duration are pinned in existing config JSON.
        settings.pipeline_mode = 'live'
        settings.replay_duration_seconds = 0
        ResearchMachine(store, settings).process(run_id)
        assert elapsed['value'] >= 120
        report_response = client.get(f'/api/v1/runs/{run_id}/report')
        assert report_response.status_code == 200
        report = store.get_report(run_id)
        assert report.company.symbols == [symbol]
        assert report.generation_metadata['model_usage']['calls'] == 0
        assert store.historical_reports(report.company.id, report.cutoff) == []
        for claim in report.claims[:1]:
            assert client.get(f'/api/v1/claims/{claim.id}?run_id={run_id}').status_code == 200
        for calc in report.calculations[:1]:
            assert client.get(f'/api/v1/calculations/{calc.id}?run_id={run_id}').status_code == 200
        for doc in report.documents[:1]:
            assert client.get(f'/api/v1/documents/{doc.id}/passages?run_id={run_id}').status_code == 200
        for suffix in ['report.html', 'report.json', 'facts.csv', 'evidence.zip']:
            assert client.get(f'/api/v1/runs/{run_id}/exports/{suffix}').status_code == 200
        assert any(r['id'] == run_id for r in client.get('/api/v1/runs/history').json()['items'])


def test_offline_roster_resolves_names_symbols_aliases_without_keys(tmp_path, monkeypatch):
    settings = Settings(pipeline_mode='precomputed', database_url=f'sqlite:///{tmp_path / "names.db"}',
                        data_dir=tmp_path)
    app = create_app(settings)
    with TestClient(app) as client:
        monkeypatch.setattr(socket.socket, 'connect', forbid_network)
        monkeypatch.setattr(socket.socket, 'connect_ex', forbid_network)
        monkeypatch.setattr(socket, 'getaddrinfo', forbid_network)
        for entry in read_json(FIXTURE_DIR / 'roster.json')['companies']:
            for query in {entry['symbol'], entry['legal_name'], *entry['aliases']}:
                response = client.post('/api/v1/companies/resolve', json={'query': query.swapcase()})
                assert response.status_code == 200, (query, response.text)
                assert entry['symbol'] in response.json()['resolved']['symbols']
