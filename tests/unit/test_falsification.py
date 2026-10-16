from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

from signal_research.research.falsification import filing_cadence


def test_next_quarter_date_uses_observed_filing_cadence_not_an_invented_promise():
    docs, facts, passages = [], [], []
    for period, published in [(date(2026, 3, 31), datetime(2026, 4, 20, tzinfo=UTC)),
                               (date(2026, 6, 30), datetime(2026, 7, 20, tzinfo=UTC))]:
        d, p = uuid4(), uuid4()
        docs.append(SimpleNamespace(id=d, published_at=published, document_type='issuer_disclosure'))
        facts.append(SimpleNamespace(passage_id=p, period_end=period))
        passages.append(SimpleNamespace(id=p, document_id=d))
    cadence = filing_cadence(facts, passages, docs, date(2026, 10, 16))
    assert cadence['next_quarter_end'] == '2026-09-30'
    assert cadence['expected_disclosure_date'] == '2026-10-20'
    assert len(cadence['samples']) == 2
    assert filing_cadence(facts[:1], passages[:1], docs[:1], date(2026, 10, 16))['expected_disclosure_date'] is None
