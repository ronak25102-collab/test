from __future__ import annotations

from signal_research.domain.schemas import ResearchReport


def report_json(report: ResearchReport) -> str:
    return report.model_dump_json(indent=2)


def evidence_manifest(report: ResearchReport) -> dict:
    return {"run_id": str(report.run_id), "schema_version": report.schema_version, "document_hashes": [document.content_hash for document in report.documents], "full_documents_included": False}
