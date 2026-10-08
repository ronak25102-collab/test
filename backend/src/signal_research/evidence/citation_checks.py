from __future__ import annotations

from dataclasses import dataclass

from signal_research.domain.enums import EvidenceRelation, VerificationStatus
from signal_research.domain.schemas import Claim, ResearchReport


@dataclass(frozen=True)
class CitationCheck:
    ok: bool
    reasons: tuple[str, ...]


def verify_claim(claim: Claim, report: ResearchReport) -> CitationCheck:
    reasons: list[str] = []
    evidence_ids = {fact.id for fact in report.facts} | {passage.id for passage in report.passages}
    for link in claim.evidence_links:
        if link.passage_or_fact_id not in evidence_ids:
            reasons.append(f"unknown evidence {link.passage_or_fact_id}")
        if link.relation == EvidenceRelation.SUPPORTING and link.entailment_status not in {VerificationStatus.PENDING, VerificationStatus.SUPPORTED}:
            reasons.append("supporting link is not entailed")
    if claim.material and not any(link.relation == EvidenceRelation.SUPPORTING for link in claim.evidence_links):
        reasons.append("material claim has no supporting link")
    return CitationCheck(not reasons, tuple(reasons))


def citation_coverage(report: ResearchReport) -> float:
    material = [claim for claim in report.claims if claim.material]
    if not material:
        return 1.0
    return sum(verify_claim(claim, report).ok for claim in material) / len(material)
