from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid5

from signal_research.domain.enums import FactStatus, PeriodType, Scope
from signal_research.domain.schemas import Company, Fact, Passage, SourceDocument


def _id(run_id: UUID, name: str) -> UUID:
    return uuid5(run_id, name)


def synthetic_evidence(run_id: UUID, company: Company, cutoff: date) -> tuple[list[SourceDocument], list[Passage], list[Fact]]:
    issuer_id = _id(run_id, "issuer-document")
    sector_id = _id(run_id, "sector-document")
    issuer_passage_id = _id(run_id, "issuer-passage")
    sector_passage_id = _id(run_id, "sector-passage")
    published = datetime(2026, 5, 15, tzinfo=UTC)
    documents = [
        SourceDocument(id=issuer_id, canonical_url="https://synthetic.example/issuer/annual-results", final_url="https://synthetic.example/issuer/annual-results", publisher="Synthetic Bank Investor Relations", origin_family_id="synthetic-issuer", title="Synthetic Bank FY2026 results", document_type="issuer_results", published_at=published, retrieved_at=published, period_end=date(2026, 3, 31), content_hash="synthetic-issuer-hash", mime_type="text/html", local_object_key=None),
        SourceDocument(id=sector_id, canonical_url="https://synthetic.example/context/sector-review", final_url="https://synthetic.example/context/sector-review", publisher="Synthetic Sector Review", origin_family_id="synthetic-independent-context", title="Sector funding context", document_type="independent_context", published_at=datetime(2026, 6, 1, tzinfo=UTC), retrieved_at=datetime(2026, 6, 1, tzinfo=UTC), period_end=date(2026, 3, 31), content_hash="synthetic-sector-hash", mime_type="text/html", local_object_key=None),
    ]
    passages = [
        Passage(id=issuer_passage_id, document_id=issuer_id, section="Balance sheet highlights", row_label="Gross advances and deposits", column_label="FY2025 / FY2026", text="Synthetic Bank reported gross advances of INR 100000 crore at 31 March 2025 and INR 120000 crore at 31 March 2026. Total deposits were INR 125000 crore and INR 137500 crore at the same dates. The figures are consolidated year-end balances.", extraction_method="fixture", extraction_quality="manually_checked"),
        Passage(id=sector_passage_id, document_id=sector_id, section="Funding context", text="The independent sector review notes that deposit growth and loan growth can diverge during expansion periods, and that a growth gap alone does not establish funding stress. Deposit composition and funding cost are needed to test that mechanism.", extraction_method="fixture", extraction_quality="manually_checked"),
    ]
    fact_specs = [
        ("gross_advances", "100000", date(2025, 3, 31), "advances_prior"),
        ("gross_advances", "120000", date(2026, 3, 31), "advances_current"),
        ("deposits", "125000", date(2025, 3, 31), "deposits_prior"),
        ("deposits", "137500", date(2026, 3, 31), "deposits_current"),
    ]
    facts = []
    for metric, value, period_end, key in fact_specs:
        passage_id = issuer_passage_id
        facts.append(Fact(id=_id(run_id, key), entity_id=company.id, metric_key=metric, value_raw=value, value_decimal=Decimal(value), unit_raw="INR crore", unit_normalized="INR_crore", currency="INR", period_end=period_end, period_type=PeriodType.INSTANT, scope=Scope.CONSOLIDATED, segment="all", definition_id=f"{metric}_as_reported_v1", passage_id=passage_id, status=FactStatus.VERIFIED, extraction_confidence=Decimal("1")))
    return documents, passages, facts
