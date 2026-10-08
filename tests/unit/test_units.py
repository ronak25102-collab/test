from decimal import Decimal

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


def test_march_fiscal_quarter():
    period = quarter("Q1 FY2027")
    assert str(period.start) == "2026-04-01"
    assert str(period.end) == "2026-06-30"
