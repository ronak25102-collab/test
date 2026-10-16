from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

from signal_research.finance.calculations import NumericFact, calculate


def test_funding_mix_change_is_a_reproducible_composition_change_not_a_growth_gap():
    entity = uuid4()
    def fact(metric, value, end):
        return NumericFact(uuid4(), Decimal(value), metric, 'INR_crore', 'standalone',
                           metric + '_as_reported_v1', end, entity, currency='INR')
    facts = [fact('deposits', '200', '2026-03-31'), fact('borrowings', '50', '2026-03-31'),
             fact('deposits', '100', '2021-03-31'), fact('borrowings', '100', '2021-03-31')]
    result = calculate('deposit_borrowing_mix', facts[:2])
    assert result.available and result.output_value == Decimal('80')
    change = calculate('deposit_borrowing_mix_change', facts)
    assert change.available and change.output_value == Decimal('30')
    assert change.unit == 'percentage_points'
    assert not calculate('deposit_borrowing_mix', [facts[0], replace(facts[1], scope='consolidated')]).available
    assert not calculate('deposit_borrowing_mix', list(reversed(facts[:2]))).available
    assert not calculate('deposit_borrowing_mix', [replace(f, value=Decimal(0)) for f in facts[:2]]).available
    assert not calculate('deposit_borrowing_mix_change', facts[2:] + facts[:2]).available
