from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from signal_research.domain.schemas import Fact
from signal_research.research.live import derive_calculations
from signal_research.research.story import quarter_ends, timeline_story


def test_quarter_target_and_source_bound_reversal_onset():
    assert len(quarter_ends(date(2026, 10, 16))) == 12
    assert quarter_ends(date(2026, 10, 16))[0] == date(2026, 9, 30)
    entity, doc, pid = uuid4(), uuid4(), uuid4()
    facts = [Fact(id=uuid4(), entity_id=entity, metric_key='aum', value_decimal=v, unit_normalized='INR_crore',
                  currency='INR', period_end=end, period_type='instant', scope='standalone', definition_id='aum_as_reported_v1',
                  passage_id=pid, status='verified') for end, v in [('2025-12-31', 100), ('2026-03-31', 110), ('2026-06-30', 90), ('2026-09-30', 95)]]
    story = timeline_story(facts, derive_calculations(facts), [SimpleNamespace(id=pid, document_id=doc)],
                           [SimpleNamespace(id=doc, canonical_url='https://issuer.example/results')], [])
    assert len(story['events']) == 4
    assert story['onsets'][0]['estimate']['date'] == '2026-06-30'
    assert story['onsets'][0]['estimate']['calculation_ids']
    assert all(e['passage_id'] == str(pid) for e in story['events'])
