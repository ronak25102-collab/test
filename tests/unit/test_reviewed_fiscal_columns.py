from datetime import date
from uuid import uuid4

from signal_research.domain.schemas import Passage
from signal_research.extraction.dates import reviewed_table_column_periods, source_dates


def table(text, column):
    return Passage(id=uuid4(), document_id=uuid4(), text=text, extraction_method='pdf_table',
                   row_label='Value of new business', column_label=column)


def test_fiscal_comparison_requires_the_same_sources_complete_calendar_anchor():
    source = ('Performance for the half year ended September 30, 2026. '
              'H1 FY27 H1 FY26 Value of new business 2,037 1,818 INR crore standalone')
    result = reviewed_table_column_periods(table(source, 'H1 FY26'))
    assert result[0]['period_start'] == date(2025, 4, 1)
    assert result[0]['period_end'] == date(2025, 9, 30)
    assert not reviewed_table_column_periods(table(source.replace(
        'half year ended September 30, 2026', 'H1 FY27'), 'H1 FY26'))
    assert not reviewed_table_column_periods(table(source, 'H1 FY25'))
    assert not reviewed_table_column_periods(table(source, 'FY26'))


def test_fiscal_quarter_and_annual_durations_are_not_interchangeable():
    source = ('Performance for the quarter ended June 30, 2026. '
              'Q1-FY 2027 Q1-FY 2026 Value of new business 14.1 10.9 INR billion standalone')
    result = reviewed_table_column_periods(table(source, 'Q1-FY 2026'))
    assert result[0]['period_start'] == date(2025, 4, 1)
    assert result[0]['period_end'] == date(2025, 6, 30)
    assert not reviewed_table_column_periods(table(source, 'FY 2026'))


def test_pdf_superscript_ordinals_do_not_remove_complete_dates():
    assert source_dates('quarter ended 30\n th September, 2025') == [date(2025, 9, 30)]
    assert source_dates('Friday 26th. April, 2024') == [date(2024, 4, 26)]
