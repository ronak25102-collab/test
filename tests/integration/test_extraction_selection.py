from datetime import date
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from signal_research.domain.enums import RunMode
from signal_research.domain.schemas import Fact, Passage, SourceDocument
from signal_research.extraction.models import ExtractedFactBatch
from signal_research.research.live import LiveResearch, fact_review_schema
from signal_research.settings import Settings
from signal_research.worker.budgets import Budget


def test_independent_review_cannot_grow_beyond_its_candidate_count_or_reason_limit():
    schema = fact_review_schema(2)
    verdict = {"index": 0, "supported": True, "reason": "Exact row and column match."}
    assert len(schema(verdicts=[verdict, verdict | {"index": 1}]).verdicts) == 2
    for items in ([verdict], [verdict] * 3,
                  [verdict, verdict | {"reason": "x" * 301}],
                  [verdict, verdict | {"index": -1}]):
        with pytest.raises(ValidationError):
            schema(verdicts=items)


def test_comparative_balance_pages_precede_audit_mentions_and_duplicate_rows(store, tmp_path, monkeypatch):
    company = store.search_companies("HDFCBANK")[0]
    run_id = store.create_run(company, date(2026, 10, 10), RunMode.LIVE)
    store.lease_next("selection-test")
    settings = Settings(data_dir=tmp_path, model_rate_card_path=tmp_path / "no-rates.json")
    research = LiveResearch(SimpleNamespace(store=store, settings=settings), run_id, company,
                            date(2026, 10, 10), Budget(1, 1, 1, 1))
    document_id = uuid4()
    research.documents = [SourceDocument(id=document_id, canonical_url="https://hdfc.bank.in/results.pdf",
        final_url="https://hdfc.bank.in/results.pdf", publisher="HDFC Bank", origin_family_id="issuer:test",
        title="Results", document_type="issuer_disclosure", retrieved_at="2026-10-10T00:00:00Z",
        content_hash="test", mime_type="application/pdf", cutoff_eligibility="eligible")]
    balance = Passage(id=uuid4(), document_id=document_id, page_index=2,
        text="Standalone INR crore at 30.06.2026 and 30.06.2025\nDeposits 100 90\nAdvances 80 70", extraction_method="pdf")
    duplicate = balance.model_copy(update={"id": uuid4(), "extraction_method": "pdf_table"})
    audit = Passage(id=uuid4(), document_id=document_id, page_index=12,
        text="Audit review Employee Welfare Trust: advances deposits CASA net interest margin gross NPA capital adequacy ratio net profit total revenue")
    research.passages = [audit, duplicate, balance]
    selected = []
    def model(schema, payload, *args):
        selected.append(payload["passage_id"])
        return ExtractedFactBatch()
    monkeypatch.setattr(research.calls, "model", model)
    research.extract(limit=2)
    assert selected == [balance.id]  # The trust's figures are never issuer totals.


def test_axis_complete_balance_precedes_partial_table_view_with_duplicate_numeric_rows(store, tmp_path, monkeypatch):
    company = store.search_companies("AXISBANK")[0]
    run_id = store.create_run(company, date(2026, 10, 11), RunMode.LIVE)
    store.lease_next("axis-table")
    settings = Settings(data_dir=tmp_path, model_rate_card_path=tmp_path / "none.json")
    research = LiveResearch(SimpleNamespace(store=store, settings=settings), run_id, company,
                            date(2026, 10, 11), Budget(1, 1, 1, 1))
    doc = SourceDocument(id=uuid4(), canonical_url="https://axis.bank.in/results.pdf", final_url="https://axis.bank.in/results.pdf",
        publisher=company.legal_name, origin_family_id=f"issuer:{company.id}", title="Quarterly results",
        document_type="issuer_disclosure", retrieved_at="2026-10-11T00:00:00Z", published_at="2026-07-18T00:00:00Z",
        content_hash="axis", mime_type="application/pdf", cutoff_eligibility="eligible")
    balance = Passage(id=uuid4(), document_id=doc.id, page_index=6, extraction_method="pdf",
        text=(Path(__file__).parents[1] / "fixtures/axis-consolidated-balance.txt").read_text(encoding="utf-8"))
    # Real pdf_table views repeat the page prefix and append an individual row;
    # that extra numeric row must not outrank a complete source page.
    duplicate = balance.model_copy(update={"id": uuid4(), "extraction_method": "pdf_table",
        "text": balance.text[:1600] + "\nDeposits 13,71,173.07 13,33,791.44 11,59,584.25"})
    research.documents, research.passages = [doc], [duplicate, balance]
    reviews = []
    def review(schema, payload, *args):
        assert schema.__name__ == "FactReview"  # Complete columns need no model extraction.
        assert payload["source_text"] == balance.text
        reviews.append(payload)
        return schema(verdicts=[{"index": i, "supported": True, "reason": "Exact columns match"} for i in range(4)])
    monkeypatch.setattr(research.calls, "model", review)
    research.extract()
    assert len(reviews) == 1 and len(research.facts) == 4
    assert all(f.passage_id == balance.id for f in research.facts)
    assert research.calculations


def test_analysis_payload_keeps_cited_spans_and_context_without_entire_report(store, tmp_path):
    company = store.search_companies("HDFCBANK")[0]
    settings = Settings(data_dir=tmp_path, model_rate_card_path=tmp_path / "no-rates.json")
    research = LiveResearch(SimpleNamespace(store=store, settings=settings), uuid4(), company,
                            date(2026, 10, 10), Budget(1, 1, 1, 1))
    issuer = SourceDocument(id=uuid4(), canonical_url="https://hdfc.bank.in/annual.pdf",
        final_url="https://hdfc.bank.in/annual.pdf", publisher="HDFC Bank", origin_family_id="issuer:test",
        title="Annual report", document_type="issuer_disclosure", retrieved_at="2026-10-10T00:00:00Z",
        content_hash="issuer", mime_type="application/pdf", cutoff_eligibility="eligible")
    context = issuer.model_copy(update={"id": uuid4(), "document_type": "public_context", "content_hash": "context"})
    future = context.model_copy(update={"id": uuid4(), "cutoff_eligibility": "ineligible"})
    research.documents = [issuer, context, future]
    cited = Passage(id=uuid4(), document_id=issuer.id, text="Standalone deposits INR 100 crore at 31 March 2026")
    research.passages = [cited] + [Passage(id=uuid4(), document_id=issuer.id, text="Irrelevant annual report page " * 200) for _ in range(100)]
    research.passages += [Passage(id=uuid4(), document_id=context.id, text="Independent deposit growth context") for _ in range(10)]
    research.passages.append(Passage(id=uuid4(), document_id=future.id, text="Future deposits evidence"))
    research.facts = [Fact(id=uuid4(), entity_id=company.id, metric_key="deposits", passage_id=cited.id,
                           value_decimal=100, unit_normalized="INR_crore", period_end="2026-03-31",
                           period_type="instant", scope="standalone", definition_id="deposits_as_reported_v1")]
    payload = research.payload()
    assert len(payload["passages"]) == 3
    assert {p["document_id"] for p in payload["passages"]} == {issuer.id, context.id}
    assert next(p for p in payload["passages"] if p["id"] == cited.id)["text"] == cited.text
    assert len(str(payload)) < 5000


@pytest.mark.parametrize("review_supported", [True, False])
def test_sbi_own_balance_precedes_rrbs_and_requires_independent_review(store, tmp_path, monkeypatch, review_supported):
    company = store.search_companies("SBIN")[0]
    run_id = store.create_run(company, date(2026, 10, 11), RunMode.LIVE)
    store.lease_next("sbi-table")
    settings = Settings(data_dir=tmp_path, model_rate_card_path=tmp_path / "none.json")
    research = LiveResearch(SimpleNamespace(store=store, settings=settings), run_id, company,
                            date(2026, 10, 11), Budget(1, 1, 1, 1))
    doc = SourceDocument(id=uuid4(), canonical_url="https://sbi.bank.in/results.pdf", final_url="https://sbi.bank.in/results.pdf", publisher="State Bank of India",
        origin_family_id=f"issuer:{company.id}", title="Q1FY27 results", document_type="issuer_disclosure",
        retrieved_at="2026-10-11T00:00:00Z", published_at="2026-08-07T00:00:00Z", content_hash="sbi",
        mime_type="application/pdf", cutoff_eligibility="eligible")
    balance = Passage(id=uuid4(), document_id=doc.id, page_index=45, extraction_method="pdf",
        text=(Path(__file__).parents[1] / "fixtures/sbi-comparative-balance.txt").read_text(encoding="utf-8"))
    rrb = Passage(id=uuid4(), document_id=doc.id, page_index=43,
        text="Regional Rural Banks – Sponsored by SBI\nDeposits at INR 148806 crore\nGross Advances at INR 125857 crore\nCASA NIM GNPA net profit")
    duplicate = balance.model_copy(update={"id": uuid4(), "extraction_method": "pdf_table"})
    research.documents, research.passages = [doc], [rrb, balance, duplicate]
    reviews = []
    def model(schema, payload, *args):
        assert schema.__name__ == "FactReview"
        reviews.append(payload)
        return schema(verdicts=[{"index": c["index"], "supported": review_supported, "reason": "Own bank column checked."} for c in payload["candidates"]])
    monkeypatch.setattr(research.calls, "model", model)
    research.extract()
    assert len(reviews) == 1 and "SBI SOLO" in reviews[0]["source_text"]
    assert len(research.facts) == (4 if review_supported else 0)
    assert len(research.calculations) == (2 if review_supported else 0)
    assert all(f.passage_id == balance.id and f.scope.value == "standalone" for f in research.facts)
    if review_supported:
        research.extract()
        assert len(reviews) == 1 and len(research.facts) == 4  # No duplicate paid review.


def test_original_company_context_is_not_crowded_out_by_peer_metric_mentions(store, tmp_path):
    company = store.search_companies("SBIN")[0]
    settings = Settings(data_dir=tmp_path, model_rate_card_path=tmp_path / "none.json")
    research = LiveResearch(SimpleNamespace(store=store, settings=settings), uuid4(), company,
                            date(2026, 10, 11), Budget(1, 1, 1, 1))
    for name, text in (("peer1", "Axis Bank advances deposits CASA net interest margin gross NPA capital adequacy ratio"),
                       ("peer2", "HDFC Bank advances deposits CASA net interest margin gross NPA capital adequacy ratio"),
                       ("target", "SBI retains a stable funding assessment; deposit composition requires monitoring.")):
        document = SourceDocument(id=uuid4(), canonical_url=f"https://independent.example/{name}", final_url=f"https://independent.example/{name}",
            publisher="Independent analyst", origin_family_id=name, title=name, document_type="public_context",
            retrieved_at="2026-10-11T00:00:00Z", content_hash=name, mime_type="text/html", cutoff_eligibility="eligible")
        research.documents.append(document)
        research.passages.extend(Passage(id=uuid4(), document_id=document.id, text=text) for _ in range(2))
    passages = research.payload()["passages"]
    assert len(passages) == 4
    assert all("SBI retains" in p["text"] for p in passages[:2])
