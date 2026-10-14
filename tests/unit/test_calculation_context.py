from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from signal_research.domain.schemas import Calculation
from signal_research.research.calculation_context import calculation_context
from signal_research.research.live import cited_hypothesis_schema


def test_growth_gap_bindings_follow_formula_order_even_when_source_facts_are_reordered():
    facts = [SimpleNamespace(id=uuid4(), metric_key=metric, value_decimal=Decimal(value),
        period_start=None, period_end=date(year, 3, 31), scope='standalone', segment='all',
        definition_id=metric + '_v1') for metric, value, year in
        [('deposits', '1000', 2026), ('deposits', '900', 2025),
         ('borrowings', '200', 2026), ('borrowings', '220', 2025)]]
    ids = [facts[i].id for i in [2, 3, 0, 1]]
    calculation = Calculation(id=uuid4(), formula_id='growth_gap', formula_version='1.0',
        input_fact_ids=ids, output_value=Decimal('-20.2020202020202'), unit='percentage_points',
        period='2026/2025', scope='standalone', precision=2)
    context = calculation_context(calculation, facts)
    assert [binding['id'] for binding in context['input_bindings']] == ids
    assert [binding['role'] for binding in context['input_bindings']] == [
        'first_current', 'first_prior', 'second_current', 'second_prior']
    assert context['output_display'] == '-20.20'
    assert context['output_value'] == str(calculation.output_value)
    assert 'borrowings minus YoY growth in deposits' in context['reading']
    assert 'not a change in the gap' in context['reading']


def test_hypothesis_schema_offers_existing_evidence_and_retains_response_bounds():
    fact_id, calculation_id = uuid4(), uuid4()
    schema = cited_hypothesis_schema({'facts': [{'id': fact_id}], 'calculations': [{'id': calculation_id}]})
    definitions = schema.model_json_schema()
    properties = definitions['$defs']['CitedHypothesis']['properties']
    assert properties['fact_ids']['items']['enum'] == [str(fact_id)]
    assert properties['calculation_ids']['items']['enum'] == [str(calculation_id)]
    assert properties['fact_ids']['maxItems'] == 12 and properties['calculation_ids']['maxItems'] == 8
    with pytest.raises(ValidationError):
        schema(candidates=[], missing_evidence=['x' * 201])
    assert schema(candidates=[], missing_evidence=['Independent supporting evidence']).candidates == []
