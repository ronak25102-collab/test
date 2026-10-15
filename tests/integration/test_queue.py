from datetime import date

import pytest
from fastapi.testclient import TestClient
from signal_research.db.models import ResearchRunModel
from signal_research.domain.enums import RunMode, RunStatus
from signal_research.main import create_app


def test_clear_queue_preserves_active_and_terminal_runs_and_saved_work(store):
    company = store.search_companies("SYNTHBANK")[0]
    active = store.create_run(company, date(2026, 10, 8), RunMode.REPLAY)
    assert store.lease_next("queue-test") == active
    store.update_run(active, status=RunStatus.EXTRACTING, stage="extracting", started=True)
    before = store.get_summary(active).model_dump()
    waiting = [store.create_run(company, date(2026, 10, 8), RunMode.REPLAY) for _ in range(2)]
    store.checkpoint(waiting[0], "extracting", 0, {"saved": "evidence"})
    store.artifact(waiting[0], "queue_test", {"saved": "artifact"})
    terminals = {}
    for status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED):
        run_id = store.create_run(company, date(2026, 10, 8), RunMode.REPLAY)
        store.update_run(run_id, status=status, stage=status.value, ended=True)
        terminals[run_id] = store.get_summary(run_id).model_dump()

    assert store.queued_run_count() == 2
    assert set(store.clear_queue()) == {str(run_id) for run_id in waiting}
    assert store.queued_run_count() == 0
    assert store.clear_queue() == []
    assert store.get_summary(active).model_dump() == before
    for run_id, summary in terminals.items():
        assert store.get_summary(run_id).model_dump() == summary
    for run_id in waiting:
        summary = store.get_summary(run_id)
        assert summary.status == RunStatus.CANCELLED
        assert summary.stage == "cancelled"
        assert summary.ended_at is not None
        assert store.is_cancelled(run_id)
        events = store.get_events(run_id)
        assert len([event for event in events if event.event_type == "run_cancelled"]) == 1
        assert "clearing the queue" in events[-1].public_summary
        assert store.provider_calls(run_id) == []
    assert store.load_checkpoint(waiting[0], "extracting") == {"saved": "evidence"}
    assert store.artifacts(waiting[0], "queue_test")[0]["payload"] == {"saved": "artifact"}
    assert store.resume(waiting[0]) == "queued"
    assert store.queued_run_count() == 1


def test_queue_api_counts_clears_and_refreshes_existing_run(store, settings):
    application = create_app(settings, store_override=store)
    with TestClient(application) as client:
        company = store.search_companies("SYNTHBANK")[0]
        run_id = store.create_run(company, date(2026, 10, 8), RunMode.REPLAY)
        assert client.get("/api/v1/runs/queue").json() == {"queued_count": 1}
        response = client.post("/api/v1/runs/queue/clear")
        assert response.status_code == 200
        assert response.json() == {"cancelled_count": 1, "run_ids": [str(run_id)]}
        assert client.get("/api/v1/runs/queue").json() == {"queued_count": 0}
        assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "cancelled"
        assert client.post("/api/v1/runs/queue/clear").json() == {"cancelled_count": 0, "run_ids": []}
        assert store.lease_next("after-clear") is None


def test_sqlite_worker_cannot_lease_a_run_cleared_after_selection(store, monkeypatch):
    if store.session_factory.kw["bind"].dialect.name != "sqlite":
        pytest.skip("PostgreSQL uses row locks; this regression covers SQLite's ignored FOR UPDATE")
    company = store.search_companies("SYNTHBANK")[0]
    run_id = store.create_run(company, date(2026, 10, 8), RunMode.REPLAY)
    session_type = store.session_factory.class_
    original_scalar = session_type.scalar
    interleaved = []

    def clear_after_selection(session, *args, **kwargs):
        result = original_scalar(session, *args, **kwargs)
        if isinstance(result, ResearchRunModel) and result.status == "queued" and not interleaved:
            interleaved.append(True)
            assert store.clear_queue() == [str(run_id)]
        return result

    monkeypatch.setattr(session_type, "scalar", clear_after_selection)
    assert store.lease_next("racing-worker") is None
    assert interleaved
    assert store.get_summary(run_id).status == RunStatus.CANCELLED
    assert str(run_id) not in store.lease_tokens
