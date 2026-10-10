from datetime import date

import pytest
from signal_research.retrieval.disclosures import linked_disclosures
from signal_research.retrieval.metadata import source_publication


def test_disclosure_links_exclude_navigation_foreign_hosts_and_unrelated_pdfs():
    raw = b'''<html><nav><a href="/nav.pdf">Annual Report FY29</a></nav>
    <a href="/forms.pdf">Account application form</a>
    <a href="https://sbi.bank.in.evil.example/results.pdf">Financial Results FY28</a>
    <a href="http://user:password@sbi.bank.in/results.pdf">Financial Results FY28</a>
    <a href="/older.pdf">Analyst Presentation Q4FY26</a>
    <a href="/latest.pdf/id?t=123#page=2">Analyst Presentation Q1FY27</a>
    <a href="/latest.pdf/id?t=123#page=3">Analyst Presentation Q1FY27</a></html>'''
    hits = linked_disclosures(raw, "https://sbi.bank.in/investors", ["sbi.bank.in"], limit=1)
    assert len(hits) == 1
    assert hits[0].url == "https://sbi.bank.in/latest.pdf/id?t=123"
    assert hits[0].published_at is None
    assert linked_disclosures(raw, "https://independent.example", ["sbi.bank.in"]) == []


@pytest.mark.parametrize("cover,expected", [
    ("Quarterly Results\nQ1FY27\nA N A L Y S T P R E S E N T A T I O N\n0 7 . 0 8 . 2 0 2 6", date(2026, 8, 7)),
    ("Annual Results FY26\nA N A L Y S T P R E S E N T A T I O N | 0 8 . 0 5 . 2 0 2 6", date(2026, 5, 8)),
    ("Analyst Presentation\nBalances as at 31.03.2026", None),
    ("Analyst Presentation Q1FY27\n07.08.2026", None),
    ("Analyst Presentation\n31.02.2026", None),
])
def test_pdf_cover_event_dates_do_not_infer_reporting_dates(cover, expected):
    published = source_publication(b"%PDF test", cover)
    assert (published.date() if published else None) == expected


def test_presentation_date_detection_is_limited_to_pdf_cover():
    text = "Analyst Presentation\n07.08.2026"
    assert source_publication(b"<html></html>", text) is None
    assert source_publication(b"%PDF test", "x" * 1200 + text) is None


def test_cited_regulation_date_does_not_date_the_disclosure():
    assert source_publication(b"%PDF test", "RBI circular dated 19 July 2025. Balances at 30 June 2026.") is None


def test_exchange_filing_cover_dates_the_annual_report():
    text = "Ref. No. SE/2026-27/65\nJuly 10, 2026\nBSE Limited\nNational Stock Exchange of India\nEnclosed annual report FY2025-26."
    assert source_publication(b"%PDF test", text).date() == date(2026, 7, 10)
    assert source_publication(b"%PDF test", "Annual report\nBalances at July 10, 2026") is None


def test_icon_only_results_links_are_found_and_prefer_short_results():
    raw = b'''<a href="/annual-report-2026.pdf">Annual Report 2026</a>
    <a href="/2026/unaudited-financial-results-for-the-quarter-ended-30th-june-2026.pdf"><img src="download.svg"></a>
    <a href="/investor-presentation-2026.pdf" aria-label="Investor presentation 2026"></a>
    <a href="/application-form-2027.pdf"><img src="download.svg"></a>'''
    hits = linked_disclosures(raw, "https://axis.bank.in/results", ["axis.bank.in"], limit=3)
    assert len(hits) == 3
    assert "unaudited-financial-results" in hits[0].url
    assert all(hit.published_at is None for hit in hits)
    assert "application" not in " ".join(hit.url for hit in hits)


@pytest.mark.parametrize("date_label,expected", [
    ("18th July, 2026", date(2026, 7, 18)),
    ("1st August 2026", date(2026, 8, 1)),
    ("22nd May, 2026", date(2026, 5, 22)),
    ("23rd April 2026", date(2026, 4, 23)),
    ("18-07-2026", date(2026, 7, 18)),
])
def test_formal_bank_document_dates_accept_ordinal_days(date_label, expected):
    text = f"Financial results for the quarter ended 30th June, 2026\nPlace: Mumbai\nDate: {date_label} www.bank.example"
    assert source_publication(b"%PDF test", text).date() == expected
    assert source_publication(b"%PDF test", f"Balances as on {date_label}") is None
    assert source_publication(b"%PDF test", f"RBI circular dated {date_label}") is None


def test_axis_exchange_filing_reference_dates_its_own_cover():
    text = "AXIS/CO/CS/380/2025-26\nOctober 31, 2025\nNational Stock Exchange of India Limited\nBSE Limited\nChange in domain name of the Bank website"
    assert source_publication(b"%PDF test", text).date() == date(2025, 10, 31)


def test_kotak_press_tables_are_disclosure_leads_without_accepting_other_financial_folder_files():
    raw = b'''<a href="/Financial-Result/QuarterlyReport/FY-2027/q1/Press-Table/Q1FY27-Press-Table.pdf"></a>
    <a href="/Financial-Result/QuarterlyReport/FY-2027/q1/PressRelease/Q1-FY27_Press-Release.pdf"></a>
    <a href="/Financial-Result/QuarterlyReport/FY-2027/q1/account-application.pdf"></a>'''
    hits = linked_disclosures(raw, "https://kotak.bank.in/results", ["kotak.bank.in"])
    assert len(hits) == 2
    assert all(hit.published_at is None for hit in hits)


def test_issuer_portal_subsidiary_prefix_does_not_fill_issuer_lead_budget():
    raw = b'''<a href="/life-investor-presentation-2027.pdf">ICICI Prudential Life: Investor Presentation 2027</a>
    <a href="/general-investor-presentation-2027.pdf">ICICI Lombard General: Investor Presentation 2027</a>
    <a href="/financial-results-2026.pdf">ICICI Bank: Financial Results June 2026</a>'''
    hits = linked_disclosures(raw, "https://icici.bank.in/results", ["icici.bank.in"], limit=1, issuer_name="ICICI Bank")
    assert len(hits) == 1 and hits[0].url.endswith("/financial-results-2026.pdf")


@pytest.mark.parametrize("signature", [
    "For Kotak Mahindra Bank Limited\nAshok Vaswani\nMumbai, 18th July, 2026 Managing Director and Chief Executive Officer",
    "For and on behalf of the Board of Directors\nSandeep Batra\nMumbai Executive Director\nJuly, 18 2026 DIN-03620913",
    "For and on behalf of the Board of Directors\nSandeep Batra\nMumbai Executive Director\nJuly 18, 2026 DIN-03620913",
])
def test_signed_financial_results_datelines_date_the_document(signature):
    text = "Standalone Financial Results\nBalances at June 30, 2026\n" + signature
    assert source_publication(b"%PDF test", text).date() == date(2026, 7, 18)


@pytest.mark.parametrize("text", [
    "Financial Results\nMumbai, 18th July, 2026\nBalances as at June 30, 2026",
    "Financial Results\nApproved by Board of Directors at its meeting held on July 18, 2026.",
    "Financial Results\nRBI circular dated July 18, 2026\nExecutive Director",
    "Chairman's Letter\nFor Kotak Mahindra Bank Limited\nMumbai, 18th July, 2026 Managing Director",
])
def test_unlabelled_dates_and_approval_references_do_not_date_a_source(text):
    assert source_publication(b"%PDF test", text) is None
