from decimal import Decimal
from uuid import uuid4

from signal_research.domain.enums import Scope
from signal_research.finance.calculations import NumericFact, calculate


def fact(value: str) -> NumericFact:
    return NumericFact(uuid4(), Decimal(value), "metric", "INR_crore", Scope.CONSOLIDATED, "definition", "FY", uuid4())


def test_synthetic_growth_and_gap():
    advances = calculate("yoy_growth", [fact("120000"), fact("100000")])
    deposits = calculate("yoy_growth", [fact("137500"), fact("125000")])
    gap = calculate("change_pp", [NumericFact(uuid4(), advances.output_value, "growth", "percent", "", "", "", ""), NumericFact(uuid4(), deposits.output_value, "growth", "percent", "", "", "", "")])
    assert advances.output_value == Decimal("20.0")
    assert deposits.output_value == Decimal("10.0")
    assert gap.output_value == Decimal("10.0")


def test_non_positive_growth_is_unavailable():
    result = calculate("yoy_growth", [fact("10"), fact("0")])
    assert result.available is False
    assert result.output_value is None


def test_loan_to_deposit():
    result = calculate("loan_to_deposit", [fact("120000"), fact("137500")])
    assert result.output_value == Decimal("87.27272727272727272727272727")
