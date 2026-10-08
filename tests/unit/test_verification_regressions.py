from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from signal_research.domain.enums import Profile
from signal_research.domain.schemas import Passage
from signal_research.extraction.models import ExtractedFactCandidate
from signal_research.extraction.validate import validate_candidate
from signal_research.finance.calculations import NumericFact, calculate
from signal_research.research.integrity import attest_report
from signal_research.research.report_builder import build_synthetic_report
from signal_research.research.verifier import VerificationFailure, verify_report


@pytest.mark.parametrize("change", [dict(metric_key="deposits"), dict(value_raw="120"), dict(period_end=date(2025, 3, 31)), dict(scope="standalone"), dict(unit_raw="INR million"), dict(evidence_quote="fabricated quote")])
def test_fact_rejects_mismatched_source_context(change):
    passage = Passage(id=uuid4(), document_id=uuid4(), text="Consolidated gross advances were INR 120000 crore at 31 March 2026.")
    values = dict(metric_key="gross_advances", value_raw="120000", unit_raw="INR crore", currency="INR", period_end=date(2026, 3, 31), scope="consolidated", passage_id=passage.id, extraction_confidence=Decimal(".99"))
    assert validate_candidate(ExtractedFactCandidate(**(values | change)), passage, uuid4(), Profile.BANK).fact is None


@pytest.mark.parametrize("field,value", [("entity_id", uuid4()), ("unit", "USD_million"), ("scope", "standalone"), ("metric_key", "deposits"), ("definition_id", "changed"), ("period", "2024-03-31"), ("segment", "retail")])
def test_growth_rejects_incomparable_inputs(field, value):
    a = NumericFact(uuid4(), Decimal("120"), "gross_advances", "INR_crore", "consolidated", "v1", "2026-03-31", uuid4())
    b = replace(a, id=uuid4(), value=Decimal("100"), period="2025-03-31")
    assert not calculate("yoy_growth", [a, replace(b, **{field: value})]).available


@pytest.mark.parametrize("mutation", ["claim", "calculation", "headline", "why", "timeline", "pending"])
def test_publication_rejects_content_changed_after_review(store, mutation):
    report = build_synthetic_report(uuid4(), store.search_companies("SYNTHBANK")[0], date(2026, 10, 8))
    if mutation == "claim":
        report.claims[0].text = "The company concealed losses."
    elif mutation == "calculation":
        report.calculations[0].output_value = Decimal("999999")
    elif mutation == "headline":
        report.discoveries[0].discovery_sentence = "Unsupported fraud allegation"
    elif mutation == "why":
        report.discoveries[0].why_it_matters[0].text = "Unsupported earnings projection"
    elif mutation == "timeline":
        report.timeline_events[0].event_date = date(2027, 1, 1)
    else:
        report.claims[0].evidence_links[0].entailment_status = "pending"
    with pytest.raises(VerificationFailure):
        verify_report(report)


def test_calculation_is_reproduced_even_with_new_checksum(store):
    report = build_synthetic_report(uuid4(), store.search_companies("SYNTHBANK")[0], date(2026, 10, 8))
    report.calculations[0].output_value = Decimal("999999")
    attest_report(report)
    with pytest.raises(VerificationFailure, match="reproduction"):
        verify_report(report)
