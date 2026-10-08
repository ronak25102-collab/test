from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from .runs import get_store, require_summary

router = APIRouter(tags=["evidence"])


@router.get("/claims/{claim_id}")
def claim(claim_id: UUID, run_id: UUID, store=Depends(get_store)):
    require_summary(run_id, store)
    value = store.find_claim(run_id, claim_id)
    if not value:
        raise HTTPException(status_code=404, detail={"code": "CLAIM_NOT_FOUND", "message": "claim does not exist in this run"})
    return value


@router.get("/documents/{document_id}/passages")
def passages(document_id: UUID, run_id: UUID, store=Depends(get_store)):
    report = store.get_report(run_id)
    if not report:
        raise HTTPException(status_code=409, detail={"code": "REPORT_NOT_READY", "message": "report is not available yet"})
    document = next((d for d in report.documents if d.id == document_id), None)
    if not document:
        raise HTTPException(status_code=404, detail={"code": "DOCUMENT_NOT_FOUND", "message": "document does not exist in this run"})
    return {"document": document.model_dump(mode="json"), "items": [p.model_dump(mode="json") for p in report.passages if p.document_id == document_id]}


@router.get("/calculations/{calculation_id}")
def calculation(calculation_id: UUID, run_id: UUID, store=Depends(get_store)):
    report = store.get_report(run_id)
    if not report:
        raise HTTPException(status_code=409, detail={"code": "REPORT_NOT_READY", "message": "report is not available yet"})
    value = next((c for c in report.calculations if c.id == calculation_id), None)
    if not value:
        raise HTTPException(status_code=404, detail={"code": "CALCULATION_NOT_FOUND", "message": "calculation does not exist in this run"})
    inputs = [f.model_dump(mode="json") for f in report.facts if f.id in value.input_fact_ids]
    return {"calculation": value.model_dump(mode="json"), "inputs": inputs}
