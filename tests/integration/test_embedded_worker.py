"""Keep idle hosting checks cheap while browser-created work starts immediately."""
import time
from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from signal_research.db.models import ResearchRunModel, WorkerHeartbeatModel
from signal_research.domain.enums import RunMode, RunStatus
from signal_research.main import create_app
from sqlalchemy import Engine, event, update


def wait_for_report(client, run_id):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/runs/{run_id}/report")
        if response.status_code == 200:
            return response.json()
        time.sleep(.05)
    raise AssertionError("Embedded worker did not publish the queued run")


def test_idle_worker_sleeps_and_create_and_resume_wake_it(settings):
    settings.auto_start_worker = True
    settings.worker_idle_poll_seconds = 900
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    app = create_app(settings)
    with TestClient(app) as client:
        assert app.state.worker_idle.wait(10)
        with app.state.store.session_factory() as session:
            session.execute(update(WorkerHeartbeatModel).values(
                timestamp=datetime.now(UTC) - timedelta(hours=1)))
            session.commit()
        # An intentionally idle live thread is ready even without a fresh DB heartbeat.
        assert client.get("/api/v1/health/ready").json()["worker"] == "idle"
        event.listen(Engine, "before_cursor_execute", capture)
        try:
            time.sleep(1.2)  # The previous one-second loop would query the database.
            for _ in range(3):
                assert client.get("/api/v1/health/live").status_code == 200
            assert statements == []
        finally:
            event.remove(Engine, "before_cursor_execute", capture)

        company = client.get("/api/v1/companies?q=SYNTHBANK").json()["items"][0]
        response = client.post("/api/v1/runs", json={
            "company_id": company["id"], "as_of": "2026-10-08", "mode": "replay"})
        assert response.status_code == 202
        run_id = response.json()["run_id"]
        assert wait_for_report(client, run_id)["company"]["symbols"] == ["SYNTHBANK"]
        assert app.state.worker_idle.wait(10)

        interrupted = app.state.store.create_run(
            app.state.store.get_company(company["id"]), date(2026, 10, 8), RunMode.REPLAY)
        app.state.store.update_run(interrupted, status=RunStatus.FAILED, stage="failed")
        assert client.post(f"/api/v1/runs/{interrupted}/resume").status_code == 202
        assert wait_for_report(client, interrupted)["run_id"] == str(interrupted)
        assert app.state.worker_idle.wait(10)
    assert not app.state.worker_thread.is_alive()


def test_idle_delay_recovers_outstanding_leases_promptly(store):
    assert store.worker_idle_delay(900) == 900
    company = store.search_companies("SYNTHBANK")[0]
    run_id = store.create_run(company, date(2026, 10, 8), RunMode.REPLAY)
    assert store.lease_next("interrupted-worker")
    with store.session_factory() as session:
        session.execute(update(ResearchRunModel).where(
            ResearchRunModel.id == str(run_id)).values(
                lease_expires_at=datetime.now(UTC) + timedelta(seconds=10)))
        session.commit()
    assert 1 <= store.worker_idle_delay(900) <= 11
    store.update_run(run_id, status=RunStatus.FAILED, stage="failed")
    assert store.worker_idle_delay(900) == 900
