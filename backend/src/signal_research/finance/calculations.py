from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

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
    period_start: str | None = None
    period_type: str = "instant"
    segment: str = "all"
    currency: str | None = None


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


def _growth_gap(values: list[Decimal], parameters: dict) -> Decimal:
    return _positive_growth(values[:2], parameters) - _positive_growth(values[2:], parameters)


def _ldr_change(values: list[Decimal], parameters: dict) -> Decimal:
    return _loan_to_deposit([values[0], values[2]], parameters) - _loan_to_deposit([values[1], values[3]], parameters)


def _deposit_borrowing_mix(values: list[Decimal], _: dict) -> Decimal:
    deposits, borrowings = values
    if deposits < 0 or borrowings < 0 or deposits + borrowings <= 0:
        raise ValueError('deposit/borrowing mix requires non-negative components and a positive total')
    return deposits / (deposits + borrowings) * Decimal('100')


def _deposit_borrowing_mix_change(values: list[Decimal], parameters: dict) -> Decimal:
    return _deposit_borrowing_mix(values[:2], parameters) - _deposit_borrowing_mix(values[2:], parameters)


def _recovery_ratio(values: list[Decimal], _: dict) -> Decimal:
    current, trough, before = values
    if before <= trough or current < trough:
        raise ValueError('recovery needs a pre-break level above the verified post-break trough')
    return (current - trough) / (before - trough) * Decimal('100')


def _recovery_mix(values: list[Decimal], parameters: dict) -> Decimal:
    ratios = [_deposit_borrowing_mix(values[i:i + 2], parameters) for i in (0, 2, 4)]
    return _recovery_ratio(ratios, parameters)


FORMULAS: dict[str, tuple[str, Formula, str]] = {
    'recovery_ratio': ('1.0', _recovery_ratio, 'percent'),
    'recovery_ratio_funding_mix': ('1.0', _recovery_mix, 'percent'),
    "yoy_growth": ("1.0", _positive_growth, "percent"),
    "share_pct": ("1.0", _share, "percent"),
    "change_pp": ("1.0", _change_pp, "percentage_points"),
    "change_bps": ("1.0", _change_bps, "basis_points"),
    "cagr": ("1.0", _cagr, "percent"),
    "loan_to_deposit": ("1.0", _loan_to_deposit, "percent"),
    "growth_gap": ("1.0", _growth_gap, "percentage_points"),
    "ldr_change": ("1.0", _ldr_change, "percentage_points"),
    'deposit_borrowing_mix': ('1.0', _deposit_borrowing_mix, 'percent'),
    'deposit_borrowing_mix_change': ('1.0', _deposit_borrowing_mix_change, 'percentage_points'),
    "vnb_to_ape": ("1.0", _share, "percent"),
    "fee_yield": ("1.0", _share, "percent"),
    "funding_share": ("1.0", _share, "percent"),
    "profit_margin": ("1.0", _share, "percent"),
    "transaction_revenue_share": ("1.0", _share, "percent"),
}


def comparable(formula_id: str, facts: list[NumericFact]) -> list[str]:
    expected = 6 if formula_id == 'recovery_ratio_funding_mix' else 3 if formula_id == 'recovery_ratio' else 4 if formula_id in {"growth_gap", "ldr_change", 'deposit_borrowing_mix_change'} else 2
    if len(facts) != expected:
        raise ValueError(f"{formula_id} requires {expected} facts")
    for field_name in ("entity_id", "unit", "scope", "segment", "currency", "period_type"):
        if len({str(getattr(f, field_name)) for f in facts}) != 1:
            raise ValueError(f"incomparable {field_name}")
    if any(not isinstance(f.value, Decimal) or not f.value.is_finite() for f in facts):
        raise ValueError("non-finite input")
    if formula_id.startswith('recovery_ratio'):
        levels = facts
        if formula_id == 'recovery_ratio_funding_mix':
            for i in (0, 2, 4):
                comparable('deposit_borrowing_mix', facts[i:i + 2])
            levels = facts[::2]
            if len({f.definition_id for f in facts[1::2]}) != 1:
                raise ValueError('recovery component definitions differ')
        if len({f.metric_key for f in levels}) != 1 or len({f.definition_id for f in levels}) != 1:
            raise ValueError('recovery metric definitions differ')
        if levels[0].period_type != 'instant' or not (levels[0].period > levels[1].period > levels[2].period):
            raise ValueError('recovery requires ordered current, post-break trough, pre-break stock dates')
        if formula_id == 'recovery_ratio' and facts[0].unit != 'percent':
            raise ValueError('recovery requires a verified ratio or percentage')
    elif formula_id == 'deposit_borrowing_mix_change':
        comparable('deposit_borrowing_mix', facts[:2])
        comparable('deposit_borrowing_mix', facts[2:])
        if date.fromisoformat(facts[0].period) <= date.fromisoformat(facts[2].period):
            raise ValueError('current mix must follow the prior mix')
        if facts[0].definition_id != facts[2].definition_id or facts[1].definition_id != facts[3].definition_id:
            raise ValueError('mix component definitions differ')
    elif formula_id in {"growth_gap", "ldr_change"}:
        comparable("yoy_growth", facts[:2])
        comparable("yoy_growth", facts[2:])
        if facts[0].period != facts[2].period or facts[1].period != facts[3].period:
            raise ValueError("growth intervals differ")
        if formula_id == "ldr_change" and [facts[0].metric_key, facts[2].metric_key] != ["gross_advances", "deposits"]:
            raise ValueError("LDR requires advances and deposits")
    elif formula_id in {"yoy_growth", "change_pp", "change_bps", "cagr"}:
        if len({f.metric_key for f in facts}) != 1 or len({f.definition_id for f in facts}) != 1:
            raise ValueError("metric definitions differ")
        current, prior = facts if formula_id != "cagr" else list(reversed(facts))
        try:
            end, start = date.fromisoformat(current.period), date.fromisoformat(prior.period)
        except ValueError as exc:
            raise ValueError("explicit comparable dates are required") from exc
        if end <= start:
            raise ValueError("current date must follow prior date")
        if formula_id == "yoy_growth" and (end.month, end.day, end.year - start.year) != (start.month, start.day, 1):
            raise ValueError("year-on-year endpoints must be one year apart")
        if current.period_type == "duration":
            if not current.period_start or not prior.period_start:
                raise ValueError("duration starts are required")
            a, b = date.fromisoformat(current.period_start), date.fromisoformat(prior.period_start)
            if (a.month, a.day) != (b.month, b.day) or abs((end - a).days - (start - b).days) > 1:
                raise ValueError("duration windows differ")
        if formula_id in {"change_pp", "change_bps"} and facts[0].unit != "percent":
            raise ValueError("percentage changes require percentage inputs")
    else:
        if facts[0].period != facts[1].period or facts[0].period_start != facts[1].period_start:
            raise ValueError("ratio periods differ")
        if formula_id == "loan_to_deposit" and [f.metric_key for f in facts] != ["gross_advances", "deposits"]:
            raise ValueError("LDR requires advances and deposits")
        if formula_id == 'deposit_borrowing_mix' and ([f.metric_key for f in facts] != ['deposits', 'borrowings']
                                                     or facts[0].period_type != 'instant' or facts[0].unit != 'INR_crore'):
            raise ValueError('deposit/borrowing mix requires disclosed comparable deposit and borrowing stocks')
        expected_keys = {"vnb_to_ape": ["vnb", "ape"], "fee_yield": ["fee_revenue", "average_aum"],
                         "profit_margin": ["net_profit", "revenue"],
                         "transaction_revenue_share": ["transaction_revenue", "revenue"]}
        if formula_id in expected_keys and [f.metric_key for f in facts] != expected_keys[formula_id]:
            raise ValueError("ratio metric definitions differ")
        if formula_id == "funding_share":
            if facts[0].metric_key not in {"bank_borrowings", "bond_borrowings"} or facts[1].metric_key != "borrowings":
                raise ValueError("funding share requires a disclosed borrowing component and total borrowings")
        if formula_id in {"funding_share", "transaction_revenue_share"} and not (0 <= facts[0].value <= facts[1].value):
            raise ValueError("disclosed component must be non-negative and no larger than its total")
    return ["same entity, unit, currency, scope, segment and period type", "formula-specific metric and period checks passed"]


def numeric_fact(fact) -> NumericFact:
    if fact.value_decimal is None:
        raise ValueError("missing calculation input")
    return NumericFact(fact.id, fact.value_decimal, fact.metric_key, fact.unit_normalized or "", fact.scope,
                       fact.definition_id, str(fact.period_end), fact.entity_id, str(fact.period_start) if fact.period_start else None,
                       fact.period_type.value, fact.segment, fact.currency)


def calculate(formula_id: str, facts: list[NumericFact], parameters: dict | None = None) -> CalculationResult:
    parameters = parameters or {}
    if formula_id not in FORMULAS:
        raise KeyError(f"unregistered formula: {formula_id}")
    version, formula, unit = FORMULAS[formula_id]
    try:
        checks = comparable(formula_id, facts)
        output = formula([fact.value for fact in facts], parameters)
    except (ValueError, InvalidOperation, ArithmeticError) as exc:
        return CalculationResult(
            uuid4(), formula_id, version, [fact.id for fact in facts], None, unit,
            [str(exc)], available=False,
        )
    identifier = uuid5(NAMESPACE_URL, f"{formula_id}|{version}|{[str(f.id) for f in facts]}|{sorted(parameters.items())}")
    return CalculationResult(identifier, formula_id, version, [fact.id for fact in facts], output, unit, comparability_checks=checks)


def calculation_context(result: CalculationResult, facts: list[NumericFact]) -> dict:
    return {
        "formula_id": result.formula_id,
        "formula_version": result.formula_version,
        "inputs": [{"fact_id": str(f.id), "value": str(f.value), "unit": f.unit} for f in facts],
        "output": None if result.output_value is None else str(result.output_value),
        "unit": result.unit,
        "limitations": result.limitations,
    }
