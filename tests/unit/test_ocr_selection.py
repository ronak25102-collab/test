from uuid import uuid4

from signal_research.domain.schemas import Passage
from signal_research.retrieval.passages import ParsedDocument, prioritized_ocr_pages


def test_ocr_budget_prioritizes_cover_and_scans_near_financial_pages():
    page = Passage(id=uuid4(), document_id=uuid4(), page_index=100,
                   text="Consolidated balance sheet, assets and liabilities")
    parsed = ParsedDocument("Annual report", [page], "pdf", [3, 4, 0, 99, 101])
    assert prioritized_ocr_pages(parsed)[:3] == [0, 99, 101]
    assert set(prioritized_ocr_pages(parsed)) == set(parsed.blank_page_indexes)
