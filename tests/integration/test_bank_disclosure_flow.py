"""Every supported bank uses the same verified-domain, link and date pipeline."""
import hashlib
import io
from datetime import date
from types import SimpleNamespace

import pytest
from reportlab.pdfgen import canvas
from signal_research.domain.enums import RunMode
from signal_research.providers.search.base import SearchHit
from signal_research.research.live import LiveResearch
from signal_research.retrieval.disclosures import (
    BANK_DISCLOSURE_INDEXES,
    verified_disclosure_indexes,
)
from signal_research.retrieval.fetch import FetchResult, PublicFetcher
from signal_research.retrieval.metadata import source_origin
from signal_research.settings import Settings
from signal_research.worker.budgets import Budget

BANKS = [
    ("AXISBANK", "axis.bank.in", "axisbank.com"),
    ("HDFCBANK", "hdfc.bank.in", "hdfcbank.com"),
    ("ICICIBANK", "icici.bank.in", "icicibank.com"),
    ("KOTAKBANK", "kotak.bank.in", "kotak.com"),
    ("SBIN", "sbi.bank.in", "sbi.co.in"),
]


@pytest.mark.parametrize("symbol,domain,legacy", BANKS)
@pytest.mark.parametrize("cutoff,eligible", [(date(2026, 7, 18), True), (date(2026, 7, 17), False)])
@pytest.mark.parametrize("empty_search", [False, True])
def test_bank_redirect_and_icon_link_reaches_dated_original_with_reviewed_comparable_facts(
    store, tmp_path, monkeypatch, symbol, domain, legacy, cutoff, eligible, empty_search,
):
    company = store.search_companies(symbol)[0]
    run_id = store.create_run(company, cutoff, RunMode.LIVE)
    store.lease_next("bank-regression")
    settings = Settings(data_dir=tmp_path, model_rate_card_path=tmp_path / "no-rates.json")
    research = LiveResearch(SimpleNamespace(store=store, settings=settings, _cancelled=lambda _: False),
                            run_id, company, cutoff, Budget(2, 3, 3, 1))
    index = BANK_DISCLOSURE_INDEXES[symbol] if empty_search else f"https://{legacy}/results"
    final = f"https://{domain}/results"
    pdf_url = f"https://{domain}/financial-results-june-2026.pdf"
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    text = pdf.beginText(40, 780)
    for line in [company.legal_name, "Consolidated Statement of Assets and Liabilities", "INR in crore",
                 "As on 30.06.2026 As on 31.03.2026 As on 30.06.2025", "Deposits 120 110 100",
                 "Borrowings 30 25 20", "Place: Mumbai", "Date: 18th July, 2026"]:
        text.textLine(line)
    pdf.drawText(text)
    pdf.save()
    fetched = []

    def fetch(self, url):
        fetched.append(url)
        if url == index:
            raw = b'<html><a href="/financial-results-june-2026.pdf"><img src="download.svg"></a></html>'
            mime, target, suffix = "text/html", final, ".html"
        else:
            assert url == pdf_url
            raw = buffer.getvalue()
            mime, target, suffix = "application/pdf", url, ".pdf"
        digest = hashlib.sha256(raw).hexdigest()
        path = tmp_path / (digest + suffix)
        path.write_bytes(raw)
        return FetchResult(url, target, 200, mime, digest, str(path))

    reviews = []

    def review(schema, payload, *args, **kwargs):
        if schema.__name__ == "HypothesisBatch":
            return schema(candidates=[], missing_evidence=["Independent corroboration still needed"])
        assert schema.__name__ == "FactReview"  # Explicit tables still require independent review.
        reviews.append(payload)
        assert [c["value_raw"] for c in payload["candidates"]] == ["120", "100", "30", "20"]
        return schema(verdicts=[{"index": i, "supported": True, "reason": "Exact issuer, scope and date columns matched."}
                                for i in range(4)])

    monkeypatch.setattr(PublicFetcher, "fetch", fetch)
    monkeypatch.setattr(research.calls, "model", review)
    if empty_search:
        monkeypatch.setattr(research.calls, "search", lambda *a, **k: [])
        monkeypatch.setattr(research, "stage", lambda *a: None)
        result = research.run([])
        assert not result.discoveries  # Verified numbers cannot fabricate a finding.
        assert len(result.facts) == (4 if eligible else 0)
    else:
        research.ingest([SearchHit(index, "Financial results", "Not evidence", 1, "test")])
    assert fetched == [index, pdf_url]
    document = next(d for d in research.documents if d.mime_type == "application/pdf")
    assert document.document_type == "issuer_disclosure"
    assert document.origin_family_id == f"issuer:{company.id}"
    assert document.published_at.date() == date(2026, 7, 18)
    assert document.cutoff_eligibility == ("eligible" if eligible else "ineligible")
    research.extract()
    assert len(research.facts) == (4 if eligible else 0)
    assert len(reviews) == int(eligible)
    assert bool(research.calculations) == eligible
    assert research.budget.ocr_pages == 0


def test_every_supported_live_bank_has_verified_disclosure_entry_points(store):
    for company in store.search_companies(""):
        if "bank" not in company.business_profiles or company.symbols == ["SYNTHBANK"]:
            continue
        hits = verified_disclosure_indexes(company)
        assert hits, f"New supported bank {company.legal_name} needs a verified disclosure index"
        assert all(hit.published_at is None for hit in hits)
        assert not verified_disclosure_indexes(company.model_copy(update={"verified_ir_domains": []}))


@pytest.mark.parametrize("symbol,domain,legacy", BANKS)
def test_bank_domain_aliases_never_authorize_a_peer_or_lookalike(store, symbol, domain, legacy):
    company = store.search_companies(symbol)[0]
    for host in (domain, legacy, "www." + domain):
        assert source_origin(f"https://{host}/results.pdf", company, "Results", company.legal_name)[2] == "issuer_disclosure"
    for host in (domain + ".evil.example", "unverified.bank.in", "another-bank.example"):
        assert source_origin(f"https://{host}/results.pdf", company, "Results", company.legal_name)[2] == "public_context"
