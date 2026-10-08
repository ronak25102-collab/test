from datetime import date
from decimal import Decimal
from uuid import uuid4

from signal_research.domain.enums import PeriodType, Profile, Scope
from signal_research.domain.schemas import Passage
from signal_research.extraction.models import ExtractedFactCandidate
from signal_research.extraction.validate import validate_candidate


def test_fact_candidate_requires_exact_source_value_and_scale():
    passage = Passage(id=uuid4(), document_id=uuid4(), text="Consolidated gross advances were INR 1,20,000 crore at 31 March 2026.")
    candidate = ExtractedFactCandidate(metric_key="gross_advances", value_raw="1,20,000", unit_raw="INR crore", currency="INR", period_end=date(2026, 3, 31), period_type=PeriodType.INSTANT, scope=Scope.CONSOLIDATED, passage_id=passage.id, extraction_confidence=Decimal("0.98"))
    result = validate_candidate(candidate, passage, uuid4(), Profile.BANK)
    assert result.fact is not None
    assert result.fact.value_decimal == Decimal("120000")
    assert result.fact.unit_normalized == "INR_crore"


def test_fact_candidate_rejects_wrong_profile_or_missing_scale():
    passage = Passage(id=uuid4(), document_id=uuid4(), text="Value of new business was 100.")
    candidate = ExtractedFactCandidate(metric_key="vnb", value_raw="100", unit_raw="INR crore", currency="INR", period_end=date(2026, 3, 31), scope=Scope.CONSOLIDATED, passage_id=passage.id, extraction_confidence=Decimal("0.9"))
    wrong_profile = validate_candidate(candidate, passage, uuid4(), Profile.BANK)
    assert wrong_profile.fact is None
    missing_scale = ExtractedFactCandidate(metric_key="gross_advances", value_raw="100", unit_raw="INR", currency="INR", period_end=date(2026, 3, 31), scope=Scope.CONSOLIDATED, passage_id=passage.id, extraction_confidence=Decimal("0.9"))
    assert validate_candidate(missing_scale, passage, uuid4(), Profile.BANK).fact is None
