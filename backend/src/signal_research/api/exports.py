from __future__ import annotations

import io
import json
import zipfile
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from signal_research.exports.csv_facts import spreadsheet_safe

from .runs import get_store

router = APIRouter(prefix="/runs", tags=["exports"])


safe_csv = spreadsheet_safe


@router.get('/{run_id}/exports/report.html')
def portable_html(run_id: UUID, store=Depends(get_store)):
    from signal_research.exports.html_report import report_html
    report = store.get_report(run_id)
    if not report:
        raise HTTPException(status_code=409, detail={'code': 'REPORT_NOT_READY', 'message': 'report is not available yet'})
    return Response(report_html(report), media_type='text/html', headers={'Content-Disposition': f'attachment; filename=Beyond-{run_id}.html'})


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
    from signal_research.exports.csv_facts import facts_csv as render_facts_csv
    return Response(render_facts_csv(report), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={run_id}.facts.csv"})


@router.get("/{run_id}/exports/evidence.zip")
def evidence_zip(run_id: UUID, store=Depends(get_store)):
    report = store.get_report(run_id)
    if not report:
        raise HTTPException(status_code=409, detail={"code": "REPORT_NOT_READY", "message": "report is not available yet"})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("manifest.json", json.dumps({"run_id": str(run_id), "documents": [str(d.id) for d in report.documents], "note": "Metadata, hashes and retained parsed passages; no raw PDFs. Abstention reports may retain extensive source text. For local review; observe original source reuse terms."}, indent=2))
        bundle.writestr("report.json", report.model_dump_json(indent=2))
        bundle.writestr("facts.json", json.dumps([f.model_dump(mode="json") for f in report.facts], indent=2))
        bundle.writestr("calculations.json", json.dumps([c.model_dump(mode="json") for c in report.calculations], indent=2))
    return Response(buffer.getvalue(), media_type="application/zip", headers={"Content-Disposition": f"attachment; filename={run_id}.evidence.zip"})
