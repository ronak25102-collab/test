from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, localcontext
from uuid import UUID, uuid4

from signal_research.domain.enums import Scope


@dataclass(frozen=True)
class CalculationResult:
    id: UUID
    formula_id: str
    formula_version: str
    input_fact_ids: list[UUID]
    output_value: Decimal | None
    unit: str
    limitations: list[str] = field(default_factory=list)
    available: bool = True
    comparability_checks: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NumericFact:
    id: UUID
    value: Decimal
    metric_key: str
    unit: str
    scope: Scope | str
    definition_id: str
    period: str
    entity_id: UUID | str


Formula = Callable[[list[Decimal], dict], Decimal]


def _positive_growth(values: list[Decimal], _: dict) -> Decimal:
    current, prior = values
    if prior <= 0:
        raise ValueError("ordinary growth is unavailable for a non-positive base")
    return (current / prior - Decimal("1")) * Decimal("100")


def _share(values: list[Decimal], _: dict) -> Decimal:
    component, total = values
    if total <= 0:
        raise ValueError("share denominator must be positive")
    return component / total * Decimal("100")


def _change_pp(values: list[Decimal], _: dict) -> Decimal:
    return values[0] - values[1]


def _change_bps(values: list[Decimal], _: dict) -> Decimal:
    return (values[0] - values[1]) * Decimal("100")


def _cagr(values: list[Decimal], parameters: dict) -> Decimal:
    start, end = values
    years = Decimal(str(parameters.get("years", "1")))
    if start <= 0 or end <= 0 or years <= 0:
        raise ValueError("CAGR requires positive endpoints and a positive interval")
    with localcontext() as context:
        context.prec = 34
        return ((end / start) ** (Decimal("1") / years) - Decimal("1")) * Decimal("100")


def _loan_to_deposit(values: list[Decimal], _: dict) -> Decimal:
    advances, deposits = values
    if deposits <= 0:
        raise ValueError("deposit denominator must be positive")
    return advances / deposits * Decimal("100")


FORMULAS: dict[str, tuple[str, Formula, str]] = {
    "yoy_growth": ("1.0", _positive_growth, "percent"),
    "share_pct": ("1.0", _share, "percent"),
    "change_pp": ("1.0", _change_pp, "percentage_points"),
    "change_bps": ("1.0", _change_bps, "basis_points"),
    "cagr": ("1.0", _cagr, "percent"),
    "loan_to_deposit": ("1.0", _loan_to_deposit, "percent"),
}


def calculate(formula_id: str, facts: list[NumericFact], parameters: dict | None = None) -> CalculationResult:
    parameters = parameters or {}
    if formula_id not in FORMULAS:
        raise KeyError(f"unregistered formula: {formula_id}")
    version, formula, unit = FORMULAS[formula_id]
    try:
        output = formula([fact.value for fact in facts], parameters)
    except (ValueError, InvalidOperation, ArithmeticError) as exc:
        return CalculationResult(
            uuid4(), formula_id, version, [fact.id for fact in facts], None, unit,
            [str(exc)], available=False,
        )
    return CalculationResult(uuid4(), formula_id, version, [fact.id for fact in facts], output, unit)


def calculation_context(result: CalculationResult, facts: list[NumericFact]) -> dict:
    return {
        "formula_id": result.formula_id,
        "formula_version": result.formula_version,
        "inputs": [{"fact_id": str(f.id), "value": str(f.value), "unit": f.unit} for f in facts],
        "output": None if result.output_value is None else str(result.output_value),
        "unit": result.unit,
        "limitations": result.limitations,
    }
