from __future__ import annotations

import csv
import io
import json
import zipfile
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from .runs import get_store

router = APIRouter(prefix="/runs", tags=["exports"])


def safe_csv(value: object) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


@router.get("/{run_id}/exports/report.json")
def report_json(run_id: UUID, store=Depends(get_store)):
    report = store.get_report(run_id)
    if not report:
        raise HTTPException(status_code=409, detail={"code": "REPORT_NOT_READY", "message": "report is not available yet"})
    return Response(report.model_dump_json(), media_type="application/json", headers={"Content-Disposition": f"attachment; filename={run_id}.report.json"})


@router.get("/{run_id}/exports/facts.csv")
def facts_csv(run_id: UUID, store=Depends(get_store)):
    report = store.get_report(run_id)
    if not report:
        raise HTTPException(status_code=409, detail={"code": "REPORT_NOT_READY", "message": "report is not available yet"})
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "metric_key", "value_raw", "value_decimal", "unit", "period_end", "scope", "status", "passage_id"])
    for fact in report.facts:
        writer.writerow([safe_csv(fact.id), safe_csv(fact.metric_key), safe_csv(fact.value_raw), safe_csv(fact.value_decimal), safe_csv(fact.unit_normalized), safe_csv(fact.period_end), safe_csv(fact.scope), safe_csv(fact.status), safe_csv(fact.passage_id)])
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={run_id}.facts.csv"})


@router.get("/{run_id}/exports/evidence.zip")
def evidence_zip(run_id: UUID, store=Depends(get_store)):
    report = store.get_report(run_id)
    if not report:
        raise HTTPException(status_code=409, detail={"code": "REPORT_NOT_READY", "message": "report is not available yet"})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("manifest.json", json.dumps({"run_id": str(run_id), "documents": [str(d.id) for d in report.documents], "note": "metadata, hashes and short passages only"}, indent=2))
        bundle.writestr("report.json", report.model_dump_json(indent=2))
        bundle.writestr("facts.json", json.dumps([f.model_dump(mode="json") for f in report.facts], indent=2))
        bundle.writestr("calculations.json", json.dumps([c.model_dump(mode="json") for c in report.calculations], indent=2))
    return Response(buffer.getvalue(), media_type="application/zip", headers={"Content-Disposition": f"attachment; filename={run_id}.evidence.zip"})
