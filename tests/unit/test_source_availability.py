from datetime import UTC, date, datetime
from uuid import uuid4

from signal_research.domain.schemas import SourceDocument
from signal_research.retrieval.metadata import available_by_cutoff, source_availability


def test_live_receipt_proves_availability_without_fabricating_publication_date():
    receipt = datetime(2026, 10, 11, 19, tzinfo=UTC)  # Already 12 October in India.
    assert source_availability(None, receipt, date(2026, 10, 12)) == ('eligible', 'verified_retrieval')
    assert source_availability(None, receipt, date(2026, 10, 11)) == ('unknown', 'unknown')
    assert source_availability(None, None, date(2026, 10, 12)) == ('unknown', 'unknown')
    assert source_availability(None, receipt.replace(tzinfo=None), date(2026, 10, 12)) == ('unknown', 'unknown')
    later_publication = datetime(2026, 10, 13, tzinfo=UTC)
    assert source_availability(later_publication, receipt, date(2026, 10, 12)) == ('ineligible', 'publication_date')
    doc = SourceDocument(id=uuid4(), canonical_url='https://issuer.example/report.pdf', final_url='https://issuer.example/report.pdf',
        publisher='Example', origin_family_id='issuer', title='Report', document_type='issuer_disclosure',
        retrieved_at=receipt, content_hash='a' * 64, mime_type='application/pdf',
        cutoff_eligibility='eligible', cutoff_eligibility_basis='verified_retrieval')
    assert doc.published_at is None
    assert available_by_cutoff(doc, date(2026, 10, 12))
    assert not available_by_cutoff(doc, date(2026, 10, 11))
    assert not available_by_cutoff(doc.model_copy(update={'content_hash': 'fake'}), date(2026, 10, 12))
    assert not available_by_cutoff(doc.model_copy(update={'access_status': 'failed'}), date(2026, 10, 12))
    assert not available_by_cutoff(doc.model_copy(update={'cutoff_eligibility_basis': 'unknown'}), date(2026, 10, 12))
