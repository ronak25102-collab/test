from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from signal_research.db.errors import public_failure_message
from signal_research.db.repositories import Store
from signal_research.domain.enums import PublicationStatus, ResearchOutcome, RunMode, RunStatus
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
        self.lease_error = None

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
        pipeline_mode = self.store.run_configuration(run_id).get('pipeline_mode', self.settings.pipeline_mode)
        if pipeline_mode == "precomputed" and summary.mode != RunMode.REPLAY:
            from signal_research.precomputed.runtime import process_precomputed
            try:
                process_precomputed(self, run_id)
            except Exception as exc:
                if self.lease_error or "fenced lease" in str(exc) or self._cancelled(run_id):
                    return
                if self.store.has_report(run_id):
                    return
                logger.exception("precomputed playback %s failed", run_id)
                self.store.update_run(run_id, status=RunStatus.FAILED, stage=RunStatus.FAILED.value,
                                      limitations=[public_failure_message(exc)], ended=True)
                self.store.append_event(run_id, RunStatus.FAILED.value, "run_failed",
                                        "Stored evidence playback failed; no live research was attempted",
                                        error_code=getattr(exc, "code", "STAGE_FAILED"))
            return
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
        report = None
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
            cache = report.generation_metadata.get('cache_usage', {})
            self.store.update_run(run_id, progress={"sources_found": len(report.documents), "documents_parsed": len(report.documents), 'facts_verified': len(report.facts), 'facts_reused': cache.get('reused', 0), 'facts_fresh': cache.get('fresh', len(report.facts)), "calculations_completed": len(report.calculations), "counterevidence_checks": checks}, budget=budget.snapshot())
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
            if isinstance(exc, BudgetExceeded):
                try:
                    if self._preserve_evidence_at_limit(run_id, budget, exc, report.limitations if report else []):
                        return
                except Exception as recovery_error:
                    logger.exception("research run %s evidence recovery failed", run_id)
                    if self.lease_error or "fenced lease" in str(recovery_error):
                        return
                    if self._cancelled(run_id) or self.store.has_report(run_id):
                        return
                    exc = recovery_error
            self.store.update_run(run_id, status=RunStatus.FAILED, stage=RunStatus.FAILED.value, limitations=[public_failure_message(exc)], ended=True)
            self.store.append_event(run_id, RunStatus.FAILED.value, "run_failed", "Research stopped because a stage failed", error_code=getattr(exc, "code", "STAGE_FAILED"))

    def _preserve_evidence_at_limit(self, run_id, budget, error, limitations) -> bool:
        """Publish only the latest reviewed evidence checkpoint after a limit.

        This is local recovery, never a new research attempt or a late discovery.
        An empty latest checkpoint must not resurrect older withheld figures.
        """
        evidence = self.store.load_checkpoint(run_id, "evidence_collected", iteration=None)
        report = ResearchReport.model_validate(evidence) if evidence else None
        if (not report or report.outcome != ResearchOutcome.PARTIAL or not report.facts
                or report.discoveries or report.publication_status != PublicationStatus.ABSTAINED):
            return False
        current = self.store.get_summary(run_id)
        if report.run_id != run_id or report.company.id != current.company.id or report.cutoff != current.as_of:
            return False
        note = f"Research stopped at its configured limit: {error}. Verified evidence was preserved."
        report.limitations = list(dict.fromkeys([*report.limitations, *current.limitations, *limitations, note]))
        report.generation_metadata["stopped_by_limit"] = str(error)
        report = verify_report(report)
        if self._cancelled(run_id):
            return True
        self._set_stage(run_id, RunStatus.VERIFYING, "evidence_preserved_at_limit",
                        "Research limit reached; locally verified evidence was preserved without a discovery")
        cache = report.generation_metadata.get("cache_usage", {})
        self.store.update_run(run_id, progress={"sources_found": len(report.documents),
                              "documents_parsed": len(report.documents), "facts_verified": len(report.facts),
                              "facts_reused": cache.get("reused", 0), "facts_fresh": cache.get("fresh", len(report.facts)),
                              "calculations_completed": len(report.calculations),
                              "counterevidence_checks": len(report.generation_metadata.get("challenge_reviews", []))},
                              budget=budget.snapshot())
        self.store.save_report(report)
        return True

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
        from signal_research.providers.search.tavily_provider import SearchQuotaExceeded
        from signal_research.research.live import LiveResearch
        from signal_research.worker.calls import UncertainCall
        run_settings = self.settings.model_copy(update={'cold_start': self.settings.cold_start or self.store.get_summary(run_id).cold_start})
        research = LiveResearch(self, run_id, company, as_of, budget, settings=run_settings)

        def provider_stop(exc):
            """Partial report naming the actual provider cause, from durable routing records."""
            from signal_research.research.readiness import provider_cause
            search_failure = isinstance(exc, (SearchQuotaExceeded, FreeQuotaUnavailable))
            rejections = self.store.provider_rejections(run_id)
            cause = None if search_failure else provider_cause(rejections, run_settings, exc)
            retained = ('verified figures are retained' if research.facts else
                        'no figures had been verified yet, so nothing could be retained')
            reason = ('The Tavily search allowance is unavailable; restore search access before starting new research.'
                      if search_failure else
                      f'{cause}; {retained}.' if cause else
                      f'The model response timed out; {retained}.'
                      if 'TIMEOUT' in getattr(exc, 'code', '') else
                      f'The model provider did not return a valid completed response; {retained}.')
            reasons = [reason]
            if rejections['exhausted'] or rejections['rejected']:
                reasons.append('Restore model access (add CodeCraft credits or replace the rejected keys in .env), then start a new run.')
            reasons.append('A completed independent publication review of the candidate.')
            report = research.abstain(reasons)
            report.outcome = ResearchOutcome.PARTIAL
            preserved = 'Previously verified evidence was preserved' if research.facts else 'No verified evidence existed yet'
            report.limitations.append(f"Provider work stopped: {str(exc).rstrip('.')}. {preserved}; no discovery was substituted.")
            report.generation_metadata['provider_failure'] = getattr(exc, 'code', type(exc).__name__)
            if rejections['exhausted'] or rejections['rejected']:
                report.generation_metadata['provider_rejections'] = rejections
            return report

        try:
            report = research.run(plan)
            # Skipped timeouts let the run keep reading other sources. If none of them
            # yielded a figure, the gap is a provider failure, not an absence of evidence.
            if research.last_extraction_timeout and not report.facts and not report.discoveries:
                return provider_stop(research.last_extraction_timeout)
            return report
        except BudgetExceeded as exc:
            # Stop all provider work, then locally verify and save what has
            # already been independently checked. A limit is not a discovery.
            report = research.abstain(["Additional investigation within the configured research limits"])
            report.outcome = ResearchOutcome.PARTIAL
            report.limitations.append(f"Research stopped at its configured limit: {exc}. Verified evidence was preserved.")
            report.generation_metadata["stopped_by_limit"] = str(exc)
            return report
        except (CodeCraftError, NvidiaRequestError, FreeQuotaUnavailable, SearchQuotaExceeded, UncertainCall, httpx.HTTPError) as exc:
            return provider_stop(exc)

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
