from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from signal_research.domain.enums import RunMode
from signal_research.domain.schemas import Passage, SourceDocument
from signal_research.providers.llm.nvidia_provider import (
    NvidiaRequestError,
    NvidiaStructuredOutputError,
    NvidiaTimeout,
)
from signal_research.research.live import LiveResearch
from signal_research.worker.budgets import Budget


def research_fixture(store, settings):
    company = store.search_companies('HDFCBANK')[0]
    run_id = store.create_run(company, date(2026, 10, 14), RunMode.LIVE)
    store.lease_next('extraction-failure')
    research = LiveResearch(SimpleNamespace(store=store, settings=settings), run_id, company,
        date(2026, 10, 14), Budget(10, 10, 10, 1))
    document = SourceDocument(id=uuid4(), canonical_url='https://hdfc.bank.in/results.pdf',
        final_url='https://hdfc.bank.in/results.pdf', publisher=company.legal_name,
        origin_family_id=f'issuer:{company.id}', title='Results', document_type='issuer_disclosure',
        retrieved_at='2026-10-14T00:00:00Z', published_at='2026-05-15T00:00:00Z',
        content_hash='results', mime_type='application/pdf')
    research.documents = [document]
    return research, document


@pytest.mark.parametrize('phase', ['extraction', 'review'])
def test_incomplete_response_withholds_entire_page_then_checks_another_source(store, settings, monkeypatch, phase):
    research, document = research_fixture(store, settings)
    table = (research.company.legal_name + '\nStandalone INR crore\n'
             'As at 31 March 2026 | 31 March 2025\nDeposits 1000 900\nBorrowings 200 220')
    first = Passage(id=uuid4(), document_id=document.id, page_index=2,
        text=table if phase == 'review' else research.company.legal_name +
        ' reported standalone deposits INR 1000 crore at 31 March 2026.')
    duplicate = first.model_copy(update={'id': uuid4(), 'extraction_method': 'pdf_table'})
    research.passages = [first, duplicate]
    calls = []
    def fail(schema, *args):
        calls.append(schema.__name__)
        raise NvidiaStructuredOutputError('Output limit reached')
    monkeypatch.setattr(research.calls, 'model', fail)
    research.extract(limit=1)
    assert len(calls) == 1 and not research.facts and not research.calculations
    assert {first.id, duplicate.id} <= research.extracted
    failure = store.artifacts(research.run_id, 'extraction_failure')[0]['payload']
    assert failure['passage_id'] == str(first.id)
    assert failure['action'] == 'source withheld; request not retried'
    next_source = Passage(id=uuid4(), document_id=document.id, page_index=3, text=table)
    research.passages.append(next_source)
    def review(schema, payload, *args):
        calls.append(schema.__name__)
        assert schema.__name__ == 'FactReview'
        return schema(verdicts=[{'index': c['index'], 'supported': True, 'reason': 'Source columns match'}
                                for c in payload['candidates']])
    monkeypatch.setattr(research.calls, 'model', review)
    research.extract()
    assert len(calls) == 2 and len(research.facts) == 4 and research.calculations
    assert all(f.passage_id == next_source.id for f in research.facts)
    snapshot = store.load_checkpoint(research.run_id, 'evidence_collected', iteration=None)
    assert snapshot['outcome'] == 'partial' and not snapshot['discoveries']


@pytest.mark.parametrize('error', [NvidiaRequestError('NVIDIA authentication failed'),
                                  NvidiaRequestError('NVIDIA quota exceeded'),
                                  NvidiaTimeout('Uncertain response timeout')])
def test_access_and_uncertain_transport_errors_stop_provider_work(store, settings, monkeypatch, error):
    research, document = research_fixture(store, settings)
    research.passages = [Passage(id=uuid4(), document_id=document.id,
        text=research.company.legal_name + ' standalone deposits INR 100 at 31 March 2026.')]
    def fail(*args):
        raise error
    monkeypatch.setattr(research.calls, 'model', fail)
    with pytest.raises(type(error)):
        research.extract()
    assert not research.facts and not store.artifacts(research.run_id, 'extraction_failure')
