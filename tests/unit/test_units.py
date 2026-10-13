from decimal import Decimal

import pytest
from signal_research.finance.periods import quarter
from signal_research.finance.units import parse_numeric, to_inr_crore


def test_indian_grouping_and_missingness():
    parsed = parse_numeric("(1,23,456)")
    assert parsed.value == Decimal("-123456")
    assert parse_numeric("-").value is None
    assert parse_numeric("-").missing_reason == "not_disclosed"


def test_inr_scales():
    assert to_inr_crore(Decimal("10"), "INR million") == Decimal("1")
    assert to_inr_crore(Decimal("1"), "INR billion") == Decimal("100")
    assert to_inr_crore(Decimal('29.5'), 'INR lakh crore') == Decimal('2950000')
    assert to_inr_crore(Decimal('29.5'), 'INR trillion') == Decimal('2950000')


def test_march_fiscal_quarter():
    period = quarter("Q1 FY2027")
    assert str(period.start) == "2026-04-01"
    assert str(period.end) == "2026-06-30"


@pytest.mark.parametrize('raw', ['3170830,09', '510056,.21', '3,170,830,09', '1,234,56', '1.234,56', '1.234.56'])
def test_ocr_damaged_decimal_or_grouping_is_not_reinterpreted_as_an_amount(raw):
    assert parse_numeric(raw).value is None
    assert parse_numeric(raw).missing_reason == 'ambiguous'


@pytest.mark.parametrize('raw,value', [('3,170,830.09', '3170830.09'), ('31,70,830.09', '3170830.09'), ('31,052,504,740', '31052504740')])
def test_valid_indian_and_western_financial_grouping_remains_supported(raw, value):
    assert parse_numeric(raw).value == Decimal(value)
