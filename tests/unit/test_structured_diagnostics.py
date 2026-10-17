import json

import pytest
from pydantic import BaseModel, Field, ValidationError
from signal_research.providers.llm.structured import validate_response


class Verdict(BaseModel):
    supported: bool
    reason: str = Field(max_length=20)
    claim_text: str = Field(max_length=20)
    value: int


def test_only_oversized_diagnostic_reason_is_shortened_without_changing_verdict_or_value():
    raw = {'supported':False, 'reason':'Source cannot establish this claim. ' * 5, 'claim_text':'Financial claim', 'value':123}
    result = validate_response(Verdict, json.dumps(raw))
    assert result.reason == raw['reason'][:20]
    assert result.supported is False and result.value == 123
    assert result.claim_text == raw['claim_text']


def test_diagnostic_normalization_never_repairs_claim_text_or_invalid_financial_values():
    for claim, value in [('Unreviewed long claim. ' * 10, 123), ('Financial claim', 'invented value')]:
        with pytest.raises(ValidationError):
            validate_response(Verdict, json.dumps({'supported':True, 'reason':'A long reason. ' * 10,
                                                   'claim_text':claim, 'value':value}))
