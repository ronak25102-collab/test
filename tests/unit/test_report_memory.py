"""Heavy operations wait without starving status requests or leaking permits."""
import asyncio
import hashlib
import json
from datetime import date
from threading import Event, Thread
from uuid import uuid4

import pytest
from signal_research.report_memory import ReportMemoryMiddleware, report_memory
from signal_research.research.integrity import report_digest
from signal_research.research.report_builder import build_synthetic_report


@pytest.mark.asyncio
async def test_http_waits_for_worker_but_health_bypasses_and_cancellation_releases():
    entered, release = Event(), Event()

    def worker():
        with report_memory():
            with report_memory():  # Nested fixture checks cannot deadlock.
                entered.set()
                assert release.wait(5)

    thread = Thread(target=worker)
    thread.start()
    assert await asyncio.to_thread(entered.wait, 5)
    calls = []

    async def app(scope, receive, send):
        calls.append(scope["path"])

    middleware = ReportMemoryMiddleware(app)

    async def invoke(path):
        await middleware({"type": "http", "method": "GET", "path": path}, None, None)

    pending = asyncio.create_task(invoke("/api/v1/runs/123/report"))
    try:
        await asyncio.sleep(.05)
        await invoke("/api/v1/health/live")
        assert calls == ["/api/v1/health/live"]
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
    finally:
        release.set()
        await asyncio.to_thread(thread.join, 5)
    await asyncio.wait_for(invoke("/api/v1/runs/123/report"), 2)
    assert calls[-1].endswith("/report")


@pytest.mark.asyncio
async def test_failed_http_operation_releases_slot():
    async def broken(scope, receive, send):
        raise RuntimeError("interrupted")

    middleware = ReportMemoryMiddleware(broken)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="interrupted"):
            await asyncio.wait_for(middleware(
                {"type": "http", "method": "GET", "path": "/api/v1/runs/123/report"}, None, None), 2)


def test_streamed_digest_matches_existing_review_receipts(store):
    report = build_synthetic_report(uuid4(), store.search_companies("SYNTHBANK")[0], date(2026, 10, 8))
    report.generation_metadata["unicode_and_escaping"] = "₹ é \\ \n"
    payload = report.model_dump(mode="json")
    for document in payload["documents"]:
        if document.get("cutoff_eligibility_basis") == "publication_date":
            document.pop("cutoff_eligibility_basis")
    payload["generation_metadata"].pop("verification_digest", None)
    expected = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert report_digest(report) == expected
