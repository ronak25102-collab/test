from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from signal_research.db.repositories import Store
from signal_research.domain.enums import ResearchOutcome, RunMode, RunStatus
from signal_research.domain.errors import BudgetExceeded
from signal_research.domain.schemas import ResearchReport
from signal_research.research.planner import initial_plan
from signal_research.research.report_builder import build_synthetic_report
from signal_research.research.verifier import verify_report
from signal_research.settings import Settings

from .budgets import Budget

logger = logging.getLogger(__name__)


class CostPolicyError(RuntimeError):
    code = "COST_POLICY_UNCONFIGURED"


class ResearchMachine:
    def __init__(self, store: Store, settings: Settings):
        self.store = store
        self.settings = settings

    def process(self, run_id: UUID) -> None:
        from threading import Event, Thread
        stop = Event()
        self.lease_error = None
        def renew():
            while not stop.wait(10):
                try:
                    self.store.heartbeat(run_id)
                except Exception as exc:
                    self.lease_error = exc
                    return
        thread = Thread(target=renew, daemon=True, name="lease-renewal")
        thread.start()
        try:
            self._process(run_id)
        finally:
            stop.set()
            thread.join(timeout=2)

    def _process(self, run_id: UUID) -> None:
        run_id = UUID(str(run_id))
        if self.store.has_report(run_id):
            report = self.store.get_report(run_id)
            self.store.update_run(run_id, status=RunStatus.COMPLETED, stage=RunStatus.COMPLETED.value, outcome=report.outcome, ended=True)
            return
        summary = self.store.get_summary(run_id)
        if not summary:
            return
        self.store.update_run(run_id, started=True)
        summary = self.store.get_summary(run_id)
        saved = summary.budget
        limits = saved.get("limits", {})
        started = summary.started_at.replace(tzinfo=UTC) if summary.started_at.tzinfo is None else summary.started_at
        duration = min(self.settings.max_run_seconds, self.settings.demo_target_seconds) if summary.mode == RunMode.LIVE else self.settings.max_run_seconds
        deadline = datetime.fromisoformat(saved["deadline"]) if saved.get("deadline") else started + timedelta(seconds=duration)
        budget = Budget(**{k: limits.get(k, getattr(self.settings, k)) for k in ("max_search_calls", "max_fetch_documents", "max_model_calls", "max_ocr_pages", "max_input_tokens", "max_output_tokens")},
                        max_cost_usd=limits.get("max_cost_usd", self.settings.max_run_cost_usd), deadline=deadline,
                        **{k: saved.get(k, 0) for k in ("search_calls", "fetch_documents", "model_calls", "ocr_pages", "input_tokens", "output_tokens", "reserved_cost_usd")},
                        persist=lambda value: self.store.update_run(run_id, budget=value))
        self.store.update_run(run_id, budget=budget.snapshot())
        try:
            recovered = self.store.load_checkpoint(run_id, RunStatus.VERIFYING.value)
            recovered_report = ResearchReport.model_validate(recovered) if recovered else None
            if recovered_report is None and datetime.now(UTC) >= deadline:
                evidence = self.store.load_checkpoint(run_id, "evidence_collected", iteration=None)
                snapshot = ResearchReport.model_validate(evidence) if evidence else None
                if snapshot and snapshot.outcome == ResearchOutcome.PARTIAL and snapshot.facts:
                    recovered_report = verify_report(snapshot)
            # A verified partial checkpoint can be saved locally after its limit;
            # resuming it never extends the deadline or sends provider requests.
            if not recovered_report or recovered_report.outcome != ResearchOutcome.PARTIAL:
                budget.check()
            self._stage(run_id, RunStatus.RESOLVING, "entity_resolved", f"Resolved {summary.company.legal_name} to {','.join(summary.company.symbols)}")
            if self._cancelled(run_id):
                return
            profile = summary.company.business_profiles[0] if summary.company.business_profiles else "ambiguous"
            self._stage(run_id, RunStatus.PLANNING, "plan_created", f"Selected the {profile} profile and bounded starter questions")
            plan = initial_plan(summary.company.legal_name, profile, summary.company.symbols[0], str(summary.as_of)) if profile != "ambiguous" else []
            self.store.checkpoint(run_id, RunStatus.PLANNING.value, 0, [task.query for task in plan])
            if self._cancelled(run_id):
                return
            if recovered_report:
                report = recovered_report
            elif summary.mode == RunMode.REPLAY:
                report = self._process_replay(run_id, summary.as_of, summary.company, budget)
            else:
                self._check_live_cost_policy()
                report = self._process_live(run_id, summary.as_of, summary.company, plan, budget)
            if self._cancelled(run_id):
                return
            self._set_stage(run_id, RunStatus.VERIFYING, "verification_started", "Checking cutoff, citations, calculations and publication gates")
            report = verify_report(report)
            self.store.checkpoint(run_id, RunStatus.VERIFYING.value, 0, report.model_dump(mode="json"))
            self._set_stage(run_id, RunStatus.COMPOSING, "report_composed", "Composed the validated report from verified artifacts")
            if report.outcome != ResearchOutcome.PARTIAL:
                budget.check()
            checks = len(report.generation_metadata.get('challenge_reviews', []))
            if report.source_coverage.get('synthetic'):
                checks = 1 if report.discoveries else 0
            self.store.update_run(run_id, progress={"sources_found": len(report.documents), "documents_parsed": len(report.documents), "calculations_completed": len(report.calculations), "counterevidence_checks": checks}, budget=budget.snapshot())
            self.store.save_report(report)
        except Exception as exc:
            if getattr(exc, "code", None):
                logger.error("research run %s stopped: %s", run_id, exc)
            else:
                logger.exception("research run %s failed", run_id)
            if self.lease_error or "fenced lease" in str(exc):
                return
            if self._cancelled(run_id):
                return
            if self.store.has_report(run_id):
                return  # DB publication succeeded; an optional export-file write failed.
            self.store.update_run(run_id, status=RunStatus.FAILED, stage=RunStatus.FAILED.value, limitations=[str(exc)], ended=True)
            self.store.append_event(run_id, RunStatus.FAILED.value, "run_failed", "Research stopped because a stage failed", error_code=getattr(exc, "code", "STAGE_FAILED"))

    def _process_replay(self, run_id, as_of, company, budget) -> ResearchReport:
        self._set_stage(run_id, RunStatus.DISCOVERING, "queries_selected", "Selected profile queries and a targeted counterevidence query")
        budget.reserve("search_calls", 3)
        self._set_stage(run_id, RunStatus.FETCHING, "documents_found", "Loaded two explicitly labelled synthetic public-evidence fixtures")
        budget.reserve("fetch_documents", 2)
        self.store.update_run(run_id, progress={"sources_found": 2, "documents_parsed": 0, "calculations_completed": 0, "counterevidence_checks": 0})
        self._set_stage(run_id, RunStatus.EXTRACTING, "documents_parsed", "Parsed page-level passages while retaining table labels and units")
        self._set_stage(run_id, RunStatus.NORMALIZING, "facts_normalized", "Normalized Indian monetary values and preserved source scope")
        self._set_stage(run_id, RunStatus.HYPOTHESIZING, "hypotheses_created", "Generated two observation-first candidates and prioritized the funding-growth angle")
        self._set_stage(run_id, RunStatus.INVESTIGATING, "calculations_completed", "Calculated growth, growth gap and loan-to-deposit relationships")
        report = build_synthetic_report(run_id, company, as_of)
        self.store.update_run(run_id, progress={"sources_found": len(report.documents), "documents_parsed": len(report.passages), "calculations_completed": len(report.calculations), "counterevidence_checks": 0})
        self._set_stage(run_id, RunStatus.CHALLENGING, "counterevidence_checked", "Searched the strongest alternative and retained the unresolved qualification")
        self.store.update_run(run_id, progress={"sources_found": len(report.documents), "documents_parsed": len(report.passages), "calculations_completed": len(report.calculations), "counterevidence_checks": 1})
        return report

    def _process_live(self, run_id, as_of, company, plan, budget) -> ResearchReport:
        import httpx

        from signal_research.providers.llm.codecraft_provider import CodeCraftError
        from signal_research.providers.llm.nvidia_provider import NvidiaRequestError
        from signal_research.providers.search.account import FreeQuotaUnavailable
        from signal_research.research.live import LiveResearch
        from signal_research.worker.calls import UncertainCall
        run_settings = self.settings.model_copy(update={'cold_start': self.settings.cold_start or self.store.get_summary(run_id).cold_start})
        research = LiveResearch(self, run_id, company, as_of, budget)
        research.settings = run_settings
        research.calls.settings = run_settings
        try:
            return research.run(plan)
        except BudgetExceeded as exc:
            # Stop all provider work, then locally verify and save what has
            # already been independently checked. A limit is not a discovery.
            report = research.abstain(["Additional investigation within the configured research limits"])
            report.outcome = ResearchOutcome.PARTIAL
            report.limitations.append(f"Research stopped at its configured limit: {exc}. Verified evidence was preserved.")
            report.generation_metadata["stopped_by_limit"] = str(exc)
            return report
        except (CodeCraftError, NvidiaRequestError, FreeQuotaUnavailable, UncertainCall, httpx.HTTPError) as exc:
            if not research.facts:
                raise
            report = research.abstain(["Provider access recovery and additional independently verified evidence"])
            report.outcome = ResearchOutcome.PARTIAL
            report.limitations.append(f"Provider work stopped: {exc}. Previously verified evidence was preserved; no discovery was substituted.")
            report.generation_metadata['provider_failure'] = getattr(exc, 'code', type(exc).__name__)
            return report

    def _check_live_cost_policy(self):
        if not self.settings.llm_configured:
            from signal_research.providers.llm.base import ProviderNotConfigured
            raise ProviderNotConfigured(f"{self.settings.llm_provider} key and both model roles must be configured")
        from signal_research.research.readiness import live_readiness
        readiness = live_readiness(self.settings)
        if not readiness["ready"]:
            raise CostPolicyError(" ".join(readiness["issues"]))

    def _set_stage(self, run_id, status, event_type, summary):
        if self.lease_error:
            raise self.lease_error
        self.store.heartbeat(run_id)
        self.store.update_run(run_id, status=status, stage=status.value)
        self.store.append_event(run_id, status.value, event_type, summary)

    def _stage(self, run_id, status, event_type, summary):
        self._set_stage(run_id, status, event_type, summary)
        self.store.checkpoint(run_id, status.value, 0, {"event": event_type})

    def _cancelled(self, run_id: UUID) -> bool:
        if not self.store.is_cancelled(run_id):
            return False
        self.store.update_run(run_id, status=RunStatus.CANCELLED, stage=RunStatus.CANCELLED.value, ended=True)
        self.store.append_event(run_id, RunStatus.CANCELLED.value, "run_cancelled", "Cancellation was honored before the next unit of work")
        return True
