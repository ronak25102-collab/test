from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from signal_research.domain.enums import Profile
from signal_research.domain.schemas import Passage
from signal_research.extraction.stock_ratios import stock_ratio_batch
from signal_research.extraction.validate import validate_candidate

COMPANY = SimpleNamespace(legal_name='Quartz Bank Limited')
TEXT = '''Quartz Bank Limited
UNAUDITED STANDALONE FINANCIAL RESULTS
(in crore)
Quarter ended                         Year ended
Particulars 30.06.2026 31.03.2026 30.06.2025 31.03.2026
(ii) Capital Adequacy Ratio 19.57% 19.71% 19.88% 19.71%
(iv) NPA Ratios:
(a) Gross NPAs 35846.35 34061.19 37040.80 34061.19
(b) Net NPAs 12357.27 11169.54 12275.99 11169.54
(c) % of Gross NPAs to Gross Advances 1.17% 1.15% 1.40% 1.15%
(d) % of Net NPAs to Net Advances 0.41% 0.38% 0.47% 0.38%
'''


def batch_for(text=TEXT, **kwargs):
    passage = Passage(id=uuid4(), document_id=uuid4(), text=text)
    return passage, stock_ratio_batch(passage, COMPANY, Profile.BANK, **kwargs)


def test_mixed_quarter_year_stock_ratios_keep_three_exact_dates_and_deduplicate():
    passage, batch = batch_for(focus_metrics=('gnpa', 'nnpa'))
    assert len(batch.facts) == 9
    assert [(fact.metric_key, fact.value_raw, fact.period_end) for fact in batch.facts[:3]] == [
        ('gnpa', '1.17%', date(2026, 6, 30)),
        ('gnpa', '1.15%', date(2026, 3, 31)),
        ('gnpa', '1.40%', date(2025, 6, 30)),
    ]
    assert [fact.metric_key for fact in batch.facts[3:6]] == ['nnpa'] * 3
    assert all(fact.period_type.value == 'instant' and fact.period_start is None
               and fact.scope.value == 'standalone' and fact.currency is None for fact in batch.facts)
    assert all(validate_candidate(fact, passage, uuid4(), Profile.BANK).fact for fact in batch.facts)


@pytest.mark.parametrize('change', [
    lambda text: text.replace('Quartz Bank Limited', 'Another Bank Limited'),
    lambda text: text.replace('Quartz Bank Limited', ''),
    lambda text: text.replace('STANDALONE', 'STANDALONE CONSOLIDATED'),
    lambda text: text.replace('STANDALONE', ''),
    lambda text: text.replace('30.06.2026 31.03.2026 30.06.2025 31.03.2026', 'Q1FY27 FY26 Q1FY26 FY26'),
    lambda text: text.replace('%', ''),
    lambda text: text.replace('30.06.2026', '31.06.2026'),
])
def test_ambiguous_issuer_scope_date_or_nonpercentage_cells_are_not_bound(change):
    assert batch_for(change(TEXT))[1] is None


def test_document_identity_authorizes_missing_heading_but_never_foreign_cover():
    assert batch_for(TEXT.replace('Quartz Bank Limited', ''), document_issuer_verified=True)[1]
    assert batch_for(TEXT.replace('Quartz Bank Limited', 'Another Bank Limited'), document_issuer_verified=True)[1] is None


def test_conflicting_duplicate_end_dates_withhold_entire_metric_without_harming_other_rows():
    _, batch = batch_for(TEXT.replace('1.17% 1.15% 1.40% 1.15%', '1.17% 1.15% 1.40% 1.99%'))
    assert {fact.metric_key for fact in batch.facts} == {'capital_adequacy', 'nnpa'}


def test_equal_numeric_duplicate_dates_allow_different_display_precision():
    _, batch = batch_for(TEXT.replace('1.17% 1.15% 1.40% 1.15%', '1.17% 1.15% 1.40% 1.150%'))
    assert len([fact for fact in batch.facts if fact.metric_key == 'gnpa']) == 3


def test_monetary_npa_and_duration_margin_never_become_instant_percentages():
    text = '\n'.join(TEXT.splitlines()[:5]) + '''
Gross NPAs 35846.35 34061.19 37040.80 34061.19
Net NPAs 12357.27 11169.54 12275.99 11169.54
Net interest margin 3.4% 3.5% 3.6% 3.5%
'''
    assert batch_for(text)[1] is None


def test_extra_numeric_footnotes_missing_percent_or_repeated_metric_rows_withhold_row():
    for replacement in (
        '1.17% 1.15% 1.40% 1.15% 7',
        '1.17% 1.15 1.40% 1.15%',
        '1.17% 1.15% 1.40% 1.15%\nGross NPA ratio 1.17% 1.15% 1.40% 1.15%',
    ):
        _, batch = batch_for(TEXT.replace('1.17% 1.15% 1.40% 1.15%', replacement))
        assert 'gnpa' not in {fact.metric_key for fact in batch.facts}


def test_registered_profile_restriction_and_spaced_aliases_preserved():
    passage = Passage(id=uuid4(), document_id=uuid4(), text=TEXT.replace('Gross NPAs to Gross Advances', 'Gross  NPAs to  Gross Advances'))
    assert stock_ratio_batch(passage, COMPANY, Profile.BANK)
    assert stock_ratio_batch(passage, COMPANY, Profile.LIFE_INSURER) is None


def test_verbose_extraction_note_is_not_a_financial_evidence_gate():
    import pytest
    from pydantic import ValidationError
    from signal_research.extraction.models import ExtractedFactBatch
    note = 'The disclosure is missing one requested comparison. ' * 8
    batch = ExtractedFactBatch(facts=[], notes=[note])
    assert batch.notes == [note.strip()] and batch.facts == []
    with pytest.raises(ValidationError):
        ExtractedFactBatch(facts=[], notes=['x' * 1201])
