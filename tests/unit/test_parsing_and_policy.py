from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from reportlab.pdfgen import canvas
from signal_research.domain.enums import Profile
from signal_research.domain.errors import BudgetExceeded
from signal_research.domain.schemas import Fact
from signal_research.extraction.xbrl import parse_safe_xbrl
from signal_research.finance.calculations import calculate, numeric_fact
from signal_research.finance.periods import quarter
from signal_research.research.live import derive_calculations
from signal_research.retrieval.metadata import domain_matches, source_publication
from signal_research.retrieval.passages import (
    bounded_parse_pdf,
    parse_html,
    parse_pdf,
    parse_xbrl,
    recover_rupee_glyphs,
)
from signal_research.worker.budgets import Budget


def test_html_table_preserves_row_and_column_locators():
    identifier = uuid4()
    raw = b'<html><p>Consolidated INR crore</p><table><tr><th>Metric</th><th>31 March 2026</th></tr><tr><td>Deposits</td><td>100</td></tr></table></html>'
    parsed = parse_html(identifier, raw)
    table = next(p for p in parsed.passages if p.table_id is not None)
    assert table.row_label == "Deposits" and "31 March 2026" in table.column_label
    assert [p.id for p in parsed.passages] == [p.id for p in parse_html(identifier, raw).passages]


def test_pdf_process_preserves_physical_page_locator(tmp_path):
    path = tmp_path / "report.pdf"
    pdf = canvas.Canvas(str(path))
    pdf.drawString(50, 750, "Published on 15 May 2026. Consolidated advances: INR 100 crore.")
    pdf.showPage()
    pdf.drawString(50, 750, "Consolidated deposits: INR 200 crore at 31 March 2026.")
    pdf.save()
    parsed = bounded_parse_pdf(uuid4(), path, 10)
    assert {p.page_index for p in parsed.passages} == {0, 1}


def test_large_pdf_keeps_all_pages_and_headers_without_exhaustive_tables(tmp_path, monkeypatch):
    path = tmp_path / "annual.pdf"
    pdf = canvas.Canvas(str(path))
    for index in range(81):
        pdf.drawString(50, 750, f"Page {index + 1}: INR crore at 30.06.2026")
        pdf.drawString(50, 730, "Deposits 100; Advances 90")
        pdf.showPage()
    pdf.save()
    import pdfplumber
    monkeypatch.setattr(pdfplumber, "open", lambda *a, **k: pytest.fail("Large PDFs must avoid exhaustive table detection"))
    identifier = uuid4()
    parsed = parse_pdf(identifier, path)
    assert parsed.extraction_method == "pdf_layout"
    assert {p.page_index for p in parsed.passages} == set(range(81))
    assert all("30.06.2026" in p.text and "Deposits 100" in p.text for p in parsed.passages)
    assert [p.id for p in parsed.passages] == [p.id for p in parse_pdf(identifier, path).passages]


def test_pdf_timeout_does_not_expose_local_command_or_paths(tmp_path, monkeypatch):
    import subprocess
    def expired(*args, **kwargs):
        raise subprocess.TimeoutExpired("private-command", kwargs["timeout"])
    monkeypatch.setattr(subprocess, "run", expired)
    with pytest.raises(RuntimeError) as error:
        bounded_parse_pdf(uuid4(), tmp_path / "private-document.pdf", 90)
    assert str(error.value) == "PDF parsing exceeded its 90-second limit"


def test_rupee_font_recovery_never_changes_ordinary_letters():
    chars = [{"text": "C", "fontname": "AAATJJ+ITFRupee"},
             {"text": "C", "fontname": "Helvetica"},
             {"text": "1", "fontname": "AAATJJ+ITFRupee"}]
    recover_rupee_glyphs(chars)
    assert [char["text"] for char in chars] == ["\u20b9", "C", "1"]


def test_bank_rupee_fonts_recover_backticks_without_changing_ordinary_backticks():
    chars = [{"text": "`", "fontname": "ABCDEE+Rupee"},
             {"text": "`", "fontname": "BCDKEE+RupeeForadian"},
             {"text": "`", "fontname": "Helvetica"},
             {"text": "C", "fontname": "Rupee"}]
    recover_rupee_glyphs(chars)
    assert [char["text"] for char in chars] == ["\u20b9", "\u20b9", "`", "C"]


def test_xbrl_keeps_entity_context_dates_units_and_dimensions():
    raw = b'''<?xml version="1.0"?><xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:f="urn:finance"><context id="c1"><entity><identifier scheme="ISIN">INTEST123</identifier><segment><explicitMember dimension="f:scope">f:ConsolidatedMember</explicitMember></segment></entity><period><instant>2026-03-31</instant></period></context><unit id="u1"><measure>iso4217:INR</measure></unit><f:GrossAdvances contextRef="c1" unitRef="u1" decimals="0">1200000000</f:GrossAdvances><f:PublicationDate>2026-05-15</f:PublicationDate></xbrl>'''
    facts = parse_safe_xbrl(raw)
    assert facts[0]["entity_identifier"] == "INTEST123"
    assert facts[0]["period_end"] == "2026-03-31" and facts[0]["unit"] == "INR rupees"
    passage = parse_xbrl(uuid4(), raw).passages[0]
    assert "Gross Advances" in passage.text and "Consolidated Member" in passage.text
    assert source_publication(raw, passage.text).date() == date(2026, 5, 15)


def test_cutoff_date_never_comes_from_balance_period():
    assert source_publication(b'<html><p>Balances at 31 March 2026</p></html>', 'Balances at 31 March 2026') is None
    assert domain_matches("reports.bank.com", "bank.com")
    assert not domain_matches("bank.com.evil.example", "bank.com")


@pytest.mark.parametrize("profile,metric,unit,values", [(Profile.NBFC, "aum", "INR_crore", ("120", "100")), (Profile.LIFE_INSURER, "vnb", "INR_crore", ("120", "100")), (Profile.GENERAL_INSURER, "combined_ratio", "percent", ("95", "100")), (Profile.EXCHANGE, "transaction_revenue", "INR_crore", ("120", "100")), (Profile.ASSET_MANAGER, "average_aum", "INR_crore", ("120", "100")), (Profile.DIVERSIFIED, "segment_profit", "INR_crore", ("120", "100"))])
def test_registered_calculations_work_across_profiles(profile, metric, unit, values):
    entity = uuid4()
    facts = [Fact(id=uuid4(), entity_id=entity, metric_key=metric, value_decimal=Decimal(value), unit_normalized=unit, currency="INR", period_start=date(year - 1, 4, 1), period_end=date(year, 3, 31), period_type="duration", scope="consolidated", definition_id=metric, passage_id=uuid4(), status="verified") for value, year in zip(values, (2026, 2025), strict=True)]
    calculations = derive_calculations(facts)
    assert calculations and calculations[0].output_value == Decimal("-5" if unit == "percent" else "20")
    assert calculate(calculations[0].formula_id, [numeric_fact(f) for f in facts]).available


def test_budget_enforces_cumulative_tokens_and_cost():
    budget = Budget(2, 2, 2, 1, max_input_tokens=100, max_output_tokens=100, max_cost_usd=.1)
    budget.reserve_model(40, 40, .04)
    with pytest.raises(BudgetExceeded):
        budget.reserve_model(70, 1, .01)
    with pytest.raises(BudgetExceeded):
        budget.reserve_model(1, 1, .07)
    assert budget.model_calls == 1


def test_calendar_year_quarter_has_inclusive_end():
    assert quarter("Q1 FY2026", fiscal_year_end_month=12).end == date(2026, 3, 31)
