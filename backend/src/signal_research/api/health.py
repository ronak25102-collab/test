from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/configuration")
def configuration(request: Request):
    from signal_research.research.readiness import live_readiness, provider_warnings
    settings = request.app.state.settings
    if settings.pipeline_mode == "precomputed":
        from signal_research.precomputed.catalog import index_entries
        return {"ready": True, "issues": [], "warnings": [], "provider": "none",
                "mode": "precomputed", "max_run_seconds": settings.replay_duration_seconds,
                "demo_time_warning": False, "cost_policy": "No outbound calls",
                "model_request_timeout_seconds": settings.model_request_timeout_seconds,
                "codecraft_backup_keys": 0, "nvidia_fallback_enabled": False,
                "nvidia_planning_enabled": False,
                "companies_available": [entry["symbol"] for entry in index_entries(settings)]}
    result = live_readiness(settings)
    try:
        result["warnings"] = provider_warnings(request.app.state.store, settings)
    except Exception:
        # Warnings are advisory; a database hiccup must not hide readiness itself.
        result["warnings"] = []
    return result


@router.get("/live")
def live():
    return {"status": "ok", "service_version": "0.1.0"}


@router.get("/ready")
def ready(request: Request):
    from signal_research.db.models import WorkerHeartbeatModel
    try:
        with request.app.state.store.session_factory() as session:
            session.execute(text("SELECT 1"))
            heartbeat = session.scalar(select(WorkerHeartbeatModel).order_by(WorkerHeartbeatModel.timestamp.desc()))
            fresh = False
            if heartbeat:
                timestamp = heartbeat.timestamp.replace(tzinfo=UTC)
                fresh = (datetime.now(UTC) - timestamp).total_seconds() < 30
        return JSONResponse({"database": "ok", "worker": "fresh" if fresh else "stale"}, status_code=200 if fresh else 503)
    except Exception:
        return JSONResponse({"database": "unavailable", "worker": "unknown"}, status_code=503)
