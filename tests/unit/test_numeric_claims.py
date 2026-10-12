from types import SimpleNamespace

from signal_research.research.numeric_claims import (
    complete_calculation_lineage,
    supported_percentages,
)


def test_invented_ratios_are_rejected_and_rounded_verified_values_allowed():
    calculations = [SimpleNamespace(output_value='94.5870967', unit='percent'),
                    SimpleNamespace(output_value='-1.909541', unit='percentage_points')]
    assert supported_percentages('Ratio 94.6%, down 1.9 percentage points.', [], calculations)
    assert not supported_percentages('Ratio decreased from 108.1% to 94.6%.', [], calculations)
    assert not supported_percentages('Ratio fell 13.5 percentage points.', [], calculations)
    assert supported_percentages('Ratio down 1.9 pp.', [], calculations)
    assert not supported_percentages('Ratio down 94.6 pp.', [], calculations)
    assert not supported_percentages('Ratio down 1.9%.', [], calculations)


def test_missing_numeric_links_only_use_unique_verified_arithmetic_on_bound_facts():
    gap = SimpleNamespace(id='gap', input_fact_ids=['a', 'b', 'c', 'd'], output_value='5.66', unit='percentage_points')
    growth = SimpleNamespace(id='growth', input_fact_ids=['a', 'b'], output_value='19.63', unit='percent')
    alien = SimpleNamespace(id='alien', input_fact_ids=['x', 'y'], output_value='13.97', unit='percent')
    assert complete_calculation_lineage('19.63%, gap 5.66 pp', [], ['gap'], [gap, growth, alien]) == ['gap', 'growth']
    assert complete_calculation_lineage('13.97%', [], ['gap'], [gap, growth, alien]) == ['gap']
    assert complete_calculation_lineage('108.1%', [], ['gap'], [gap, growth]) == ['gap']
    duplicate = SimpleNamespace(id='duplicate', input_fact_ids=['c', 'd'], output_value='19.63', unit='percent')
    assert complete_calculation_lineage('19.63%', [], ['gap'], [gap, growth, duplicate]) == ['gap']


def test_plain_balance_sheet_advances_are_not_gross_loans():
    from datetime import date
    from uuid import uuid4

    from signal_research.domain.enums import Profile
    from signal_research.domain.schemas import Passage
    from signal_research.extraction.models import ExtractedFactCandidate
    from signal_research.extraction.validate import validate_candidate
    passage = Passage(id=uuid4(), document_id=uuid4(), text='Standalone INR crore at 31 March 2026. Advances 100.')
    candidate = ExtractedFactCandidate(metric_key='gross_advances', value_raw='100', unit_raw='INR crore', currency='INR',
        period_end=date(2026, 3, 31), scope='standalone', passage_id=passage.id, extraction_confidence='0.99')
    assert validate_candidate(candidate, passage, uuid4(), Profile.BANK).fact is None
