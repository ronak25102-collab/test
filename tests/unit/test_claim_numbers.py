from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from signal_research.research.claim_numbers import supported_numbers


def test_currency_figures_need_their_own_fact_not_a_random_citation():
    facts = [SimpleNamespace(value_decimal=Decimal('206765.5655'), value_raw='206765.5655',
                             period_start=None, period_end=date(2024, 3, 31))]
    assert supported_numbers('Borrowings were 2,06,765.57 crore on 31 March 2024.', facts, [])
    assert not supported_numbers('Funding costs included 50,000 crore of maturities.', facts, [])
    assert not supported_numbers('Borrowings were 9,99,999 crore in 2024.', facts, [])


def test_iso_dates_and_fiscal_ranges_do_not_create_negative_or_invented_numbers():
    facts = [SimpleNamespace(value_decimal=Decimal('10'), value_raw='10',
        period_start=date(2023, 4, 1), period_end=date(2024, 3, 31))]
    assert supported_numbers('The ratio was 10% on 2024-03-31 in FY2023-24.', facts, [])
    assert supported_numbers('The ratio was 10% in 2023–24.', facts, [])
    assert not supported_numbers('The ratio was 10% on 2028-03-31.', facts, [])
