from datetime import date
from uuid import uuid4

from bs4 import BeautifulSoup
from signal_research.exports.html_report import public_url, report_html
from signal_research.research.report_builder import build_synthetic_report


def test_export_embeds_evidence_without_network_assets_or_local_links(store):
    report = build_synthetic_report(uuid4(), store.search_companies('SYNTHBANK')[0], date(2026, 10, 15))
    report.passages[0].text += '\n<script>bad()</script>'
    html = report_html(report)
    soup = BeautifulSoup(html, 'html.parser')
    assert not soup.select('script[src], link[href], img[src]')
    assert soup.select('dialog blockquote') and soup.select('#report-data')
    assert '&lt;script&gt;bad()&lt;/script&gt;' in html
    assert not any('localhost' in a.get('href', '') or '127.0.0.1' in a.get('href', '') for a in soup.select('a'))
    assert public_url('http://127.0.0.1:5173/') is None
    assert public_url('http://localhost/') is None
    assert public_url('http://localhost./') is None
    assert public_url('javascript:alert(1)') is None
    assert soup.select('svg text[text-anchor="end"]')


def test_export_keeps_peer_lineage_and_prints_significance_and_checked_passages(store):
    report = build_synthetic_report(uuid4(), store.search_companies('SYNTHBANK')[0], date(2026, 10, 15))
    bundle = {name: [x.model_dump(mode='json') for x in getattr(report, name)] for name in ('facts', 'passages', 'documents')}
    bundle['company'] = report.company.model_dump(mode='json')
    bundle['company']['legal_name'] = 'Synthetic Peer'
    report.generation_metadata['peer_benchmark'] = {'status': 'inconclusive', 'comparisons': [], 'sources': [bundle]}
    html = report_html(report)
    soup = BeautifulSoup(html, 'html.parser')
    assert soup.select('#peer-evidence blockquote')
    assert 'Synthetic Peer' in soup.select_one('#peer-evidence').text
    assert str(report.facts[0].id) in soup.select_one('#peer-evidence').text
    assert 'button[data-open]{display:inline' in html
    assert "querySelectorAll('main details:not([open])')" in html
