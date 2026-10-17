from datetime import date
from decimal import Decimal
from uuid import uuid4

from signal_research.domain.schemas import Fact
from signal_research.research.draft_repair import coverage_repair
from signal_research.research.live import DiscoveryDraft, Statement, derive_calculations


def test_unverified_context_bullet_can_only_be_replaced_with_existing_formula_coverage():
    entity = uuid4()
    facts = [Fact(id=uuid4(), entity_id=entity, metric_key=key, value_decimal=Decimal(value),
        unit_normalized='INR_crore', currency='INR', period_end=date(year, 3, 31), period_type='instant',
        scope='standalone', definition_id=key, status='verified', passage_id=uuid4())
        for key, year, value in [('deposits',2025,'100'),('deposits',2026,'120'),('borrowings',2025,'30'),('borrowings',2026,'25')]]
    calculations = derive_calculations(facts)
    c = next(c for c in calculations if c.formula_id == 'deposit_borrowing_mix_change')
    s = Statement(text='The reported mix changed on the same basis.', kind='derived',
        fact_ids=list(c.input_fact_ids), calculation_ids=[c.id], passage_ids=[])
    bad = s.model_copy(update={'text':'The industry norm was 99%.'})
    draft = DiscoveryDraft(headline=s, why_it_matters=[s, bad, s], counterargument=s, timeline_analysis=s,
        onset_status='unknown', falsification='A comparable reversal challenges continuation.',
        falsification_window='Next quarterly disclosure', falsification_source='Issuer financial results')
    repaired = coverage_repair(draft, facts, calculations)
    assert repaired is not None and '99%' not in repaired.model_dump_json()
    assert repaired.why_it_matters[1].text == ' '.join(c.limitations)
    assert repaired.why_it_matters[1].calculation_ids == [c.id]
    assert repaired.headline == draft.headline
    # It cannot manufacture a missing financial headline, or fill multiple gaps.
    assert coverage_repair(draft.model_copy(update={'headline':bad}), facts, calculations) is None
    assert coverage_repair(draft.model_copy(update={'why_it_matters':[bad,bad,s]}), facts, calculations) is None
