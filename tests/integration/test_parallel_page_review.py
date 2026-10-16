from datetime import UTC, date, datetime
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

from signal_research.domain.enums import RunMode
from signal_research.domain.schemas import Passage, SourceDocument
from signal_research.providers.llm.openai_provider import OpenAIProvider
from signal_research.research.live import LiveResearch
from signal_research.settings import Settings
from signal_research.worker.budgets import Budget
from signal_research.worker.machine import ResearchMachine


def test_parallel_review_keeps_source_checks_and_withholds_conflicting_values(store, tmp_path, monkeypatch):
    company = store.search_companies('HDFCBANK')[0]
    rid = store.create_run(company, date(2026, 10, 8), RunMode.LIVE)
    store.lease_next('parallel-page-review')
    settings = Settings(data_dir=tmp_path, llm_provider='openai', openai_api_key='test-only',
                        openai_model_research='test', openai_model_extract='test',
                        allow_unknown_cost=True, max_research_agents=2)
    budget = Budget(max_search_calls=10, max_fetch_documents=10, max_model_calls=10,
                    max_ocr_pages=1, max_input_tokens=200000, max_output_tokens=100000)
    research = LiveResearch(ResearchMachine(store, settings), rid, company, date(2026, 10, 8), budget)
    doc_id = uuid4()
    research.documents = [SourceDocument(id=doc_id, canonical_url='https://hdfc.bank.in/results.pdf',
        final_url='https://hdfc.bank.in/results.pdf', publisher=company.legal_name,
        origin_family_id=f'issuer:{company.id}', title='Financial results', document_type='issuer_disclosure',
        published_at=datetime(2026, 5, 15, tzinfo=UTC), retrieved_at=datetime(2026, 10, 8, tzinfo=UTC),
        content_hash='a' * 64, mime_type='application/pdf')]
    research.passages = [Passage(id=uuid4(), document_id=doc_id, page_index=i,
        text=(f'{company.legal_name}\nStandalone balance sheet\nINR in crore\n'
              f'As at 31 March 2026 | 31 March 2025\nDeposits {value} 90\nBorrowings 30 25\nGross advances 80 70'))
        for i, value in enumerate([100, 110])]
    barrier = Barrier(2)
    def generate(self, schema, messages, *args):
        import json
        payload = json.loads(messages[1]['content'])
        assert schema.__name__ == 'FactReview'
        barrier.wait(timeout=3)  # Serial reviews fail, independent agents meet.
        return schema(verdicts=[dict(index=c['index'], supported=True, reason='Checked exact source column')
                                for c in payload['candidates']]), SimpleNamespace(input_tokens=100, output_tokens=100)
    monkeypatch.setattr(OpenAIProvider, 'generate', generate)
    research.extract()
    assert research.facts
    assert not any(f.metric_key == 'deposits' and f.period_end == date(2026, 3, 31) for f in research.facts)
    assert any('Conflicting disclosures withheld' in note for note in research.limitations)
    assert len(store.artifacts(rid, 'research_agent')) == 4
    checkpoint = store.load_checkpoint(rid, 'evidence_collected', iteration=None)
    assert checkpoint and checkpoint['facts'] and not checkpoint['discoveries']
    assert all('110' != f['value_raw'] for f in checkpoint['facts'])
