from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from signal_research.db.models import ResearchRunModel
from signal_research.domain.enums import RunMode, RunStatus
from signal_research.research.report_builder import build_synthetic_report
from signal_research.worker.budgets import Budget
from signal_research.worker.calls import DurableCalls, UncertainCall


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


def test_idempotency_rejects_conflicting_request(store):
    company = store.search_companies("SYNTHBANK")[0]
    store.create_run(company, date(2026, 10, 8), RunMode.REPLAY, "key")
    with pytest.raises(ValueError, match="different request"):
        store.create_run(company, date(2026, 10, 7), RunMode.REPLAY, "key")
