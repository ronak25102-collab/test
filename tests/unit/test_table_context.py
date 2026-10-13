from types import SimpleNamespace
from uuid import uuid4

from signal_research.domain.enums import Profile
from signal_research.extraction.financial_tables import financial_table_batch
from signal_research.extraction.validate import validate_candidate
from signal_research.retrieval.passages import parse_html


def test_each_table_keeps_its_own_preceding_scope_and_complete_period_headers():
    company = SimpleNamespace(id=uuid4(), legal_name='Quartz Life Limited')
    raw = b'''<html><h1>Quartz Life Limited</h1><h2>Standalone</h2><p>INR crore</p>
    <table><tr><th>Metric</th><th>Year ended 31 March 2026</th><th>31 March 2025</th></tr>
    <tr><td>Annual premium equivalent</td><td>120</td><td>100</td></tr>
    <tr><td>Value of new business</td><td>30</td><td>20</td></tr></table>
    <h2>Consolidated</h2><p>INR crore</p>
    <table><tr><th>Metric</th><th>Year ended 31 March 2026</th><th>31 March 2025</th></tr>
    <tr><td>Annual premium equivalent</td><td>150</td><td>130</td></tr>
    <tr><td>Value of new business</td><td>35</td><td>25</td></tr></table>
    <p>Unrelated footer claims standalone INR million.</p></html>'''
    parsed = parse_html(uuid4(), raw)
    whole = [p for p in parsed.passages if p.table_id and p.row_label is None]
    assert len(whole) == 2
    for passage, scope in zip(whole, ['standalone', 'consolidated'], strict=True):
        assert 'Unrelated footer' not in passage.text
        batch = financial_table_batch(passage, company, Profile.LIFE_INSURER, document_issuer_verified=True)
        assert batch and len(batch.facts) == 4
        assert all(f.scope.value == scope for f in batch.facts)
        for candidate in batch.facts:
            result = validate_candidate(candidate, passage, company.id, Profile.LIFE_INSURER)
            assert result.fact, result.reason
