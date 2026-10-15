from datetime import date
from uuid import uuid4

from signal_research.domain.enums import Profile
from signal_research.domain.schemas import Passage
from signal_research.extraction.dates import declared_duration_periods
from signal_research.extraction.models import ExtractedFactCandidate
from signal_research.extraction.validate import validate_candidate


def test_declared_year_and_quarter_are_exact_but_bare_fy_is_not():
    assert declared_duration_periods('FY2026 Q1 FY25') == []
    assert declared_duration_periods('Year ended 31 March 2026')[0]['period_start'] == date(2025, 4, 1)
    assert declared_duration_periods('Three months ended 30 June 2026')[0]['period_start'] == date(2026, 4, 1)
    assert declared_duration_periods('Year ended 15 March 2026') == []


def test_duration_requires_its_own_exact_header():
    passage = Passage(id=uuid4(), document_id=uuid4(), text='Consolidated net profit INR 100 crore. Year ended 31 March 2026.')
    candidate = ExtractedFactCandidate(metric_key='net_profit', value_raw='100', unit_raw='INR crore', currency='INR',
        period_type='duration', period_start=date(2025, 4, 1), period_end=date(2026, 3, 31), scope='consolidated',
        passage_id=passage.id, extraction_confidence='0.99')
    assert validate_candidate(candidate, passage, uuid4(), Profile.NBFC).fact
    candidate.period_start = date(2026, 1, 1)
    assert not validate_candidate(candidate, passage, uuid4(), Profile.NBFC).fact


def test_a_comparative_end_date_cannot_be_reused_as_a_duration_start():
    passage = Passage(id=uuid4(), document_id=uuid4(), text=(
        'Consolidated Q1 FY27 cost of funds was 7.40%. '
        'Customer franchise as of 30 June 2026; AUM as of 30 June 2025.'))
    candidate = ExtractedFactCandidate(metric_key='funding_cost', value_raw='7.40%', unit_raw='percent',
        period_type='duration', period_start=date(2025, 6, 30), period_end=date(2026, 6, 30),
        scope='consolidated', passage_id=passage.id, extraction_confidence='0.99')
    validation = validate_candidate(candidate, passage, uuid4(), Profile.NBFC)
    assert not validation.fact and 'one explicit reporting interval' in validation.reason


def test_explicit_reporting_ranges_bind_dates_as_a_pair():
    from signal_research.extraction.dates import explicit_duration_ranges

    for text in ['from 1 April 2025 to 31 March 2026',
                 'between 1 April 2025 and 31 March 2026',
                 '1 April 2025 through 31 March 2026']:
        periods = explicit_duration_ranges(text)
        assert periods[0]['period_start'] == date(2025, 4, 1)
        assert periods[0]['period_end'] == date(2026, 3, 31)
    assert not explicit_duration_ranges('As at 31 March 2025 and 31 March 2026')
    assert not explicit_duration_ranges('31 March 2026 to 1 April 2025')


def test_release_dateline_dates_source_but_snapshot_date_does_not():
    from signal_research.retrieval.metadata import source_publication
    assert source_publication(b'%PDF', 'NEWS RELEASE\nMumbai, April 18, 2026\nStandalone results').date() == date(2026, 4, 18)
    assert source_publication(b'%PDF', 'NEWS RELEASE\nBalance sheet at March 31, 2026') is None
    assert source_publication(b'%PDF', 'Q1FY27\nEarnings Presentation\nJuly 18, 2026').date() == date(2026, 7, 18)


def test_exchange_domain_is_not_issuer_proof_for_an_exchange_company():
    from types import SimpleNamespace

    from signal_research.retrieval.metadata import source_origin
    company = SimpleNamespace(id=uuid4(), legal_name='Example Exchange Limited', isin='INE000000001', verified_ir_domains=['bseindia.com'])
    foreign = 'To Example Exchange Limited. Financial results of Different Issuer. For Different Issuer Limited.'
    assert source_origin('https://bseindia.com/filing.pdf', company, 'Financial results', foreign)[2] == 'public_context'
    own = 'Example Exchange Limited financial results. For Example Exchange Limited.'
    assert source_origin('https://bseindia.com/filing.pdf', company, 'Financial results', own)[2] == 'issuer_disclosure'


def test_explicit_short_year_day_month_is_not_a_fiscal_quarter():
    from signal_research.extraction.dates import source_dates
    assert source_dates("30th June’26 30th June'25 Q1FY27") == [date(2025, 6, 30), date(2026, 6, 30)]
    assert source_dates('Q1FY27 June 26') == []


def test_short_explicit_date_still_requires_source_scope_and_unit():
    passage = Passage(id=uuid4(), document_id=uuid4(), text="Standalone INR crore balance sheet as on 30th June’26 and 30th June’25\nDeposits 100 90")
    fact = ExtractedFactCandidate(metric_key='deposits', value_raw='100', unit_raw='INR crore', currency='INR', period_end=date(2026, 6, 30), scope='standalone', passage_id=passage.id, extraction_confidence='.99')
    assert validate_candidate(fact, passage, uuid4(), Profile.BANK).fact
    assert not validate_candidate(fact.model_copy(update={'period_end': date(2027, 6, 30)}), passage, uuid4(), Profile.BANK).fact
    assert not validate_candidate(fact.model_copy(update={'scope': 'consolidated'}), passage, uuid4(), Profile.BANK).fact


def test_hyphenated_month_dates_and_explicit_compound_durations():
    from signal_research.extraction.dates import source_dates
    assert source_dates('31-Dec-2025 31/Mar/2025') == [date(2025, 3, 31), date(2025, 12, 31)]
    assert source_dates('30-Feb-2025 Q3FY26') == []
    periods = declared_duration_periods('Quarter and Nine Months ended December 31, 2025')
    assert {(p['period_start'],p['period_end']) for p in periods} == {(date(2025, 10, 1),date(2025, 12, 31)), (date(2025, 4, 1),date(2025, 12, 31))}
    assert declared_duration_periods('Quarter and nine months Q3FY26') == []
