from uuid import uuid4

from signal_research.domain.enums import PeriodType, Scope
from signal_research.domain.schemas import Fact
from signal_research.research.history import (
    comparable_series,
    has_relationship_evidence,
    needs_history,
)


def make_fact(entity, period, *, scope='standalone', definition='aum_as_reported_v1'):
    return Fact(id=uuid4(), entity_id=entity, metric_key='aum', value_decimal=100,
                unit_normalized='INR_crore', currency='INR', period_end=period,
                period_type='instant', scope=scope, definition_id=definition,
                passage_id=uuid4(), status='verified')


def test_same_scope_definition_and_endpoint_form_a_chronological_series():
    entity = uuid4()
    facts = [make_fact(entity, f'{year}-03-31') for year in [2026, 2024, 2025]]
    series = comparable_series(facts)
    assert len(series) == 1 and series[0]['coverage'] == 'multi_period'
    assert [str(o['period_end']) for o in series[0]['observations']] == ['2024-03-31', '2025-03-31', '2026-03-31']
    assert not needs_history(facts)


def test_mismatched_endpoint_scope_entity_and_definition_cannot_prove_a_trend():
    entity = uuid4()
    facts = [make_fact(entity, '2026-03-31'), make_fact(entity, '2025-03-31'),
             make_fact(entity, '2024-06-30'), make_fact(entity, '2024-03-31', scope='consolidated'),
             make_fact(uuid4(), '2024-03-31'), make_fact(entity, '2024-03-31', definition='on_book_loans')]
    assert needs_history(facts)
    assert max(s['comparable_periods'] for s in comparable_series(facts)) == 2
    assert all(s['limitations'] for s in comparable_series(facts))


def test_one_growth_metric_does_not_stop_financial_statement_recovery():
    from types import SimpleNamespace

    entity = uuid4()
    a, b = make_fact(entity, '2026-03-31'), make_fact(entity, '2025-03-31')
    single = SimpleNamespace(input_fact_ids=[a.id, b.id])
    assert not has_relationship_evidence([a, b], [single])
    c = make_fact(entity, '2026-03-31').model_copy(update={'metric_key': 'borrowings'})
    relationship = SimpleNamespace(input_fact_ids=[a.id, c.id])
    assert has_relationship_evidence([a, b, c], [single, relationship])


def test_consecutive_quarters_are_visible_without_mixing_them_into_annual_comparisons():
    entity = uuid4()
    facts = [make_fact(entity, end) for end in ['2025-12-31', '2026-03-31', '2026-06-30']]
    quarterly = [s for s in comparable_series(facts) if s['cadence'] == 'quarterly']
    assert len(quarterly) == 1 and quarterly[0]['comparable_periods'] == 3
    assert quarterly[0]['limitations']
    assert not needs_history(facts)
    facts[1].scope = Scope.CONSOLIDATED
    assert not any(s['cadence'] == 'quarterly' for s in comparable_series(facts))


def test_quarterly_series_excludes_cumulative_ytd_duration_windows():
    from datetime import date
    entity = uuid4()
    facts = [make_fact(entity, end).model_copy(update={'period_type': PeriodType.DURATION, 'period_start': date(2026, 1, 1)})
             for end in ['2026-03-31', '2026-06-30', '2026-09-30']]
    # Construct validated enums after the deliberate source-window changes.
    facts = [Fact.model_validate(f.model_dump()) for f in facts]
    assert not any(s['cadence'] == 'quarterly' for s in comparable_series(facts))
