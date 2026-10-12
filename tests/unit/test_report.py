from datetime import date
from uuid import uuid4

import pytest
from signal_research.research.integrity import attest_report
from signal_research.research.report_builder import build_synthetic_report
from signal_research.research.verifier import VerificationFailure, verify_report


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


def test_independent_context_elsewhere_cannot_validate_single_origin_headline(store):
    company = store.search_companies("SYNTHBANK")[0]
    report = build_synthetic_report(uuid4(), company, date(2026, 10, 8))
    headline = next(c for c in report.claims if c.text == report.discoveries[0].discovery_sentence)
    headline.evidence_links = headline.evidence_links[:1]
    attest_report(report)
    with pytest.raises(VerificationFailure, match="independently"):
        verify_report(report)


def test_material_inferred_significance_cannot_rely_on_one_origin(store):
    from signal_research.domain.enums import ClaimKind
    company = store.search_companies('SYNTHBANK')[0]
    report = build_synthetic_report(uuid4(), company, date(2026, 10, 8))
    report.claims[0].kind = ClaimKind.INFERRED
    attest_report(report)
    with pytest.raises(VerificationFailure, match='material inferred claims'):
        verify_report(report)


def test_legacy_digest_preserved_but_retrieval_basis_is_bound(store):
    import hashlib
    import json

    from signal_research.research.integrity import report_digest
    report = build_synthetic_report(uuid4(), store.search_companies('SYNTHBANK')[0], date(2026, 10, 8))
    legacy = report.model_dump(mode='json')
    legacy['generation_metadata'].pop('verification_digest', None)
    for doc in legacy['documents']:
        doc.pop('cutoff_eligibility_basis')
    digest = hashlib.sha256(json.dumps(legacy, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert report_digest(report) == digest
    report.documents[0].cutoff_eligibility_basis = 'verified_retrieval'
    assert report_digest(report) != digest
