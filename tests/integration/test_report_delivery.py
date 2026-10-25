"""Saved evidence stays out of polling queries and is delivered without rebuilding it."""
from datetime import date

from fastapi.testclient import TestClient
from signal_research.domain.enums import RunMode
from signal_research.main import create_app
from signal_research.research.report_builder import build_synthetic_report
from sqlalchemy import event


def test_polling_skips_report_payload_and_report_response_preserves_all_evidence(store, settings):
    company = store.search_companies("SYNTHBANK")[0]
    run_id = store.create_run(company, date(2026, 10, 8), RunMode.REPLAY)
    assert store.lease_next("delivery-test")
    report = build_synthetic_report(run_id, company, date(2026, 10, 8))
    # Simulate a large saved evidence appendix, as in the real bank fixtures.
    report.generation_metadata["source_appendix"] = "source-bound evidence " * 100_000
    store.save_report(report)
    with store.session_factory() as session:
        engine = session.get_bind()
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    with TestClient(create_app(settings, store_override=store)) as client:
        event.listen(engine, "before_cursor_execute", capture)
        try:
            assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "completed"
            assert client.get("/api/v1/runs/history").json()["items"][0]["id"] == str(run_id)
            assert client.get("/api/v1/runs/queue").status_code == 200
            assert client.get(f"/api/v1/runs/{run_id}/events").status_code == 200
            assert statements and all("report_json" not in statement for statement in statements)
            statements.clear()
            response = client.get(f"/api/v1/runs/{run_id}/report")
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/json"
            assert response.json() == report.model_dump(mode="json")
            payload_queries = [statement for statement in statements if "report_json" in statement]
            assert len(payload_queries) == 1
            assert "cast(" in payload_queries[0]
        finally:
            event.remove(engine, "before_cursor_execute", capture)
