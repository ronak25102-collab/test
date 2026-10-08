from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status

from signal_research.db.repositories import Store
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
def create_run(request: RunCreate, response: Response, store: Store = Depends(get_store), idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None):
    if request.as_of > datetime.now(UTC).date():
        raise HTTPException(status_code=422, detail={"code": "INVALID_CUTOFF", "message": "cutoff cannot be in the future"})
    company = store.get_company(request.company_id)
    if not company:
        raise HTTPException(status_code=404, detail={"code": "COMPANY_NOT_FOUND", "message": "company does not exist"})
    run_id = store.create_run(company, request.as_of, request.mode, idempotency_key)
    response.headers["Location"] = f"/api/v1/runs/{run_id}"
    return {"run_id": str(run_id), "status_url": f"/api/v1/runs/{run_id}", "status": "queued"}


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
