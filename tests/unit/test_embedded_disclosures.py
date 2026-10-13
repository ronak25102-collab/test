import pytest
from signal_research.retrieval.disclosures import embedded_disclosures


@pytest.mark.parametrize('raw', [
    b'<button onclick="window.open(\'/reports/annual-report-2026.pdf\')">Annual report</button>',
    b'<a data-url="/reports/financial-results-2026.pdf">Financial results</a>',
    b'<script type="application/json">{"reports":[{"title":"Annual report 2026","url":"/attachments/1234.pdf"}]}</script>',
    b'<script>const files = ["/reports/annual-report-2026.pdf"];</script>',
])
def test_embedded_public_disclosure_links_are_found_without_executing_code(raw):
    hits = embedded_disclosures(raw, 'https://issuer.example/investors', ['issuer.example'])
    assert len(hits) == 1
    assert hits[0].url.startswith('https://issuer.example/')
    assert hits[0].provider == 'issuer_embedded_link'


@pytest.mark.parametrize('url', ['http://127.0.0.1/annual-report.pdf', 'https://issuer.example.evil.test/annual-report.pdf',
                                 'javascript:alert(1)', 'file:///annual-report.pdf', 'https://outside.example/annual-report.pdf'])
def test_embedded_links_cannot_escape_the_verified_issuer_or_fetch_local_files(url):
    raw = f'<script type="application/json">{{"title":"Annual report","url":"{url}"}}</script>'.encode()
    assert not embedded_disclosures(raw, 'https://issuer.example/investors', ['issuer.example'])


def test_unverified_portals_and_nonfinancial_downloads_are_not_followed():
    raw = b'<script>const download = "/employee-handbook.pdf";</script>'
    assert not embedded_disclosures(raw, 'https://issuer.example/', ['issuer.example'])
    raw = b'<script>const download = "/annual-report.pdf";</script>'
    assert not embedded_disclosures(raw, 'https://unverified.example/', ['issuer.example'])
