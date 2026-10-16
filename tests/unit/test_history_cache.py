import hashlib
from datetime import date
from uuid import uuid4

from signal_research.domain.schemas import Fact, Passage, SourceDocument
from signal_research.research.history_cache import historical_observations
from signal_research.research.report_builder import build_abstention


def test_cache_rechecks_original_bytes_and_excludes_recent_unverified_or_synthetic_facts(store, tmp_path):
    company = store.search_companies('HDFCBANK')[0]
    raw = tmp_path / 'source.txt'
    raw.write_bytes(b'Original dated issuer disclosure')
    doc = SourceDocument(id=uuid4(), canonical_url='https://issuer.example/results',
                         final_url='https://issuer.example/results',
                         publisher=company.legal_name, origin_family_id=f'issuer:{company.id}',
                         title='Annual results', document_type='issuer_disclosure',
                         published_at='2026-05-01T00:00:00Z', retrieved_at='2026-10-15T00:00:00Z',
                         content_hash=hashlib.sha256(raw.read_bytes()).hexdigest(), mime_type='text/html',
                         local_object_key=str(raw))
    passage = Passage(id=uuid4(), document_id=doc.id, text='Original source passage')
    def fact(end, status='verified'):
        return Fact(id=uuid4(), entity_id=company.id, metric_key='deposits', value_decimal=100,
                    unit_normalized='INR_crore', currency='INR', period_end=end, scope='standalone',
                    period_type='instant',
                    definition_id='deposits_as_reported_v1', passage_id=passage.id, status=status)
    old, recent, unverified = fact('2025-03-31'), fact('2026-03-31'), fact('2024-03-31', 'candidate')
    report = build_abstention(uuid4(), company, date(2026, 10, 15), [doc], [passage],
                              [old, recent, unverified], mode='live')
    facts, passages, documents = historical_observations(report, company.id, report.cutoff)
    assert [f.id for f in facts] == [old.id]
    assert passages == [passage] and documents == [doc]
    assert not historical_observations(report, uuid4(), report.cutoff)[0]
    report.source_coverage['synthetic'] = True
    assert not historical_observations(report, company.id, report.cutoff)[0]
    report.source_coverage['synthetic'] = False
    raw.write_bytes(b'Changed source bytes')
    assert not historical_observations(report, company.id, report.cutoff)[0]
