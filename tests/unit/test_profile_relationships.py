from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest
from signal_research.domain.schemas import Fact
from signal_research.finance.calculations import NumericFact, calculate
from signal_research.research.live import derive_calculations


@pytest.mark.parametrize('formula,numerator,denominator', [
    ('funding_share', 'bank_borrowings', 'borrowings'),
    ('funding_share', 'bond_borrowings', 'borrowings'),
    ('profit_margin', 'net_profit', 'revenue'),
    ('transaction_revenue_share', 'transaction_revenue', 'revenue'),
])
def test_profile_ratio_requires_exact_metrics_and_comparable_scope(formula, numerator, denominator):
    entity = uuid4()
    def fact(key, value):
        return NumericFact(uuid4(), Decimal(value), key, 'INR_crore', 'standalone', key,
                           '2026-03-31', entity)
    a, b = fact(numerator, '25'), fact(denominator, '100')
    assert calculate(formula, [a, b]).output_value == Decimal('25')
    assert not calculate(formula, [a, replace(b, scope='consolidated')]).available
    assert not calculate(formula, [a, replace(b, metric_key='unrelated_total')]).available
    assert not calculate(formula, [a, replace(b, period='2025-03-31')]).available


def test_managed_assets_and_funding_growth_are_compared_without_becoming_on_book_loans():
    entity, passage = uuid4(), uuid4()
    facts = [Fact(id=uuid4(), entity_id=entity, metric_key=metric, value_decimal=value,
                  period_end=f'{year}-03-31', period_type='instant', scope='standalone',
                  definition_id=metric, unit_normalized='INR_crore', currency='INR',
                  status='verified', passage_id=passage)
             for metric, value, year in [('aum', 120, 2026), ('aum', 100, 2025),
                                         ('borrowings', 110, 2026), ('borrowings', 100, 2025)]]
    gap = next(c for c in derive_calculations(facts) if c.formula_id == 'growth_gap')
    assert gap.output_value == Decimal('10')
    assert len(gap.input_fact_ids) == 4
    assert not any(c.formula_id == 'loan_to_deposit' for c in derive_calculations(facts))


def test_a_funding_component_cannot_exceed_total_borrowings():
    entity = uuid4()
    a = NumericFact(uuid4(), Decimal('101'), 'bank_borrowings', 'INR_crore', 'standalone',
                    'bank_borrowings', '2026-03-31', entity)
    b = replace(a, id=uuid4(), value=Decimal('100'), metric_key='borrowings', definition_id='borrowings')
    assert not calculate('funding_share', [a, b]).available


def test_ratio_changes_have_reproducible_percentage_point_and_basis_point_outputs():
    from signal_research.research.numeric_claims import supported_percentages

    entity, passage = uuid4(), uuid4()
    facts = [Fact(id=uuid4(), entity_id=entity, metric_key='gnpa', value_decimal=value,
        period_end=f'{year}-06-30', period_type='instant', scope='consolidated',
        definition_id='gnpa_v1', unit_normalized='percent', status='verified', passage_id=passage)
        for value, year in [('0.96', 2026), ('1.03', 2025)]]
    calculations = derive_calculations(facts)
    assert {c.formula_id: c.output_value for c in calculations} == {
        'change_pp': Decimal('-0.07'), 'change_bps': Decimal('-7.00')}
    assert supported_percentages('GNPA declined 7 basis points', facts, calculations)
    assert not supported_percentages('GNPA declined 11 basis points', facts, calculations)
    assert all(len(c.input_fact_ids) == 2 for c in calculations)
