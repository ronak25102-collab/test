from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from signal_research.domain.schemas import Fact
from signal_research.finance.calculations import calculate, numeric_fact
from signal_research.research.headline import validate_headline


def test_headline_rejects_new_numbers_jargon_long_text_and_multiple_sentences():
    facts = [SimpleNamespace(value_decimal=Decimal('69'), period_start=None, period_end=date(y, 3, 31)) for y in (2023, 2026)]
    good = 'Example Finance restored 69% of its pre-event funding mix from 2023 to 2026.'
    assert not validate_headline(good, 'Example Finance', facts, [])
    for bad in [good + ' Another sentence.', good.replace('69%', '78%'), good.replace('funding mix', 'CASA'),
                good.replace('restored', ' '.join(['word'] * 36))]:
        assert validate_headline(bad, 'Example Finance', facts, [])


def test_recovery_is_reproduced_from_verified_ordered_ratio_facts():
    entity = uuid4()
    facts = [Fact(id=uuid4(), entity_id=entity, metric_key='casa_ratio', value_decimal=value,
                  unit_normalized='percent', period_type='instant', scope='standalone',
                  period_end=f'{year}-03-31', definition_id='casa_as_reported_v1', passage_id=uuid4(), status='verified')
             for year, value in [(2026, '43.8'), (2024, '30'), (2023, '50')]]
    result = calculate('recovery_ratio', [numeric_fact(f) for f in facts])
    assert result.available and result.output_value == 69
    assert not calculate('recovery_ratio', [numeric_fact(f) for f in reversed(facts)]).available
