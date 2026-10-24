from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status

from signal_research.db.repositories import Store
from signal_research.domain.enums import RunMode
from signal_research.domain.schemas import RunCreate

router = APIRouter(prefix="/runs", tags=["runs"])


def get_store(request: Request) -> Store:
    return request.app.state.store


def require_summary(run_id: UUID, store: Store):
    summary = store.get_summary(run_id)
    if not summary:
        raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND", "message": "run does not exist"})
    return summary


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_run(request: RunCreate, response: Response, http_request: Request, store: Store = Depends(get_store), idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None):
    if request.as_of > datetime.now(ZoneInfo("Asia/Kolkata")).date():
        raise HTTPException(status_code=422, detail={"code": "INVALID_CUTOFF", "message": "cutoff cannot be in the future"})
    company = store.get_company(request.company_id)
    if not company:
        raise HTTPException(status_code=404, detail={"code": "COMPANY_NOT_FOUND", "message": "company does not exist"})
    if not company.business_profiles:
        raise HTTPException(status_code=422, detail={"code": "PROFILE_UNRESOLVED", "message": "company business profile has not been resolved"})
    if (request.mode == RunMode.REPLAY) != ("SYNTHBANK" in company.symbols):
        raise HTTPException(status_code=422, detail={"code": "MODE_COMPANY_MISMATCH", "message": "Replay requires SYNTHBANK; live and deep modes require a real listed company"})
    if request.mode != RunMode.REPLAY:
        settings = http_request.app.state.settings
        if settings.pipeline_mode == "precomputed":
            from signal_research.precomputed.catalog import PrecomputedUnavailable, load_report
            try:
                load_report(settings, company, request.as_of)
            except PrecomputedUnavailable as exc:
                raise HTTPException(status_code=404, detail={"code": exc.code, "message": str(exc)}) from exc
        else:
            from signal_research.research.readiness import live_readiness
            readiness = live_readiness(settings)
            if not readiness["ready"]:
                raise HTTPException(status_code=503, detail={"code": "LIVE_CONFIGURATION_INCOMPLETE",
                    "message": " ".join(readiness["issues"]), "issues": readiness["issues"]})
    try:
        settings = http_request.app.state.settings
        run_id = store.create_run(company, request.as_of, request.mode, idempotency_key,
                                  cold_start=request.cold_start,
                                  pipeline_mode=settings.pipeline_mode,
                                  replay_duration_seconds=settings.replay_duration_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT", "message": str(exc)})
    response.headers["Location"] = f"/api/v1/runs/{run_id}"
    return {"run_id": str(run_id), "status_url": f"/api/v1/runs/{run_id}", "status": "queued"}


@router.get("/queue")
def queue_status(store: Store = Depends(get_store)):
    return {"queued_count": store.queued_run_count()}


@router.post("/queue/clear")
def clear_queue(store: Store = Depends(get_store)):
    run_ids = store.clear_queue()
    return {"cancelled_count": len(run_ids), "run_ids": run_ids}


@router.get('/history')
def run_history(limit: int = Query(12, ge=1, le=50), store: Store = Depends(get_store)):
    return {'items': [run.model_dump(mode='json') for run in store.run_history(limit)]}


@router.get("/{run_id}")
def get_run(run_id: UUID, store: Store = Depends(get_store)):
    return require_summary(run_id, store).model_dump(mode="json")


@router.get("/{run_id}/events")
def events(run_id: UUID, after: int = Query(0, ge=0), store: Store = Depends(get_store)):
    require_summary(run_id, store)
    items = store.get_events(run_id, after)
    next_cursor = items[-1].sequence if items else after
    return {"items": [item.model_dump(mode="json") for item in items], "next_cursor": next_cursor}


@router.post("/{run_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
def cancel(run_id: UUID, store: Store = Depends(get_store)):
    require_summary(run_id, store)
    try:
        state = store.request_cancel(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND", "message": "run does not exist"})
    return {"run_id": str(run_id), "status": state}


@router.post("/{run_id}/resume", status_code=status.HTTP_202_ACCEPTED)
def resume(run_id: UUID, store: Store = Depends(get_store)):
    require_summary(run_id, store)
    try:
        state = store.resume(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"code": "RUN_NOT_RESUMABLE", "message": str(exc)})
    return {"run_id": str(run_id), "status": state}


@router.get("/{run_id}/report")
def report(run_id: UUID, store: Store = Depends(get_store)):
    require_summary(run_id, store)
    value = store.get_report(run_id)
    if not value:
        raise HTTPException(status_code=409, detail={"code": "REPORT_NOT_READY", "message": "report is not available yet"})
    return value.model_dump(mode="json")
