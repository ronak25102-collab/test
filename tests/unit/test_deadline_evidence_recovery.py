"""Crossing the final local verification deadline must not discard reviewed facts."""
from datetime import UTC, date, datetime, timedelta

import pytest
from signal_research.domain.enums import ResearchOutcome, RunMode
from signal_research.research.report_builder import build_abstention, build_synthetic_report
from signal_research.research.verifier import verify_report
from signal_research.worker.machine import ResearchMachine


def setup_crossing(store, settings, monkeypatch, checkpoint="partial", cancel=False, fenced=False, published=False):
    company = store.search_companies("SYNTHBANK")[0]
    run_id = store.create_run(company, date(2026, 10, 8), RunMode.LIVE)
    assert store.lease_next("deadline-test") == run_id
    evidence = build_synthetic_report(run_id, company, date(2026, 10, 8))
    partial = build_abstention(run_id, company, evidence.cutoff, evidence.documents, evidence.passages,
                               evidence.facts, mode="live")
    partial.calculations = evidence.calculations
    partial.outcome = ResearchOutcome.PARTIAL
    partial.limitations.append("A previously recorded extraction limitation.")
    returned = evidence if published else partial.model_copy(deep=True)
    if not published:
        returned.outcome = ResearchOutcome.INSUFFICIENT_EVIDENCE
        returned.limitations.append("A final assembly limitation.")
    calls = {"research": 0, "verification": 0}
    budgets = []
    machine = ResearchMachine(store, settings)
    monkeypatch.setattr(machine, "_check_live_cost_policy", lambda: None)

    def research(*args):
        calls["research"] += 1
        budgets.append(args[-1])
        if checkpoint != "missing":
            snapshot = evidence if checkpoint == "published" else partial
            store.checkpoint(run_id, "evidence_collected", 0, snapshot.model_dump(mode="json"))
            if checkpoint == "empty":
                empty = partial.model_copy(deep=True)
                empty.facts = []
                empty.calculations = []
                store.checkpoint(run_id, "evidence_collected", 1, empty.model_dump(mode="json"))
        store.update_run(run_id, limitations=["A current run limitation."])
        return returned

    def local_verify(report):
        calls["verification"] += 1
        result = verify_report(report)
        if report.outcome != ResearchOutcome.PARTIAL:
            budgets[0].deadline = datetime.now(UTC) - timedelta(seconds=1)
            if fenced:
                machine.lease_error = RuntimeError("worker lost its fenced lease")
        elif cancel:
            store.request_cancel(run_id)
        return result

    monkeypatch.setattr(machine, "_process_live", research)
    monkeypatch.setattr("signal_research.worker.machine.verify_report", local_verify)
    return machine, run_id, partial, calls


@pytest.mark.parametrize("published", [False, True])
def test_final_local_deadline_preserves_reviewed_facts_without_late_discovery(store, settings, monkeypatch, published):
    machine, run_id, partial, calls = setup_crossing(store, settings, monkeypatch, published=published)
    machine.process(run_id)
    report = store.get_report(run_id)
    assert store.get_summary(run_id).status.value == "completed"
    assert report.outcome == ResearchOutcome.PARTIAL and not report.discoveries
    assert report.facts == partial.facts and report.calculations == partial.calculations
    assert calls == {"research": 1, "verification": 2}
    assert report.generation_metadata["stopped_by_limit"] == "run deadline exceeded"
    assert "A previously recorded extraction limitation." in report.limitations
    assert "A current run limitation." in report.limitations
    if not published:
        assert "A final assembly limitation." in report.limitations
    assert store.get_summary(run_id).progress["facts_verified"] == len(partial.facts)
    verify_report(report)


@pytest.mark.parametrize("checkpoint", ["missing", "empty", "published"])
def test_deadline_does_not_recover_missing_empty_or_discovery_checkpoint(store, settings, monkeypatch, checkpoint):
    machine, run_id, _, calls = setup_crossing(store, settings, monkeypatch, checkpoint=checkpoint)
    machine.process(run_id)
    assert not store.has_report(run_id)
    assert store.get_summary(run_id).status.value == "failed"
    assert calls == {"research": 1, "verification": 1}


def test_cancellation_during_local_recovery_prevents_publication(store, settings, monkeypatch):
    machine, run_id, _, _ = setup_crossing(store, settings, monkeypatch, cancel=True)
    machine.process(run_id)
    assert not store.has_report(run_id)
    assert store.get_summary(run_id).status.value == "cancelled"


def test_lost_fenced_lease_prevents_deadline_recovery(store, settings, monkeypatch):
    machine, run_id, _, calls = setup_crossing(store, settings, monkeypatch, fenced=True)
    machine.process(run_id)
    assert not store.has_report(run_id)
    assert calls["verification"] == 1
