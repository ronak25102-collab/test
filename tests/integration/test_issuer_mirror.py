import hashlib
import io
from datetime import date

from reportlab.pdfgen import canvas
from signal_research.domain.enums import RunMode
from signal_research.providers.search.base import SearchHit
from signal_research.research.live import LiveResearch
from signal_research.retrieval.fetch import FetchResult, PublicFetcher
from signal_research.worker.budgets import Budget
from signal_research.worker.machine import ResearchMachine


def test_original_filing_on_third_party_domain_keeps_the_issuer_origin(store, settings, tmp_path, monkeypatch):
    company = store.search_companies('HDFCBANK')[0]
    rid = store.create_run(company, date(2026, 10, 16), RunMode.LIVE)
    store.lease_next('mirror-check')
    out = io.BytesIO()
    pdf = canvas.Canvas(out)
    block = pdf.beginText(40, 780)
    for line in [company.legal_name, 'Integrated Annual Report 2025-26', 'Standalone Statement of Assets and Liabilities',
                 'INR crore', 'As at 31 March 2026 | 31 March 2025', 'Deposits 120 100', 'Borrowings 30 40', 'Date: 15 May 2026']:
        block.textLine(line)
    pdf.drawText(block)
    pdf.save()
    raw = out.getvalue()
    path = tmp_path / 'mirror.pdf'
    path.write_bytes(raw)
    def fetch(self, url):
        return FetchResult(url, url, 200, 'application/pdf', hashlib.sha256(raw).hexdigest(), str(path))
    monkeypatch.setattr(PublicFetcher, 'fetch', fetch)
    research = LiveResearch(ResearchMachine(store, settings), rid, company, date(2026, 10, 16), Budget(5, 5, 5, 0))
    research.ingest([SearchHit('https://other-issuer.example/report.pdf', 'Annual Report 2025-26', '', 1, 'test')])
    assert research.documents[0].document_type == 'issuer_mirror'
    assert research.documents[0].origin_family_id == f'issuer:{company.id}'
