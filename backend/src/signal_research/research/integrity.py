"""Bind a completed semantic review to the exact report content it reviewed.

This is an integrity checksum, not a substitute for entailment review. Only report
builders that have completed that review may call attest_report.
"""
import hashlib
import json

from signal_research.domain.enums import EvidenceRelation, VerificationStatus


def report_digest(report):
    payload = report.model_dump(mode="json")
    payload["generation_metadata"].pop("verification_digest", None)
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def attest_report(report):
    for claim in report.claims:
        if claim.verification_status != VerificationStatus.SUPPORTED:
            raise ValueError("unreviewed claim cannot be attested")
        for link in claim.evidence_links:
            if link.relation == EvidenceRelation.SUPPORTING:
                link.entailment_status = VerificationStatus.SUPPORTED
    report.generation_metadata["verification_digest"] = report_digest(report)
    return report
