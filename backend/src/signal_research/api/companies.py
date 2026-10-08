from fastapi import APIRouter, Depends, HTTPException

from signal_research.domain.schemas import ResolveRequest
from signal_research.research.entity_resolver import resolve

from .runs import get_store

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("")
def companies(q: str = "", store=Depends(get_store)):
    return {"items": [c.model_dump(mode="json") for c in store.search_companies(q)], "snapshot_age_days": store.snapshot_age_days()}


@router.post("/resolve")
def resolve_company(request: ResolveRequest, store=Depends(get_store)):
    result = resolve(store, request.query, refresh=True)
    if result.company:
        return {"resolved": result.company.model_dump(mode="json"), "candidates": [c.model_dump(mode="json") for c in result.candidates]}
    if result.candidates:
        raise HTTPException(status_code=409, detail={"code": "COMPANY_AMBIGUOUS", "message": result.reason, "candidates": [c.model_dump(mode="json") for c in result.candidates]})
    raise HTTPException(status_code=404, detail={"code": "UNSUPPORTED_SECTOR", "message": result.reason})
