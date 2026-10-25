from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from signal_research.api import companies, evidence, exports, health, runs
from signal_research.db.models import Base
from signal_research.db.repositories import Store
from signal_research.db.session import build_engine, session_factory
from signal_research.settings import get_settings


def create_app(settings=None, store_override=None):
    settings = settings or get_settings()
    settings.ensure_directories()
    engine = build_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        if settings.database_url.startswith("sqlite"):
            Base.metadata.create_all(engine)
        app.state.store = store_override or Store(session_factory(engine), settings.data_dir)
        app.state.store.bootstrap()
        if settings.pipeline_mode == "precomputed":
            from signal_research.precomputed.catalog import bootstrap_catalog
            bootstrap_catalog(app.state.store, settings)
        if settings.auto_start_worker and store_override is None:
            from threading import Event, Thread

            from signal_research.worker.main import run_worker
            app.state.worker_wakeup = Event()
            app.state.worker_stop = Event()
            app.state.worker_idle = Event()
            app.state.worker_thread = Thread(target=run_worker, kwargs={
                "settings": settings, "wakeup": app.state.worker_wakeup,
                "stop": app.state.worker_stop, "idle": app.state.worker_idle,
            }, daemon=True, name="signal-research-worker")
            app.state.worker_thread.start()
        try:
            yield
        finally:
            if hasattr(app.state, "worker_stop"):
                app.state.worker_stop.set()
                app.state.worker_wakeup.set()
                app.state.worker_thread.join(timeout=2)
            engine.dispose()

    application = FastAPI(title="Beyond", version="0.2.0", lifespan=lifespan)
    application.state.settings = settings
    application.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"], allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Idempotency-Key"])
    for router in (companies.router, runs.router, evidence.router, exports.router, health.router):
        application.include_router(router, prefix="/api/v1")

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        return JSONResponse({"code": detail.get("code", "REQUEST_FAILED"), "message": detail.get("message", "Request failed"), "retryable": detail.get("retryable", False), "details": {k: v for k, v in detail.items() if k not in {"code", "message", "retryable"}}}, status_code=exc.status_code)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"code": "INVALID_REQUEST", "message": "Request fields failed validation", "retryable": False, "details": {"errors": [{"location": list(e["loc"]), "message": e["msg"]} for e in exc.errors()]}}, status_code=422)

    if settings.frontend_dist_dir is not None:
        application.mount("/", StaticFiles(directory=settings.frontend_dist_dir, html=True), name="frontend")

    return application


app = create_app()
