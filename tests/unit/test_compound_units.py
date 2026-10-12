from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from signal_research.domain.enums import Profile
from signal_research.domain.schemas import Passage
from signal_research.extraction.models import ExtractedFactCandidate
from signal_research.extraction.validate import validate_candidate


@pytest.mark.parametrize('scale', ['lakh crore', 'trillion'])
def test_compound_scale_is_not_misread_as_lakh_or_crore(scale):
    passage = Passage(id=uuid4(), document_id=uuid4(), text=f'Standalone gross advances INR 29.5 {scale} at 31 March 2026.')
    candidate = ExtractedFactCandidate(metric_key='gross_advances', value_raw='29.5', unit_raw='INR '+scale, currency='INR',
        period_end=date(2026, 3, 31), scope='standalone', passage_id=passage.id, extraction_confidence='.99')
    result = validate_candidate(candidate, passage, uuid4(), Profile.BANK)
    assert result.fact.value_decimal == Decimal('2950000')
