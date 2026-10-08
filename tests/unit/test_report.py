from datetime import date
from uuid import uuid4

from signal_research.research.report_builder import build_synthetic_report
from signal_research.research.verifier import verify_report


def test_replay_report_has_traceable_eight_element_discovery(store):
    company = store.search_companies("SYNTHBANK")[0]
    report = verify_report(build_synthetic_report(uuid4(), company, date(2026, 10, 8)))
    discovery = report.discoveries[0]
    assert report.outcome.value == "discovery"
    assert 3 <= len(discovery.why_it_matters) <= 5
    assert len(discovery.timeline_event_ids) == 1
    assert discovery.counterargument.search_attempted
    assert discovery.falsification_rules
    assert {str(c.formula_id) for c in report.calculations} >= {"yoy_growth", "growth_gap", "loan_to_deposit", "ldr_change"}
    assert all(claim.verification_status.value == "supported" for claim in report.claims)


def test_cutoff_can_abstain(store):
    company = store.search_companies("SYNTHBANK")[0]
    report = build_synthetic_report(uuid4(), company, date(2026, 1, 1))
    assert report.outcome.value == "insufficient_evidence"
    assert not report.discoveries
    assert report.abstention
