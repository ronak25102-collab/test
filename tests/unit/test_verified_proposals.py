from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from signal_research.domain.enums import Profile, Scope
from signal_research.domain.schemas import Fact
from signal_research.research.live import derive_calculations
from signal_research.research.numeric_claims import supported_percentages
from signal_research.research.proposals import verified_proposals


def facts_for(profile, rows):
    entity = uuid4()
    company = SimpleNamespace(id=entity, legal_name='Quartz Financial Limited', business_profiles=[profile])
    facts = [Fact(id=uuid4(), entity_id=entity, metric_key=metric, value_decimal=Decimal(value),
        unit_normalized='percent' if metric == 'gnpa' else 'INR_crore',
        currency=None if metric == 'gnpa' else 'INR', period_end=date(year, 3, 31),
        period_type='instant', scope='standalone', definition_id=metric, status='verified', passage_id=uuid4())
        for metric, year, value in rows]
    return company, facts


def test_source_bound_funding_proposals_are_unconfirmed_and_use_registered_math_only():
    company, facts = facts_for(Profile.BANK, [('deposits',2025,'100'),('deposits',2026,'120'),
                                           ('borrowings',2025,'30'),('borrowings',2026,'25')])
    calculations = derive_calculations(facts)
    batch = verified_proposals(company, facts, calculations, [])
    assert batch.candidates
    for h in batch.candidates:
        linked = [c for c in calculations if c.id in h.calculation_ids]
        assert supported_percentages(h.statement, facts, linked)
        assert 'not an established causal explanation' in h.mechanism
        assert set(h.fact_ids) == {i for c in linked for i in c.input_fact_ids}


def test_fast_proposals_do_not_lead_with_structural_break_via_a_mix_change():
    company, facts = facts_for(Profile.BANK, [('deposits',2025,'100'),('deposits',2026,'120'),
                                           ('borrowings',2025,'30'),('borrowings',2026,'100')])
    event = {'fact_ids': [str(f.id) for f in facts if f.metric_key == 'borrowings']}
    assert not verified_proposals(company, facts, derive_calculations(facts), [event]).candidates


def test_nbfc_growth_quality_uses_matching_scopes_and_periods_without_deposits():
    company, facts = facts_for(Profile.NBFC, [('aum',2025,'100'),('aum',2026,'120'),
                                           ('gnpa',2025,'1'),('gnpa',2026,'1.5')])
    batch = verified_proposals(company, facts, derive_calculations(facts), [])
    assert batch.candidates and all('deposits' not in h.statement for h in batch.candidates)
    facts[-1].scope = Scope.CONSOLIDATED
    assert not verified_proposals(company, facts, derive_calculations(facts), []).candidates
