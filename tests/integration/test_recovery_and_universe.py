from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import BaseModel
from signal_research.db.models import CompanyModel, ResearchRunModel
from signal_research.domain.enums import RunMode, RunStatus
from signal_research.providers.llm.base import ProviderUsage
from signal_research.research.report_builder import build_synthetic_report
from signal_research.worker.budgets import Budget
from signal_research.worker.calls import DurableCalls, UncertainCall


def test_bootstrap_updates_sbi_domains_without_removing_existing_domains(store):
    company = store.search_companies("SBIN")[0]
    with store.session_factory() as session:
        session.get(CompanyModel, str(company.id)).verified_ir_domains = ["sbi.co.in", "reports.sbi.co.in"]
        session.commit()
    store.bootstrap()
    store.bootstrap()
    assert store.get_company(company.id).verified_ir_domains == ["sbi.bank.in", "sbi.co.in", "reports.sbi.co.in"]


@pytest.mark.parametrize("symbol,current,legacy", [
    ("AXISBANK", "axis.bank.in", "axisbank.com"),
    ("HDFCBANK", "hdfc.bank.in", "hdfcbank.com"),
    ("ICICIBANK", "icici.bank.in", "icicibank.com"),
    ("KOTAKBANK", "kotak.bank.in", "kotak.com"),
    ("SBIN", "sbi.bank.in", "sbi.co.in"),
])
def test_bootstrap_refreshes_every_supported_bank_and_keeps_identity_history(store, symbol, current, legacy):
    company = store.search_companies(symbol)[0]
    with store.session_factory() as session:
        row = session.get(CompanyModel, str(company.id))
        row.verified_ir_domains = [legacy, "reports." + legacy]
        row.isin = "EXISTING-ISIN"
        session.commit()
    store.bootstrap()
    store.bootstrap()
    updated = store.get_company(company.id)
    assert updated.verified_ir_domains == [current, legacy, "reports." + legacy]
    assert updated.isin == "EXISTING-ISIN"


def test_snapshot_adds_unseeded_financial_identity_without_json_like(store):
    payload = {"id": str(uuid4()), "source_url": "https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv", "fetched_at": datetime.now(UTC).isoformat(), "content_hash": "c" * 64, "constituents": [{"Symbol": "NEWBANK", "Company Name": "New Bank Limited", "Industry": "Financial Services", "ISIN Code": "INNEW123"}, {"Symbol": "NEWFINSERV", "Company Name": "New Financial Services Limited", "Industry": "Financial Services"}]}
    assert store.save_universe_snapshot(payload) == 2
    assert store.save_universe_snapshot(payload) == 0
    company = store.search_companies("NEWBANK")[0]
    assert company.business_profiles[0].value == "bank" and company.isin == "INNEW123"
    assert store.search_companies("NEWFINSERV")[0].business_profiles[0].value == "diversified"


def test_report_and_terminal_state_commit_together(store):
    company = store.search_companies("SYNTHBANK")[0]
    run_id = store.create_run(company, date(2026, 10, 8), RunMode.REPLAY)
    store.lease_next("worker")
    store.update_run(run_id, status=RunStatus.COMPOSING)
    store.save_report(build_synthetic_report(run_id, company, date(2026, 10, 8)))
    assert store.get_report(run_id) and store.get_summary(run_id).status == RunStatus.COMPLETED
    evidence = store.find_claim(run_id, store.get_report(run_id).claims[0].id)
    assert evidence["evidence"][0]["passage"] and evidence["evidence"][0]["document"]


def test_active_run_cap_and_stale_lease_fencing(store):
    company = store.search_companies("SYNTHBANK")[0]
    run_id = store.create_run(company, date(2026, 10, 8), RunMode.REPLAY)
    store.create_run(company, date(2026, 10, 8), RunMode.REPLAY)
    assert store.lease_next("worker-one") == run_id
    assert store.lease_next("worker-two") is None
    with store.session_factory() as session:
        row = session.get(ResearchRunModel, str(run_id))
        row.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    with pytest.raises(RuntimeError, match="fenced lease"):
        store.heartbeat(run_id)


def test_uncertain_provider_call_is_never_repeated(store, settings):
    run_id = store.create_run(store.search_companies("SYNTHBANK")[0], date(2026, 10, 8), RunMode.REPLAY)
    calls = DurableCalls(store, settings, run_id, Budget(2, 2, 2, 1))
    count = []
    def failing():
        count.append(1)
        raise RuntimeError("connection lost after sending")
    with pytest.raises(RuntimeError):
        calls.invoke(["provider", "request"], "discovering", lambda: calls.budget.reserve("search_calls"), failing)
    with pytest.raises(UncertainCall):
        calls.invoke(["provider", "request"], "discovering", lambda: calls.budget.reserve("search_calls"), failing)
    assert count == [1] and calls.budget.search_calls == 1


def test_model_timeout_is_separate_from_download_timeout_and_bounded_by_run(store, settings, monkeypatch):
    class Probe(BaseModel):
        status: str

    deadlines = []

    class Adapter:
        def generate(self, schema, messages, role, deadline, outputs):
            deadlines.append(deadline.total_seconds())
            return Probe(status="ok"), ProviderUsage(input_tokens=10, output_tokens=10)

    monkeypatch.setattr("signal_research.worker.calls.get_llm_provider", lambda s: Adapter())
    settings.source_request_timeout_seconds = 1
    settings.model_request_timeout_seconds = 90
    budget = Budget(2, 2, 2, 1, deadline=datetime.now(UTC) + timedelta(seconds=60))
    run_id = store.create_run(store.search_companies("SYNTHBANK")[0], date(2026, 10, 8), RunMode.REPLAY)
    result = DurableCalls(store, settings, run_id, budget).model(Probe, {"test": "timeout"})
    assert result.status == "ok"
    assert 50 < deadlines[0] <= 60


def test_idempotency_rejects_conflicting_request(store):
    company = store.search_companies("SYNTHBANK")[0]
    store.create_run(company, date(2026, 10, 8), RunMode.REPLAY, "key")
    with pytest.raises(ValueError, match="different request"):
        store.create_run(company, date(2026, 10, 7), RunMode.REPLAY, "key")
