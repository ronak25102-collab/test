from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from signal_research.domain.enums import Profile
from signal_research.domain.schemas import Fact
from signal_research.extraction.column_tables import column_metric_lead
from signal_research.research.live import LiveResearch, derive_calculations

ENTITY = uuid4()


def fact(metric, value, year, *, scope="consolidated", month=6, start=None):
    percentage = metric in {"gnpa", "stage2_ratio", "stage3_ratio"}
    return Fact(
        id=uuid4(), entity_id=ENTITY, metric_key=metric, value_decimal=Decimal(value),
        period_end=date(year, month, 30 if month == 6 else 31), period_start=start,
        period_type="duration" if start else "instant", scope=scope, segment="all",
        unit_normalized="percent" if percentage else "INR_crore",
        currency=None if percentage else "INR", definition_id=metric,
        status="verified", passage_id=uuid4(),
    )


def research(profile, facts):
    result = LiveResearch.__new__(LiveResearch)
    result.company = SimpleNamespace(legal_name="Quartz Financial Limited", business_profiles=[profile])
    result.facts = facts
    result.calculations = derive_calculations(facts)
    return result


def test_nbfc_profit_and_revenue_do_not_stop_track_a_collection():
    facts = [fact(metric, value, 2025, month=12, start=start)
             for start in (date(2025, 10, 1), date(2025, 4, 1))
             for metric, value in (("revenue", "100"), ("net_profit", "20"))]
    result = research(Profile.NBFC, facts)
    assert len(result.calculations) >= 2
    assert not result.angle_evidence_ready()


def test_bank_funding_relationship_still_stops_early():
    result = research(Profile.BANK, [
        fact("deposits", "100", 2025), fact("deposits", "120", 2026),
        fact("borrowings", "30", 2025), fact("borrowings", "25", 2026),
    ])
    assert result.angle_evidence_ready()


def test_nbfc_growth_quality_needs_verified_arithmetic_in_both_groups():
    result = research(Profile.NBFC, [
        fact("aum", "100", 2025), fact("aum", "120", 2026),
        fact("gnpa", "1", 2025), fact("gnpa", "1.5", 2026),
    ])
    assert result.angle_evidence_ready()
    assert not result.angle_evidence_ready([
        calculation.model_copy(update={"available": False}) for calculation in result.calculations
    ])


def test_growth_and_quality_from_different_scopes_cannot_stop_collection():
    result = research(Profile.NBFC, [
        fact("aum", "100", 2025), fact("aum", "120", 2026),
        fact("gnpa", "1", 2025, scope="standalone"),
        fact("gnpa", "1.5", 2026, scope="standalone"),
    ])
    assert not result.angle_evidence_ready()


def test_disjoint_reporting_dates_cannot_stop_collection():
    result = research(Profile.NBFC, [
        fact("aum", "100", 2025), fact("aum", "120", 2026),
        fact("gnpa", "1", 2025, month=3), fact("gnpa", "1.5", 2026, month=3),
    ])
    assert not result.angle_evidence_ready()


def test_nbfc_operating_focus_requests_missing_lending_stock_and_quality():
    result = research(Profile.NBFC, [])
    result.extraction_paused = False
    result.cutoff = date(2026, 10, 16)
    result.budget = SimpleNamespace(model_calls=0, max_model_calls=50, remaining_seconds=lambda: 600)
    result.analysis_reserve = lambda: 240
    result.stage = lambda *args: None
    captured = {}
    result.extract = lambda **kwargs: captured.update(kwargs)
    result.collect_operating_metrics()
    assert {"aum", "on_book_loans", "gross_advances", "gnpa"} <= set(captured["focus_metrics"])
    assert "deposits" not in captured["focus_metrics"]


def test_observed_quality_metrics_do_not_hide_a_missing_growth_group():
    result = research(Profile.NBFC, [
        fact("gnpa", "1", 2026),
        fact("stage2_ratio", "1", 2026),
        fact("stage3_ratio", "1", 2026),
    ])
    result.extraction_paused = False
    result.cutoff = date(2026, 10, 16)
    result.budget = SimpleNamespace(model_calls=0, max_model_calls=50, remaining_seconds=lambda: 600)
    result.analysis_reserve = lambda: 240
    result.stage = lambda *args: None
    captured = {}
    result.extract = lambda **kwargs: captured.update(kwargs)
    result.collect_operating_metrics()
    assert "aum" in captured["focus_metrics"]


COLUMN_TABLE = """Quartz Financial Limited
Asset quality - Consolidated
INR crore
Particulars AUM GNPA % NNPA %
As at 30 June 2025 | 31 March 2026 | 30 June 2026
Retail lending 85,000 1.5% 1.8% 1.7% 0.6% 0.8% 0.7%
Business lending 15,000 1.2% 1.3% 1.2% 0.5% 0.6% 0.5%
Total 1,00,000 1.4% 1.7% 1.6% 0.6% 0.7% 0.6%
"""


def test_dated_column_metrics_with_numeric_total_are_extraction_leads_only():
    passage = SimpleNamespace(text=COLUMN_TABLE)
    assert column_metric_lead(passage, Profile.NBFC) is True
    # The hint has no fact IDs, values or approved candidates to publish.
    assert isinstance(column_metric_lead(passage, Profile.NBFC), bool)


def test_column_lead_preserves_scope_date_and_numeric_requirements():
    for text in (
        COLUMN_TABLE.replace("Consolidated", "Financial overview"),
        COLUMN_TABLE.replace("Consolidated", "Consolidated and standalone"),
        COLUMN_TABLE.replace("30 June 2025 | 31 March 2026 | 30 June 2026", "FY25 | FY26"),
        COLUMN_TABLE.replace("Total 1,00,000", "Portfolio 1,00,000"),
        COLUMN_TABLE.replace("Total 1,00,000 1.4% 1.7% 1.6% 0.6% 0.7% 0.6%", "Total not disclosed"),
        COLUMN_TABLE.replace("Particulars AUM GNPA % NNPA %", "Particulars AUM"),
    ):
        assert not column_metric_lead(SimpleNamespace(text=text), Profile.NBFC)


def test_footer_date_cannot_date_undated_metric_columns():
    text = COLUMN_TABLE.replace(
        "As at 30 June 2025 | 31 March 2026 | 30 June 2026", "Quarter 1 | Quarter 2 | Quarter 3"
    ) + "\nPresentation printed 30 June 2026"
    assert not column_metric_lead(SimpleNamespace(text=text), Profile.NBFC)


def test_ambiguous_unquoted_two_digit_years_remain_unverified():
    text = COLUMN_TABLE.replace(
        "30 June 2025 | 31 March 2026 | 30 June 2026", "30 Jun 25 | 31 Mar 26 | 30 Jun 26"
    )
    assert not column_metric_lead(SimpleNamespace(text=text), Profile.NBFC)
