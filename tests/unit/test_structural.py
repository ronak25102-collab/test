from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from signal_research.domain.schemas import Fact
from signal_research.research.live import LiveResearch, derive_calculations
from signal_research.research.structural import break_calculations, detect_breaks


def test_merger_jump_cannot_be_a_headline_growth_calculation():
    entity, doc = uuid4(), uuid4()
    passage = SimpleNamespace(id=uuid4(), document_id=doc, text='Acquisition and scheme of arrangement changed the reporting boundary.')
    facts = [Fact(id=uuid4(), entity_id=entity, metric_key='borrowings', value_decimal=value,
                  unit_normalized='INR_crore', currency='INR', period_type='instant',
                  period_end=date(year, 3, 31), scope='standalone', definition_id='borrowings_as_reported_v1',
                  passage_id=passage.id, status='verified') for year, value in [(2022, 100), (2023, 300), (2024, 250)]]
    breaks = detect_breaks(facts, [passage], [SimpleNamespace(id=doc, canonical_url='https://issuer.example/report')])
    assert len(breaks) == 1 and breaks[0]['passage_ids'] == [str(passage.id)]
    calculations = derive_calculations(facts)
    blocked = break_calculations(breaks, calculations)
    assert blocked
    assert all(not (c.id in blocked and c.output_value == Decimal('-16.67')) for c in calculations)
    assert all(c.output_value != 200 for c in calculations if c.id not in blocked)
    research = LiveResearch.__new__(LiveResearch)
    research.structural_breaks, research.calculations, research.limitations = breaks, calculations, []
    assert research.compose(SimpleNamespace(headline=SimpleNamespace(calculation_ids=list(blocked))), None, '') is None
