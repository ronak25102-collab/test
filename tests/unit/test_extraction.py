from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from signal_research.domain.enums import PeriodType, Profile, Scope
from signal_research.domain.schemas import Passage
from signal_research.extraction.dates import source_dates
from signal_research.extraction.models import ExtractedFactCandidate, source_fact_batch_schema
from signal_research.extraction.validate import date_in_text, validate_candidate


def test_fact_candidate_requires_exact_source_value_and_scale():
    passage = Passage(id=uuid4(), document_id=uuid4(), text="Consolidated gross advances were INR 1,20,000 crore at 31 March 2026.")
    candidate = ExtractedFactCandidate(metric_key="gross_advances", value_raw="1,20,000", unit_raw="INR crore", currency="INR", period_end=date(2026, 3, 31), period_type=PeriodType.INSTANT, scope=Scope.CONSOLIDATED, passage_id=passage.id, extraction_confidence=Decimal("0.98"))
    result = validate_candidate(candidate, passage, uuid4(), Profile.BANK)
    assert result.fact is not None
    assert result.fact.value_decimal == Decimal("120000")
    assert result.fact.unit_normalized == "INR_crore"


def test_live_extraction_schema_keeps_original_span_and_only_offers_registered_source_bindings():
    from pydantic import ValidationError

    passage_id = uuid4()
    schema = source_fact_batch_schema(["deposits", "borrowings"], passage_id)
    native = schema.model_json_schema()["$defs"]["InstantSourceFact"]["properties"]
    assert native["evidence_quote"]["type"] == "null"
    assert native["metric_key"]["enum"] == ["deposits", "borrowings"]
    assert native["passage_id"]["enum"] == [str(passage_id)]
    assert native["period_start"]["type"] == "null"
    assert native["period_type"]["const"] == "instant"
    fact = dict(metric_key="deposits", value_raw="100", unit_raw="INR crore", currency="INR",
                period_end="2026-06-30", scope="standalone", passage_id=passage_id, extraction_confidence=".99")
    assert schema(facts=[fact]).facts[0].evidence_quote is None
    with pytest.raises(ValidationError):
        schema(facts=[fact | {"evidence_quote": "A rewritten or truncated quote"}])
    with pytest.raises(ValidationError):
        schema(facts=[fact] * 7)
    with pytest.raises(ValidationError):
        schema(facts=[fact | {"period_start": "2026-04-01"}])


def test_live_extraction_schema_requires_explicit_duration_start_for_profit_metrics():
    from pydantic import ValidationError

    passage_id = uuid4()
    schema = source_fact_batch_schema(["net_profit"], passage_id)
    fact = dict(metric_key="net_profit", value_raw="100", unit_raw="INR crore", currency="INR",
                period_end="2026-06-30", scope="standalone", passage_id=passage_id, extraction_confidence=".99")
    with pytest.raises(ValidationError):
        schema(facts=[fact])
    with pytest.raises(ValidationError):
        schema(facts=[fact | {"period_type": "instant", "period_start": "2026-04-01"}])
    assert schema(facts=[fact | {"period_start": "2026-04-01"}]).facts[0].period_type == PeriodType.DURATION
    mixed = source_fact_batch_schema(["deposits", "net_profit"], passage_id)
    with pytest.raises(ValidationError):
        mixed(facts=[fact | {"metric_key": "deposits", "period_type": "duration", "period_start": "2026-04-01"}])


def test_native_fact_dates_only_offer_complete_source_dates_or_verified_month_columns():
    dates = source_dates("As on June 30, 2026 and 30.06.2025. Signed 18th July, 2026. FY27 Q1. Invalid 31.02.2026.")
    assert dates == [date(2025, 6, 30), date(2026, 6, 30), date(2026, 7, 18)]
    assert source_dates("Q1FY27, June 2026 and year ended FY2026") == []
    schema = source_fact_batch_schema(["deposits", "net_profit"], uuid4(), dates)
    for variant in ("InstantSourceFact", "DurationSourceFact"):
        assert schema.model_json_schema()["$defs"][variant]["properties"]["period_end"]["enum"] == [str(d) for d in dates]


def test_fact_candidate_rejects_wrong_profile_or_missing_scale():
    passage = Passage(id=uuid4(), document_id=uuid4(), text="Value of new business was 100.")
    candidate = ExtractedFactCandidate(metric_key="vnb", value_raw="100", unit_raw="INR crore", currency="INR", period_end=date(2026, 3, 31), scope=Scope.CONSOLIDATED, passage_id=passage.id, extraction_confidence=Decimal("0.9"))
    wrong_profile = validate_candidate(candidate, passage, uuid4(), Profile.BANK)
    assert wrong_profile.fact is None
    missing_scale = ExtractedFactCandidate(metric_key="gross_advances", value_raw="100", unit_raw="INR", currency="INR", period_end=date(2026, 3, 31), scope=Scope.CONSOLIDATED, passage_id=passage.id, extraction_confidence=Decimal("0.9"))
    assert validate_candidate(missing_scale, passage, uuid4(), Profile.BANK).fact is None


def test_registered_metric_period_type_cannot_be_changed_by_model_review():
    passage = Passage(id=uuid4(), document_id=uuid4(), text="Standalone INR crore net profit 100 from 1 April 2026 to 30 June 2026. Deposits 200 at 30 June 2026.")
    candidate = ExtractedFactCandidate(metric_key="net_profit", value_raw="100", unit_raw="INR crore", currency="INR",
        period_end=date(2026, 6, 30), scope="standalone", passage_id=passage.id, extraction_confidence=Decimal(".99"))
    wrong = validate_candidate(candidate, passage, uuid4(), Profile.BANK)
    assert not wrong.fact and "registered metric definition" in wrong.reason
    assert validate_candidate(candidate.model_copy(update={"period_type": PeriodType.DURATION, "period_start": date(2026, 4, 1)}), passage, uuid4(), Profile.BANK).fact
    deposit = candidate.model_copy(update={"metric_key": "deposits", "value_raw": "200", "period_start": date(2026, 4, 1)})
    assert not validate_candidate(deposit, passage, uuid4(), Profile.BANK).fact


@pytest.mark.parametrize("text", ["30.06.2026", "30/06/2026", "30-06-2026", "June 30, 2026", "30 June 2026", "2026-06-30"])
def test_complete_source_dates_accept_equivalent_formats(text):
    assert date_in_text(date(2026, 6, 30), text)
    assert not date_in_text(date(2025, 6, 30), text)


def test_period_labels_and_corrupted_dates_do_not_authorize_a_fact():
    for text in ("Q1FY27", "30.06.2025", "3006-06-20", "2026-06", "June 2026"):
        assert not date_in_text(date(2026, 6, 30), text)


def test_dotted_table_header_passes_without_weakening_other_bindings():
    passage = Passage(id=uuid4(), document_id=uuid4(), text="Standalone balance sheet INR crore\nAs at 30.06.2026\nDeposits 100")
    candidate = ExtractedFactCandidate(metric_key="deposits", value_raw="100", unit_raw="INR crore", currency="INR", period_end=date(2026, 6, 30), scope="standalone", passage_id=passage.id, extraction_confidence=Decimal(".99"), evidence_quote=passage.text)
    assert validate_candidate(candidate, passage, uuid4(), Profile.BANK).fact is not None
    assert validate_candidate(candidate.model_copy(update={"period_end": date(2025, 6, 30)}), passage, uuid4(), Profile.BANK).fact is None


@pytest.mark.parametrize("unit", ["INR thousand", "000", "'000", "INR '000"])
def test_explicit_thousand_rupee_table_units_are_normalized_exactly(unit):
    passage = Passage(id=uuid4(), document_id=uuid4(), text="Standalone balance sheet (\u20b9 in '000)\nAs at March 31, 2026\nDeposits 31,052,504,740")
    candidate = ExtractedFactCandidate(metric_key="deposits", value_raw="31,052,504,740", unit_raw=unit, currency="INR", period_end=date(2026, 3, 31), scope="standalone", passage_id=passage.id, extraction_confidence=Decimal(".99"), evidence_quote=passage.text)
    result = validate_candidate(candidate, passage, uuid4(), Profile.BANK)
    assert result.fact.value_decimal == Decimal("3105250.474")
    without_scale = passage.model_copy(update={"text": passage.text.replace("in '000", "")})
    assert validate_candidate(candidate.model_copy(update={"evidence_quote": None}), without_scale, uuid4(), Profile.BANK).fact is None
