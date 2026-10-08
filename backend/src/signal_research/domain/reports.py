from signal_research.domain.schemas import ResearchReport


def published_claim_count(report: ResearchReport) -> int:
    return sum(claim.material for claim in report.claims if claim.verification_status.value == "supported")
