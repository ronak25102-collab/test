from uuid import uuid4

import pytest
from pydantic import ValidationError
from signal_research.research.live import (
    Challenge,
    Statement,
    cited_draft_schema,
    semantic_review_schema,
)


def test_challenger_cannot_generate_an_unbounded_repeated_citation_array():
    payload = dict(refuted=False, unresolved=True, strongest_alternative='Seasonality', reason='Compare periods',
                   relevant_passage_ids=[uuid4()] * 9)
    with pytest.raises(ValidationError):
        Challenge(**payload)
    assert Challenge(**(payload | {'relevant_passage_ids': []})).unresolved


def test_dynamic_draft_preserves_statement_citation_bounds():
    schema = cited_draft_schema({'facts': [], 'passages': [], 'calculations': []})
    defs = schema.model_json_schema()['$defs']['CitedStatement']['properties']
    assert defs['fact_ids']['maxItems'] == 8
    assert defs['passage_ids']['maxItems'] == 6
    assert defs['calculation_ids']['maxItems'] == 6
    with pytest.raises(ValidationError):
        Statement(text='x' * 601, kind='derived', fact_ids=[], passage_ids=[], calculation_ids=[])


def test_final_review_requires_exactly_the_claim_count_and_known_identifiers():
    identifiers = [uuid4(), uuid4()]
    schema = semantic_review_schema(identifiers)
    props = schema.model_json_schema()['properties']['verdicts']
    assert props['minItems'] == props['maxItems'] == 2
    payload = {'verdicts': [{'claim_id': identifiers[0], 'supported': True, 'reason': 'Source matches'}],
               'falsification_is_observable': True, 'contains_investment_recommendation': False,
               'non_obvious_synthesis_supported': True}
    with pytest.raises(ValidationError):
        schema(**payload)
