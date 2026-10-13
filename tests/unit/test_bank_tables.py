from datetime import date
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from signal_research.domain.enums import Profile
from signal_research.domain.schemas import Passage
from signal_research.extraction.bank_tables import comparative_bank_batch, month_end_columns
from signal_research.extraction.validate import validate_candidate

TEXT = (Path(__file__).parents[1] / "fixtures/sbi-comparative-balance.txt").read_text(encoding="utf-8")
SBI = SimpleNamespace(legal_name="State Bank of India")


def test_real_sbi_columns_preserve_dates_scope_and_amounts():
    passage = Passage(id=uuid4(), document_id=uuid4(), text=TEXT)
    batch = comparative_bank_batch(passage, SBI)
    assert [(c.metric_key, c.value_raw, c.period_end, c.scope.value) for c in batch.facts] == [
        ("deposits", "60,05,805", date(2026, 6, 30), "standalone"),
        ("deposits", "54,73,254", date(2025, 6, 30), "standalone"),
        ("borrowings", "7,68,854", date(2026, 6, 30), "standalone"),
        ("borrowings", "5,37,749", date(2025, 6, 30), "standalone"),
    ]
    for candidate in batch.facts:
        assert validate_candidate(candidate, passage, uuid4(), Profile.BANK).fact
        assert not validate_candidate(candidate.model_copy(update={"period_end": date(2026, 3, 31)}), passage, uuid4(), Profile.BANK).fact


def test_thousand_unit_balance_preserves_scale_schedule_and_comparative_columns():
    from decimal import Decimal
    company = SimpleNamespace(legal_name='Quartz Financial Bank')
    text = "Quartz Financial Bank\nSTANDALONE BALANCE SHEET\n(₹ in ‘000)\nSchedule\nMarch 31, 2026 March 31, 2025\nDeposits 3 31,052,504,740 27,147,148,959\nBorrowings 4 4,893,946,381 5,479,308,926\nAdvances 9 29,371,662,693 26,196,086,171"
    passage = Passage(id=uuid4(), document_id=uuid4(), text=text)
    batch = comparative_bank_batch(passage, company)
    assert len(batch.facts) == 6
    facts = [validate_candidate(candidate, passage, uuid4(), Profile.BANK).fact for candidate in batch.facts]
    assert all(facts)
    assert facts[0].value_decimal == Decimal('3105250.474')
    assert facts[2].value_decimal == Decimal('489394.6381')
    assert all(f.unit_raw == 'INR thousand' for f in facts)
    assert not any(f.metric_key == 'gross_advances' for f in facts)


@pytest.mark.parametrize("label,ending", [("Dec 25", date(2025, 12, 31)), ("Feb 24", date(2024, 2, 29)), ("Feb 25", date(2025, 2, 28))])
def test_comparative_month_headers_use_actual_calendar_end(label, ending):
    assert month_end_columns(TEXT.replace("Jun 26", label))[1][1] == ending


@pytest.mark.parametrize("change", [
    lambda t: t.replace("Jun 25 Jun 26", "Q1FY26 Q1FY27"),
    lambda t: t.replace("SBI SOLO SBI GROUP", ""),
    lambda t: t.replace("₹ in Crores", ""),
    lambda t: t.replace("YOY Growth (%)", "Other amounts"),
    lambda t: t + "\nRegional Rural Banks – Sponsored by SBI\n",
])
def test_incomplete_or_subsidiary_table_is_not_auto_extracted(change):
    passage = Passage(id=uuid4(), document_id=uuid4(), text=change(TEXT))
    assert comparative_bank_batch(passage, SBI) is None


def test_sbi_values_are_never_auto_assigned_to_another_issuer():
    passage = Passage(id=uuid4(), document_id=uuid4(), text=TEXT)
    assert comparative_bank_batch(passage, SimpleNamespace(legal_name="HDFC Bank")) is None


def test_net_advances_cannot_be_renamed_gross_advances():
    passage = Passage(id=uuid4(), document_id=uuid4(), text=TEXT)
    candidate = comparative_bank_batch(passage, SBI).facts[0].model_copy(update={"metric_key": "gross_advances", "value_raw": "49,92,004"})
    result = validate_candidate(candidate, passage, uuid4(), Profile.BANK)
    assert not result.fact and "net advances" in result.reason


def test_month_and_two_digits_without_year_comparison_remain_ambiguous():
    assert not month_end_columns(TEXT.replace("YOY Growth (%)", "Other amounts"))
    assert not month_end_columns("Standalone balance sheet\nJun 25\nDeposits INR 100 crore")


def test_real_axis_balance_selects_year_comparison_and_correct_consolidated_columns():
    text = (Path(__file__).parents[1] / "fixtures/axis-consolidated-balance.txt").read_text(encoding="utf-8")
    passage = Passage(id=uuid4(), document_id=uuid4(), text=text)
    batch = comparative_bank_batch(passage, SimpleNamespace(legal_name="Axis Bank"))
    assert [(c.metric_key, c.value_raw, c.period_end, c.scope.value) for c in batch.facts] == [
        ("deposits", "13,71,173.07", date(2026, 6, 30), "consolidated"),
        ("deposits", "11,59,584.25", date(2025, 6, 30), "consolidated"),
        ("borrowings", "2,85,257.98", date(2026, 6, 30), "consolidated"),
        ("borrowings", "2,19,991.64", date(2025, 6, 30), "consolidated"),
        ("advances_as_reported", "13,15,862.99", date(2026, 6, 30), "consolidated"),
        ("advances_as_reported", "11,02,649.20", date(2025, 6, 30), "consolidated"),
    ]
    for c in batch.facts:
        assert validate_candidate(c, passage, uuid4(), Profile.BANK).fact
    assert comparative_bank_batch(passage, SimpleNamespace(legal_name="ICICI Bank")) is None


@pytest.mark.parametrize("name", ["Axis Bank", "HDFC Bank", "ICICI Bank", "Kotak Mahindra Bank", "State Bank of India"])
def test_shared_explicit_balance_binding_preserves_dates_and_scope_for_each_bank(name):
    text = f"{name}\nStandalone Statement of Assets and Liabilities\nINR in crore\nAs on 30.06.2026 As on 31.03.2026 As on 30.06.2025\nDeposits 120 110 100\nBorrowings 30 25 20\n"
    passage = Passage(id=uuid4(), document_id=uuid4(), text=text)
    batch = comparative_bank_batch(passage, SimpleNamespace(legal_name=name))
    assert [c.value_raw for c in batch.facts] == ["120", "100", "30", "20"]
    assert all(c.scope.value == "standalone" for c in batch.facts)
    for c in batch.facts:
        assert validate_candidate(c, passage, uuid4(), Profile.BANK).fact


@pytest.mark.parametrize("change", [
    lambda t: t.replace("Standalone", ""),
    lambda t: t.replace("Standalone", "Standalone Consolidated"),
    lambda t: t.replace("INR in crore", "in crore"),
    lambda t: t.replace("As on 30.06.2026 As on 30.06.2025", "As on Q1FY27 As on Q1FY26"),
    lambda t: t.replace("As on 30.06.2026 As on 30.06.2025", "As on 30.06.2026 As on 30.06.2026"),
    lambda t: t.replace("Deposits 120 100", "Deposits 120 100 20%"),
])
def test_shared_balance_binding_withholds_ambiguous_rows_or_headers(change):
    text = "Axis Bank\nStandalone Balance Sheet\nINR in crore\nAs on 30.06.2026 As on 30.06.2025\nDeposits 120 100\n"
    passage = Passage(id=uuid4(), document_id=uuid4(), text=change(text))
    assert comparative_bank_batch(passage, SimpleNamespace(legal_name="Axis Bank")) is None


def test_english_headers_require_document_identity_and_preserve_schedule_columns():
    text = "Consolidated Balance Sheet\nINR in crore\nSchedule\nJune 30, 2026 March 31, 2026 June 30, 2025\nDeposits 3 120 110 100\nAdvances 9 90 85 80\n"
    passage = Passage(id=uuid4(), document_id=uuid4(), text=text)
    company = SimpleNamespace(legal_name="Example Financial Bank")
    assert comparative_bank_batch(passage, company) is None
    batch = comparative_bank_batch(passage, company, document_issuer_verified=True)
    assert [(c.metric_key, c.value_raw, c.period_end) for c in batch.facts] == [
        ("deposits", "120", date(2026, 6, 30)), ("deposits", "100", date(2025, 6, 30)),
        ("advances_as_reported", "90", date(2026, 6, 30)), ("advances_as_reported", "80", date(2025, 6, 30))]
    assert all(validate_candidate(c, passage, uuid4(), Profile.BANK).fact for c in batch.facts)


def test_document_identity_cannot_use_a_passing_issuer_mention():
    from signal_research.research.identity import issuer_cover_identity
    company = SimpleNamespace(legal_name="Example Financial Bank")
    assert issuer_cover_identity("Example Financial Bank Limited\nQuarterly results", company)
    assert not issuer_cover_identity("A subsidiary of Example Financial Bank Limited", company)
