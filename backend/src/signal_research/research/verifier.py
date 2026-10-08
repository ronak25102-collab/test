from __future__ import annotations

from signal_research.domain.schemas import ResearchReport
from signal_research.evidence.citation_checks import citation_coverage


class VerificationFailure(ValueError):
    code = "CITATION_FAILED"


def verify_report(report: ResearchReport) -> ResearchReport:
    if report.publication_status.value == "published" and citation_coverage(report) < 1:
        raise VerificationFailure("published report does not have complete material claim coverage")
    if report.publication_status.value == "published":
        for document in report.documents:
            if document.cutoff_eligibility != "eligible":
                raise VerificationFailure("ineligible source reached a published report")
    return report
