from decimal import Decimal
from uuid import uuid4

from signal_research.domain.enums import Scope
from signal_research.finance.calculations import NumericFact, calculate

ENTITY = uuid4()


def fact(value: str, metric="gross_advances", period="2026-03-31") -> NumericFact:
    return NumericFact(uuid4(), Decimal(value), metric, "INR_crore", Scope.CONSOLIDATED, metric, period, ENTITY)


def test_synthetic_growth_and_gap():
    inputs = [fact("120000"), fact("100000", period="2025-03-31"), fact("137500", "deposits"), fact("125000", "deposits", "2025-03-31")]
    advances = calculate("yoy_growth", inputs[:2])
    deposits = calculate("yoy_growth", inputs[2:])
    gap = calculate("growth_gap", inputs)
    assert advances.output_value == Decimal("20.0")
    assert deposits.output_value == Decimal("10.0")
    assert gap.output_value == Decimal("10.0")


def test_non_positive_growth_is_unavailable():
    result = calculate("yoy_growth", [fact("10"), fact("0", period="2025-03-31")])
    assert result.available is False
    assert result.output_value is None


def test_loan_to_deposit():
    result = calculate("loan_to_deposit", [fact("120000"), fact("137500", "deposits")])
    assert result.output_value == Decimal("87.27272727272727272727272727")
