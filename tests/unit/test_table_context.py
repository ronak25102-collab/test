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


def test_html_colspans_bind_quarter_and_year_windows_without_mixing_them():
    from signal_research.research.live import derive_calculations

    company = SimpleNamespace(id=uuid4(), legal_name='Quartz Financial Limited')
    raw = b'''<h2>Standalone</h2><p>INR crore</p><table>
    <tr><th rowspan="2">Metric</th><th colspan="2">Quarter ended</th><th colspan="2">Year ended</th></tr>
    <tr><th>30 June 2026</th><th>30 June 2025</th><th>31 March 2026</th><th>31 March 2025</th></tr>
    <tr><td>Total revenue</td><td>120</td><td>100</td><td>450</td><td>400</td></tr>
    <tr><td>Net profit</td><td>30</td><td>20</td><td>90</td><td>80</td></tr></table>'''
    parsed = parse_html(uuid4(), raw)
    passage = next(p for p in parsed.passages if p.table_id and p.row_label is None)
    batch = financial_table_batch(passage, company, Profile.NBFC, document_issuer_verified=True)
    assert batch and len(batch.facts) == 4
    facts = []
    for candidate in batch.facts:
        result = validate_candidate(candidate, passage, company.id, Profile.NBFC)
        assert result.fact, result.reason
        assert candidate.period_start.month == 4 and candidate.period_end.month == 6
        facts.append(result.fact)
    assert any(c.formula_id == 'growth_gap' for c in derive_calculations(facts))
    assert {c.output_value for c in derive_calculations(facts) if c.formula_id == 'profit_margin'} == {25, 20}


def test_ambiguous_html_header_spans_are_not_guessed():
    raw = b'''<table><tr><th>Metric</th><th colspan="99999">Quarter ended</th></tr>
    <tr><td></td><td>30 June 2026</td><td>30 June 2025</td></tr>
    <tr><td>Total revenue</td><td>120</td><td>100</td></tr></table>'''
    parsed = parse_html(uuid4(), raw)
    assert not any((p.column_label or '').startswith('Period columns: ') for p in parsed.passages)
