"""Controlled generated PDF; this is not live issuer evidence."""
from uuid import uuid4

from reportlab.pdfgen import canvas
from signal_research.retrieval.passages import parse_pdf


def test_large_pdf_retains_page_index_and_complete_financial_table(tmp_path):
    path = tmp_path / 'annual.pdf'
    writer = canvas.Canvas(str(path))
    for index in range(81):
        lines = ['Quartz Financial Bank public annual report section ' + str(index)]
        if index == 17:
            lines += ['Standalone balance sheet', '(INR in crore)',
                      'As at March 31, 2026 March 31, 2025',
                      'Deposits 1,000 900', 'Borrowings 200 220', 'Advances 800 700']
        for offset, line in enumerate(lines):
            writer.drawString(40, 780 - 20 * offset, line)
        writer.showPage()
    writer.save()
    parsed = parse_pdf(uuid4(), path)
    table = next(p for p in parsed.passages if 'Deposits 1,000 900' in p.text)
    assert table.page_index == 17
    assert 'Standalone balance sheet' in table.text
    assert '(INR in crore)' in table.text
    assert 'March 31, 2026 March 31, 2025' in table.text
    assert 'Borrowings 200 220' in table.text
    assert 'Advances 800 700' in table.text
