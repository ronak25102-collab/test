"""Reuse historical source observations, never cached conclusions or synthetic data."""
import hashlib
from datetime import timedelta
from pathlib import Path

from signal_research.domain.enums import FactStatus
from signal_research.research.verifier import verify_report


def historical_observations(report, company_id, cutoff):
    if report.company.id != company_id or report.cutoff > cutoff or report.source_coverage.get('synthetic') is not False:
        return [], [], []
    try:
        verify_report(report)
    except (ValueError, KeyError):
        return [], [], []
    documents = {}
    for document in report.documents:
        if (not document.document_type.startswith('issuer') or document.cutoff_eligibility != 'eligible' or not document.published_at
                or document.published_at.date() > cutoff or not document.local_object_key):
            continue
        try:
            if hashlib.sha256(Path(document.local_object_key).read_bytes()).hexdigest() != document.content_hash:
                continue
        except OSError:
            continue
        documents[document.id] = document
    passages = {p.id: p for p in report.passages if p.document_id in documents}
    facts = [f for f in report.facts if f.status == FactStatus.VERIFIED and f.entity_id == company_id
             and f.period_end and cutoff - timedelta(days=6 * 366) <= f.period_end <= cutoff - timedelta(days=365)
             and f.passage_id in passages]
    used_documents = {passages[f.passage_id].document_id for f in facts}
    # Keep original page context for fresh extraction and source reconciliation.
    return (facts, [p for p in passages.values() if p.document_id in used_documents],
            [d for d in documents.values() if d.id in used_documents])
