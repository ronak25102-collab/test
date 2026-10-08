from __future__ import annotations

from signal_research.domain.schemas import ResearchReport


def printable_sections(report: ResearchReport) -> list[tuple[str, str]]:
    sections = [("Company", report.company.legal_name), ("Cutoff", report.cutoff.isoformat()), ("Outcome", report.outcome.value)]
    for discovery in report.discoveries:
        sections.append(("Discovery", discovery.discovery_sentence))
        sections.append(("Evidence strength", f"{discovery.evidence_strength}: {discovery.strength_rationale}"))
    if report.abstention:
        sections.append(("Missing requirements", "; ".join(report.abstention.missing_requirements)))
    return sections
