from types import SimpleNamespace
from uuid import uuid4

import pytest
from signal_research.domain.enums import Profile
from signal_research.domain.schemas import Passage
from signal_research.extraction.financial_tables import financial_table_batch
from signal_research.extraction.validate import validate_candidate


@pytest.mark.parametrize('profile,rows,duration', [
    (Profile.NBFC, 'Assets under management | 120 | 100\nTotal borrowings | 80 | 75', ''),
    (Profile.LIFE_INSURER, 'Annual premium equivalent | 120 | 100\nValue of new business | 30 | 20', 'Year ended '),
    (Profile.GENERAL_INSURER, 'Combined ratio (%) | 95 | 100\nClaims ratio (%) | 65 | 70', 'Year ended '),
    (Profile.EXCHANGE, 'Transaction fees | 120 | 100\nTotal revenue | 200 | 180', 'Year ended '),
    (Profile.ASSET_MANAGER, 'Average AUM | 1000 | 900\nManagement fees | 30 | 25', 'Year ended '),
])
def test_explicit_tables_bind_each_business_type(profile, rows, duration):
    company = SimpleNamespace(id=uuid4(), legal_name='Quartz Financial Limited')
    passage = Passage(id=uuid4(), document_id=uuid4(), text=(
        'Quartz Financial Limited\nConsolidated results\nINR crore\n' + duration +
        '31 March 2026 | 31 March 2025\n' + rows))
    batch = financial_table_batch(passage, company, profile)
    assert batch and len(batch.facts) == 4
    for candidate in batch.facts:
        result = validate_candidate(candidate, passage, company.id, profile)
        assert result.fact, result.reason


def test_unnamed_segment_columns_are_candidates_but_cannot_pass_binding_gates():
    company=SimpleNamespace(id=uuid4(),legal_name='Quartz Financial Limited')
    passage=Passage(id=uuid4(),document_id=uuid4(),text=(
        'Quartz Financial Limited\nConsolidated results\nINR crore\nYear ended '
        '31 March 2026 | 31 March 2025\nSegment profit | 120 | 100\nSegment revenue | 200 | 180'))
    batch=financial_table_batch(passage,company,Profile.DIVERSIFIED)
    assert batch and len(batch.facts)==4
    for candidate in batch.facts:
        result=validate_candidate(candidate,passage,company.id,Profile.DIVERSIFIED)
        assert result.fact is None and result.reason=='segment components require a named reporting segment'


@pytest.mark.parametrize('replacement', [
    ('Consolidated', 'Scope 1 and Scope 2'),
    ('Consolidated', 'Standalone Consolidated'),
    ('31 March 2026 | 31 March 2025', 'FY26 | FY25'),
    ('120 | 100', '120 | 100 | 20%'),
    ('120 | 100', '120,09 | 100'),
    ('INR crore', 'Amounts'),
])
def test_ambiguous_columns_scope_units_and_damaged_cells_are_withheld(replacement):
    company = SimpleNamespace(legal_name='Quartz Finance')
    text = 'Quartz Finance\nConsolidated\nINR crore\n31 March 2026 | 31 March 2025\nAssets under management | 120 | 100'
    passage = Passage(id=uuid4(), document_id=uuid4(), text=text.replace(*replacement))
    assert financial_table_batch(passage, company, Profile.NBFC) is None


def test_percentage_row_requires_its_own_explicit_ratio_unit():
    company = SimpleNamespace(legal_name='Quartz Finance')
    passage = Passage(id=uuid4(), document_id=uuid4(), text=(
        'Quartz Finance\nStandalone\nINR crore\n31 March 2026 | 31 March 2025\nGross NPA | 120 | 100'))
    assert financial_table_batch(passage, company, Profile.NBFC) is None


def test_model_review_rejection_cannot_promote_deterministic_candidates(store, settings, monkeypatch):
    from datetime import date

    from signal_research.domain.enums import RunMode
    from signal_research.domain.schemas import SourceDocument
    from signal_research.research.live import LiveResearch
    from signal_research.worker.budgets import Budget

    company = store.search_companies('BAJFINANCE')[0]
    run_id = store.create_run(company, date(2026, 10, 13), RunMode.LIVE)
    store.lease_next('table-review')
    research = LiveResearch(SimpleNamespace(store=store, settings=settings), run_id, company,
                            date(2026, 10, 13), Budget(10, 10, 10, 1))
    document = SourceDocument(id=uuid4(), canonical_url='https://issuer.example/results', final_url='https://issuer.example/results',
        publisher=company.legal_name, origin_family_id='issuer', title='Results', document_type='issuer_disclosure',
        retrieved_at='2026-10-13T00:00:00Z', published_at='2026-05-15T00:00:00Z', content_hash='table', mime_type='text/html')
    research.documents = [document]
    research.passages = [Passage(id=uuid4(), document_id=document.id, text=(
        company.legal_name + '\nStandalone\nINR crore\n31 March 2026 | 31 March 2025\nAssets under management | 120 | 100'))]
    calls = []
    def reject(schema, payload, *args):
        calls.append(schema.__name__)
        return schema(verdicts=[{'index': c['index'], 'supported': False, 'reason': 'Wrong column binding'} for c in payload['candidates']])
    monkeypatch.setattr(research.calls, 'model', reject)
    research.extract()
    assert calls == ['FactReview']
    assert not research.facts and not research.calculations
