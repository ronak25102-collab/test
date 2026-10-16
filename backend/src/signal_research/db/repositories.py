from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import func, or_, select, update

from signal_research.domain.enums import ResearchOutcome, RunMode, RunStatus
from signal_research.domain.schemas import Company, ResearchReport, RunEvent, RunSummary
from signal_research.research.identity import identity_aliases, normalize_name

from .models import (
    CompanyModel,
    ResearchRunModel,
    RunEventModel,
    SourceDocumentModel,
    StageCheckpointModel,
    UniverseSnapshotModel,
)

UNIVERSE_SEED = [
    ("Axis Bank", "AXISBANK", "bank"),
    ("BSE Limited", "BSE", "exchange"),
    ("Bajaj Finance", "BAJFINANCE", "nbfc"),
    ("Bajaj Finserv", "BAJAJFINSV", "diversified"),
    ("HDFC Bank", "HDFCBANK", "bank"),
    ("HDFC Life Insurance Company", "HDFCLIFE", "life_insurer"),
    ("ICICI Bank", "ICICIBANK", "bank"),
    ("Jio Financial Services", "JIOFIN", "diversified"),
    ("Kotak Mahindra Bank", "KOTAKBANK", "bank"),
    ("SBI Life Insurance Company", "SBILIFE", "life_insurer"),
    ("Shriram Finance", "SHRIRAMFIN", "nbfc"),
    ("State Bank of India", "SBIN", "bank"),
    ("SYNTHBANK", "SYNTHBANK", "bank"),
]

IR_DOMAINS = {
    "BSE": ["bseindia.com"],
    "AXISBANK": ["axis.bank.in", "axisbank.com"],
    "BAJFINANCE": ["bajajfinserv.in"],
    "BAJAJFINSV": ["bajajfinserv.in"],
    "HDFCBANK": ["hdfc.bank.in", "hdfcbank.com"],
    "HDFCLIFE": ["hdfclife.com"],
    "ICICIBANK": ["icici.bank.in", "icicibank.com"],
    "JIOFIN": ["jfs.in"],
    "KOTAKBANK": ["kotak.bank.in", "kotak.com"],
    "SBILIFE": ["sbilife.co.in"],
    "SHRIRAMFIN": ["shriramfinance.in"],
    "SBIN": ["sbi.bank.in", "sbi.co.in"],
}


class Store:
    def __init__(self, session_factory, data_dir: Path):
        self.session_factory = session_factory
        self.data_dir = data_dir
        self.lease_tokens = {}

    def bootstrap(self) -> None:
        with self.session_factory() as session:
            for legal_name, symbol, profile in UNIVERSE_SEED:
                company_id = str(uuid5(NAMESPACE_URL, f"signal-research/company/{symbol}"))
                existing = session.get(CompanyModel, company_id)
                if existing:
                    existing.aliases = list(dict.fromkeys([*(existing.aliases or []), *identity_aliases(legal_name)]))
                    if symbol in IR_DOMAINS:
                        existing.verified_ir_domains = list(dict.fromkeys([
                            *IR_DOMAINS[symbol], *(existing.verified_ir_domains or []),
                        ]))
                    continue
                session.add(CompanyModel(
                    id=company_id, legal_name=legal_name, symbols=[symbol], aliases=identity_aliases(legal_name),
                    verified_ir_domains=IR_DOMAINS.get(symbol, []), business_profiles=[profile], identity_source_ids=[],
                ))
            session.commit()
        self.quarantine_legacy_issuer_domains()

    def quarantine_legacy_issuer_domains(self):
        """Quarantine domains without current issuer-bound proof; retain a backup."""
        from signal_research.retrieval.issuer_identity import ISSUER_REFERENCE_POLICY
        from signal_research.retrieval.metadata import domain_matches

        from .models import ArtifactModel

        with self.session_factory() as session:
            approved = {}
            for proof in session.scalars(select(ArtifactModel).where(ArtifactModel.kind == 'issuer_domain_verification')):
                if proof.payload.get('reference_policy') != ISSUER_REFERENCE_POLICY:
                    continue
                run = session.get(ResearchRunModel, proof.run_id)
                if not run or proof.payload.get('company_id') != run.company_id:
                    continue
                approved.setdefault(run.company_id, set()).update(proof.payload.get('domains', []))
            changes = []
            for company in session.scalars(select(CompanyModel)):
                base = [domain for symbol in company.symbols or [] for domain in IR_DOMAINS.get(symbol, [])]
                existing = company.verified_ir_domains or []
                allowed = [domain for domain in existing if domain in approved.get(company.id, set())
                           or any(domain_matches(domain, seed) for seed in base)]
                if allowed != existing:
                    changes.append({'company_id': company.id, 'legal_name': company.legal_name,
                                    'before': existing, 'after': allowed,
                                    'identity_source_ids': company.identity_source_ids or []})
                    company.verified_ir_domains = allowed
            if changes:
                folder = self.data_dir / 'exports' / 'domain-audits'
                folder.mkdir(parents=True, exist_ok=True)
                backup = folder / f'registry-before-{uuid4().hex}.json'
                backup.write_text(json.dumps({'policy': ISSUER_REFERENCE_POLICY,
                    'audited_at': datetime.now(UTC).isoformat(), 'changes': changes}, indent=2), encoding='utf-8')
                session.commit()

    def search_companies(self, query: str) -> list[Company]:
        lowered = query.strip().lower()
        normalized = normalize_name(query)
        with self.session_factory() as session:
            rows = session.scalars(select(CompanyModel).order_by(CompanyModel.legal_name)).all()
            matches = [r for r in rows if lowered in r.legal_name.lower() or any(lowered in s.lower() for s in (r.symbols or []) + (r.aliases or [])) or any(normalized in normalize_name(name) for name in [r.legal_name, *(r.aliases or [])])]
            matches.sort(key=lambda r: (lowered not in [s.lower() for s in r.symbols], r.legal_name))
            return [company_schema(row) for row in matches[:20]]

    def snapshot_age_days(self, source_url=None) -> int | None:
        with self.session_factory() as session:
            query = select(UniverseSnapshotModel)
            if source_url:
                query = query.where(UniverseSnapshotModel.source_url == source_url)
            latest = session.scalar(query.order_by(UniverseSnapshotModel.fetched_at.desc()))
            if not latest:
                return None
            return max(0, (datetime.now(UTC).date() - latest.fetched_at.date()).days)

    def save_universe_snapshot(self, payload: dict[str, Any]) -> int:
        """Persist a refreshed universe without replacing identity history."""
        rows = payload.get("constituents", [])
        with self.session_factory() as session:
            snapshot_id = payload.get("id", str(uuid4()))
            if not session.scalar(select(UniverseSnapshotModel).where(UniverseSnapshotModel.content_hash == payload["content_hash"])):
                session.add(UniverseSnapshotModel(id=snapshot_id, source_url=payload["source_url"], fetched_at=datetime.fromisoformat(payload["fetched_at"]), content_hash=payload["content_hash"], constituents=rows, is_cached=payload.get("is_cached", False)))
            added = 0
            for row in rows:
                symbol = row.get("Symbol") or row.get("SYMBOL") or row.get("symbol")
                legal_name = row.get("Company Name") or row.get("CompanyName") or row.get("COMPANY NAME") or row.get("NAME OF COMPANY") or symbol
                if not symbol or not legal_name:
                    continue
                symbol = symbol.upper().strip()
                company_id = str(uuid5(NAMESPACE_URL, f"signal-research/company/{symbol}"))
                existing = session.get(CompanyModel, company_id)
                if existing:
                    existing.isin = existing.isin or row.get("ISIN Code") or row.get("ISIN NUMBER")
                    existing.exchange = existing.exchange or "NSE"
                    continue
                industry = " ".join(str(row.get(key, "")) for key in ("Industry", "Sector", "ISIN Code")).lower()
                profile = infer_profile(f"{industry} {legal_name.lower()}")
                if profile or "financial" in industry:
                    session.add(CompanyModel(id=company_id, legal_name=legal_name.strip(), symbols=[symbol], isin=row.get("ISIN Code") or row.get("ISIN NUMBER"), exchange="NSE", aliases=identity_aliases(legal_name.strip()), verified_ir_domains=[], business_profiles=[profile] if profile else [], identity_source_ids=[]))
                    added += 1
            session.commit()
            return added

    def add_verified_issuer_domains(self, company_id, domains, source_id, *, run_id=None, proof=None):
        """Persist exchange-disclosure provenance together with its website references."""
        with self.session_factory() as session:
            row = session.get(CompanyModel, str(company_id))
            if not row:
                raise KeyError("company not found")
            row.verified_ir_domains = list(dict.fromkeys([*(row.verified_ir_domains or []), *domains]))
            row.identity_source_ids = list(dict.fromkeys([*(row.identity_source_ids or []), str(source_id)]))
            if proof is not None:
                from signal_research.retrieval.issuer_identity import ISSUER_REFERENCE_POLICY

                from .models import ArtifactModel

                if run_id is None:
                    raise ValueError('A domain verification proof requires its research run')
                owner = session.get(ResearchRunModel, str(run_id))
                if (not owner or owner.company_id != str(company_id)
                        or proof.get('company_id') != str(company_id)
                        or proof.get('reference_policy') != ISSUER_REFERENCE_POLICY
                        or set(proof.get('domains', [])) != set(domains)
                        or proof.get('document_id') != str(source_id)):
                    raise ValueError('Domain proof does not bind the company, run, source and domain set')
                self._check_fence(session, str(run_id))
                session.add(ArtifactModel(id=str(uuid4()), run_id=str(run_id), kind='issuer_domain_verification',
                    payload=json.loads(json.dumps(proof, default=str))))
            session.commit()

    def get_company(self, company_id: UUID | str) -> Company | None:
        with self.session_factory() as session:
            row = session.get(CompanyModel, str(company_id))
            return company_schema(row) if row else None

    def create_run(self, company: Company, as_of: date, mode: RunMode, idempotency_key: str | None = None, cold_start: bool = False) -> UUID:
        with self.session_factory() as session:
            if idempotency_key:
                existing = session.scalar(select(ResearchRunModel).where(ResearchRunModel.idempotency_key == idempotency_key))
                if existing:
                    if (existing.company_id, existing.as_of, existing.mode) != (str(company.id), as_of, mode.value):
                        raise ValueError("idempotency key already belongs to a different request")
                    if bool((existing.config_json or {}).get('cold_start', False)) != cold_start:
                        raise ValueError('idempotency key already belongs to a different cache policy')
                    return UUID(existing.id)
            run_id = uuid4()
            row = ResearchRunModel(
                id=str(run_id), company_id=str(company.id), as_of=as_of, mode=mode.value,
                status=RunStatus.QUEUED.value, stage=RunStatus.QUEUED.value,
                config_json={"schema_version": "1.0", "mode": mode.value, 'cold_start': cold_start},
                budget_json={"search_calls": 0, "fetch_documents": 0, "model_calls": 0, "ocr_pages": 0},
                progress_json={"sources_found": 0, "documents_parsed": 0, "calculations_completed": 0, "counterevidence_checks": 0},
                limitations=[], idempotency_key=idempotency_key,
            )
            session.add(row)
            session.flush()
            self._add_event(session, str(run_id), RunStatus.QUEUED.value, "run_queued", "Research run queued")
            session.commit()
            return run_id

    def _add_event(self, session, run_id: str, stage: str, event_type: str, summary: str, error_code: str | None = None) -> None:
        latest = session.scalar(select(RunEventModel).where(RunEventModel.run_id == run_id).order_by(RunEventModel.sequence.desc()))
        sequence = (latest.sequence + 1) if latest else 1
        session.add(RunEventModel(run_id=run_id, sequence=sequence, stage=stage, event_type=event_type, public_summary=summary, error_code=error_code))

    def append_event(self, run_id: UUID | str, stage: str, event_type: str, summary: str, error_code: str | None = None) -> None:
        with self.session_factory() as session:
            self._check_fence(session, str(run_id))
            self._add_event(session, str(run_id), stage, event_type, summary, error_code)
            session.commit()

    def update_run(self, run_id: UUID | str, *, status: RunStatus | None = None, stage: str | None = None,
                   outcome: ResearchOutcome | None = None, progress: dict[str, int] | None = None,
                   budget: dict[str, Any] | None = None, limitations: list[str] | None = None,
                   started: bool = False, ended: bool = False) -> None:
        with self.session_factory() as session:
            self._check_fence(session, str(run_id))
            row = session.get(ResearchRunModel, str(run_id))
            if not row:
                raise KeyError("run not found")
            if status:
                row.status = status.value
            if stage:
                row.stage = stage
            if outcome:
                row.outcome = outcome.value
            if progress is not None:
                row.progress_json = progress
            if budget is not None:
                row.budget_json = budget
            if limitations is not None:
                row.limitations = limitations
            if started and row.started_at is None:
                row.started_at = datetime.now(UTC)
            if ended:
                row.ended_at = datetime.now(UTC)
            session.commit()

    def request_cancel(self, run_id: UUID | str) -> str:
        with self.session_factory() as session:
            row = session.get(ResearchRunModel, str(run_id))
            if not row:
                raise KeyError("run not found")
            if row.status not in {RunStatus.COMPLETED.value, RunStatus.CANCELLED.value, RunStatus.FAILED.value}:
                row.cancel_requested = True
                if row.status == RunStatus.QUEUED.value:
                    row.status = RunStatus.CANCELLED.value
                    row.stage = RunStatus.CANCELLED.value
                    row.ended_at = datetime.now(UTC)
                else:
                    row.status = RunStatus.CANCEL_REQUESTED.value
                session.commit()
                if row.status == RunStatus.CANCELLED.value:
                    self.append_event(run_id, RunStatus.CANCELLED.value, "run_cancelled", "Queued run was cancelled before leasing")
            return row.status

    def queued_run_count(self) -> int:
        with self.session_factory() as session:
            return session.scalar(select(func.count()).select_from(ResearchRunModel).where(
                ResearchRunModel.status == RunStatus.QUEUED.value,
            ))

    def clear_queue(self) -> list[str]:
        """Cancel waiting work atomically; preserve active runs and durable artifacts."""
        with self.session_factory() as session:
            # A conditional write is the first statement, including on SQLite.
            # PostgreSQL rechecks queued status if a worker held the row lock.
            run_ids = list(session.scalars(update(ResearchRunModel).where(
                ResearchRunModel.status == RunStatus.QUEUED.value,
            ).values(
                status=RunStatus.CANCELLED.value, stage=RunStatus.CANCELLED.value,
                cancel_requested=True, ended_at=datetime.now(UTC),
                lease_owner=None, lease_expires_at=None,
                fencing_token=ResearchRunModel.fencing_token + 1,
            ).returning(ResearchRunModel.id)))
            for run_id in run_ids:
                self._add_event(session, run_id, RunStatus.CANCELLED.value, "run_cancelled",
                                "Queued run was cancelled by clearing the queue")
            session.commit()
            return run_ids

    def has_report(self, run_id: UUID | str) -> bool:
        with self.session_factory() as session:
            return bool(session.scalar(select(ResearchRunModel.id).where(ResearchRunModel.id == str(run_id), ResearchRunModel.report_json.is_not(None))))

    def resume(self, run_id: UUID | str) -> str:
        with self.session_factory() as session:
            row = session.get(ResearchRunModel, str(run_id))
            if not row:
                raise KeyError("run not found")
            if row.status == RunStatus.COMPLETED.value:
                return row.status
            if row.status not in {RunStatus.FAILED.value, RunStatus.CANCELLED.value, RunStatus.CANCEL_REQUESTED.value}:
                raise ValueError("only interrupted or failed runs can be resumed")
            row.status = RunStatus.QUEUED.value
            row.stage = RunStatus.QUEUED.value
            row.cancel_requested = False
            row.ended_at = None
            session.commit()
            self.append_event(run_id, RunStatus.QUEUED.value, "run_resumed", "Run queued from its last durable checkpoint")
            return row.status

    def is_cancelled(self, run_id: UUID | str) -> bool:
        with self.session_factory() as session:
            row = session.get(ResearchRunModel, str(run_id))
            return bool(row and row.cancel_requested)

    def checkpoint(self, run_id: UUID | str, stage: str, iteration: int, payload: Any) -> None:
        encoded = json.dumps(payload, sort_keys=True, default=str).encode()
        digest = hashlib.sha256(encoded).hexdigest()
        with self.session_factory() as session:
            self._check_fence(session, str(run_id))
            existing = session.scalar(select(StageCheckpointModel).where(StageCheckpointModel.run_id == str(run_id), StageCheckpointModel.stage == stage, StageCheckpointModel.iteration == iteration))
            if existing:
                return
            from .models import ArtifactModel
            artifact_id = str(uuid4())
            session.add(ArtifactModel(id=artifact_id, run_id=str(run_id), kind="checkpoint", payload=json.loads(encoded)))
            session.flush()
            session.add(StageCheckpointModel(run_id=str(run_id), stage=stage, iteration=iteration, input_hash=digest, output_artifact_ids=[artifact_id], schema_version="1.0"))
            session.commit()

    def load_checkpoint(self, run_id, stage, iteration=0):
        from .models import ArtifactModel
        with self.session_factory() as session:
            query = select(StageCheckpointModel).where(StageCheckpointModel.run_id == str(run_id), StageCheckpointModel.stage == stage)
            query = query.order_by(StageCheckpointModel.iteration.desc()) if iteration is None else query.where(StageCheckpointModel.iteration == iteration)
            row = session.scalar(query)
            if not row or not row.output_artifact_ids:
                return None
            artifact = session.get(ArtifactModel, row.output_artifact_ids[0])
            return artifact.payload if artifact else None

    def save_report(self, report: ResearchReport) -> None:
        encoded = report.model_dump_json().encode()
        digest = hashlib.sha256(encoded).hexdigest()
        with self.session_factory() as session:
            self._check_fence(session, str(report.run_id))
            row = session.get(ResearchRunModel, str(report.run_id))
            if not row:
                raise KeyError("run not found")
            if row.cancel_requested:
                raise RuntimeError("run cancelled before publication")
            row.report_json = json.loads(encoded)
            row.report_hash = digest
            row.status = RunStatus.COMPLETED.value
            row.stage = RunStatus.COMPLETED.value
            row.outcome = report.outcome.value
            row.ended_at = datetime.now(UTC)
            row.limitations = report.limitations
            row.lease_expires_at = None
            self._save_evidence(session, report)
            self._add_event(session, str(report.run_id), RunStatus.COMPLETED.value, "run_completed", f"Run completed with outcome {report.outcome.value}")
            session.commit()
        path = self.data_dir / "exports" / f"{report.run_id}.report.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)

    def get_report(self, run_id: UUID | str) -> ResearchReport | None:
        with self.session_factory() as session:
            row = session.get(ResearchRunModel, str(run_id))
            return ResearchReport.model_validate(row.report_json) if row and row.report_json else None

    def historical_reports(self, company_id: UUID, cutoff: date, limit: int = 3) -> list[ResearchReport]:
        """Prior completed live observations; never select synthetic replay work."""
        with self.session_factory() as session:
            rows = session.scalars(select(ResearchRunModel).where(
                ResearchRunModel.company_id == str(company_id), ResearchRunModel.as_of <= cutoff,
                ResearchRunModel.mode.in_(['live', 'deep']),
                ResearchRunModel.status == RunStatus.COMPLETED.value,
                ResearchRunModel.report_json.is_not(None),
            ).order_by(ResearchRunModel.ended_at.desc()).limit(limit)).all()
            reports = []
            for row in rows:
                try:
                    reports.append(ResearchReport.model_validate(row.report_json))
                except ValueError:
                    continue
            return reports

    def get_summary(self, run_id: UUID | str) -> RunSummary | None:
        with self.session_factory() as session:
            row = session.get(ResearchRunModel, str(run_id))
            if not row:
                return None
            company = session.get(CompanyModel, row.company_id)
            return RunSummary(
                id=UUID(row.id), company=company_schema(company), as_of=row.as_of, mode=row.mode,
                status=row.status, outcome=row.outcome, stage=row.stage, progress=row.progress_json or {},
                budget=row.budget_json or {}, limitations=row.limitations or [], started_at=row.started_at,
                ended_at=row.ended_at, cold_start=bool((row.config_json or {}).get('cold_start', False)),
            )

    def get_events(self, run_id: UUID | str, after: int = 0) -> list[RunEvent]:
        with self.session_factory() as session:
            rows = session.scalars(select(RunEventModel).where(RunEventModel.run_id == str(run_id), RunEventModel.sequence > after).order_by(RunEventModel.sequence)).all()
            return [RunEvent(sequence=r.sequence, timestamp=r.timestamp, stage=r.stage, event_type=r.event_type, public_summary=r.public_summary, artifact_ids=[UUID(x) for x in (r.artifact_ids or [])], duration_ms=r.duration_ms, error_code=r.error_code) for r in rows]

    def completed_stages(self, run_id: UUID | str) -> set[str]:
        with self.session_factory() as session:
            rows = session.scalars(select(StageCheckpointModel.stage).where(StageCheckpointModel.run_id == str(run_id))).all()
            return set(rows)

    def lease_next(self, owner: str, max_active_runs: int = 1) -> UUID | None:
        """PostgreSQL SKIP LOCKED lease with a monotonically increasing fencing token."""
        from datetime import timedelta

        from .models import WorkerHeartbeatModel
        with self.session_factory() as session:
            # Serialize the global admission check on PostgreSQL, then SKIP LOCKED
            # handles selection. SQLite is the single-worker development fallback.
            if session.bind.dialect.name == "postgresql":
                session.execute(select(func.pg_advisory_xact_lock(724193)))
            heartbeat = session.get(WorkerHeartbeatModel, owner)
            if not heartbeat:
                heartbeat = WorkerHeartbeatModel(owner=owner)
                session.add(heartbeat)
            heartbeat.timestamp = datetime.now(UTC)
            active = [s.value for s in RunStatus if s not in {RunStatus.COMPLETED, RunStatus.CANCELLED, RunStatus.FAILED, RunStatus.QUEUED}]
            busy = session.scalar(select(func.count()).select_from(ResearchRunModel).where(ResearchRunModel.status.in_(active), ResearchRunModel.lease_expires_at > datetime.now(UTC)))
            if busy >= max_active_runs:
                session.commit()
                return None
            row = session.scalar(select(ResearchRunModel).where(or_(ResearchRunModel.status == RunStatus.QUEUED.value, (ResearchRunModel.status.in_(active) & (ResearchRunModel.lease_expires_at < datetime.now(UTC))))).order_by(ResearchRunModel.created_at).with_for_update(skip_locked=True))
            if not row:
                session.commit()
                return None
            run_id, token = row.id, row.fencing_token + 1
            # SQLite ignores FOR UPDATE. Compare-and-set prevents a clear-queue
            # write between selection and leasing from resurrecting cancelled work.
            claimed = session.scalar(update(ResearchRunModel).where(
                ResearchRunModel.id == run_id, ResearchRunModel.status == row.status,
                ResearchRunModel.fencing_token == row.fencing_token,
            ).values(
                lease_owner=owner, lease_expires_at=datetime.now(UTC) + timedelta(seconds=60),
                fencing_token=token, status=RunStatus.RESOLVING.value,
                stage=RunStatus.RESOLVING.value,
            ).returning(ResearchRunModel.id).execution_options(synchronize_session=False))
            session.commit()
            if not claimed:
                return None
            self.lease_tokens[run_id] = (owner, token)
            self.append_event(run_id, RunStatus.RESOLVING.value, "stage_started", "Worker leased the run")
            return UUID(run_id)

    def _check_fence(self, session, run_id: str):
        if run_id not in self.lease_tokens:
            return
        owner, token = self.lease_tokens[run_id]
        row = session.scalar(select(ResearchRunModel).where(ResearchRunModel.id == run_id).with_for_update())
        expiry = row.lease_expires_at.replace(tzinfo=UTC) if row.lease_expires_at and row.lease_expires_at.tzinfo is None else row.lease_expires_at
        if row.lease_owner != owner or row.fencing_token != token or (expiry and expiry < datetime.now(UTC)):
            raise RuntimeError("worker lost its fenced lease")

    def heartbeat(self, run_id):
        from datetime import timedelta

        from .models import WorkerHeartbeatModel
        if str(run_id) not in self.lease_tokens:
            return
        owner, token = self.lease_tokens[str(run_id)]
        with self.session_factory() as session:
            self._check_fence(session, str(run_id))
            row = session.get(ResearchRunModel, str(run_id))
            row.lease_expires_at = datetime.now(UTC) + timedelta(seconds=60)
            worker = session.get(WorkerHeartbeatModel, owner)
            if worker:
                worker.timestamp = datetime.now(UTC)
            session.commit()

    def record_provider_call(
        self,
        run_id: UUID | str,
        *,
        stage: str,
        request_hash: str,
        provider: str,
        model: str | None,
        attempt: int,
        input_tokens: int = 0,
        output_tokens: int = 0,
        search_credits: int = 0,
        status: str = "ok",
        cost_status: str = "unknown",
        latency_ms: int | None = None,
        estimated_cost: float | None = None,
        result_kind: str | None = None,
        result_payload: Any = None,
    ) -> None:
        from .models import ProviderCallModel

        with self.session_factory() as session:
            self._check_fence(session, str(run_id))
            existing = session.scalar(select(ProviderCallModel).where(ProviderCallModel.run_id == str(run_id), ProviderCallModel.request_hash == request_hash, ProviderCallModel.attempt == attempt))
            if existing:
                return
            session.add(ProviderCallModel(
                run_id=str(run_id), stage=stage, request_hash=request_hash, provider=provider,
                model=model, attempt=attempt, input_tokens=input_tokens,
                output_tokens=output_tokens, search_credits=search_credits,
                status=status, cost_status=cost_status, latency_ms=latency_ms, estimated_cost=estimated_cost,
            ))
            if result_kind:
                from .models import ArtifactModel
                session.add(ArtifactModel(id=str(uuid4()), run_id=str(run_id), kind=result_kind, payload=json.loads(json.dumps(result_payload, default=str))))
            session.commit()

    def provider_calls(self, run_id: UUID | str) -> list[dict[str, Any]]:
        from .models import ProviderCallModel

        with self.session_factory() as session:
            rows = session.scalars(select(ProviderCallModel).where(ProviderCallModel.run_id == str(run_id))).all()
            return [{
                "provider": row.provider, "model": row.model, "stage": row.stage,
                "status": row.status, "input_tokens": row.input_tokens,
                "output_tokens": row.output_tokens, "search_credits": row.search_credits,
                "estimated_cost_usd": str(row.estimated_cost) if row.estimated_cost is not None else None,
                "cost_status": row.cost_status,
            } for row in rows]

    def artifact(self, run_id, kind, payload, artifact_id=None):
        from .models import ArtifactModel
        with self.session_factory() as session:
            self._check_fence(session, str(run_id))
            identifier = str(artifact_id or uuid4())
            if not session.get(ArtifactModel, identifier):
                session.add(ArtifactModel(id=identifier, run_id=str(run_id), kind=kind, payload=json.loads(json.dumps(payload, default=str))))
                session.commit()
            return identifier

    def artifacts(self, run_id, kind=None):
        from .models import ArtifactModel
        with self.session_factory() as session:
            query = select(ArtifactModel).where(ArtifactModel.run_id == str(run_id))
            if kind:
                query = query.where(ArtifactModel.kind == kind)
            return [{"id": a.id, "kind": a.kind, "payload": a.payload} for a in session.scalars(query).all()]

    def _save_evidence(self, session, report):
        from .models import (
            CalculationInputModel,
            CalculationModel,
            ClaimCalculationModel,
            ClaimModel,
            EvidenceLinkModel,
            FactModel,
            PassageModel,
        )
        document_ids = {}
        for document in report.documents:
            data = document.model_dump(mode="python")
            data["id"] = str(document.id)
            data["canonical_url"] = str(document.canonical_url)
            data["final_url"] = str(document.final_url)
            existing = session.scalar(select(SourceDocumentModel).where(SourceDocumentModel.content_hash == document.content_hash))
            if existing:
                document_ids[str(document.id)] = existing.id
            else:
                document_ids[str(document.id)] = data["id"]
            if not existing and not session.get(SourceDocumentModel, data["id"]):
                session.add(SourceDocumentModel(**data))
        session.flush()
        pending_passages = {}
        for passage in report.passages:
            data = passage.model_dump(mode="python")
            data.update(id=str(passage.id), document_id=document_ids.get(str(passage.document_id), str(passage.document_id)))
            previous = pending_passages.get(data['id'])
            if previous is not None:
                if previous != data:
                    raise ValueError('Conflicting source passages share an identifier; report was not saved')
                continue
            # Autoflush is disabled. session.get cannot see an earlier pending
            # INSERT with this ID until flush, so track repeated spans explicitly.
            pending_passages[data['id']] = data
            if not session.get(PassageModel, data["id"]):
                session.add(PassageModel(**data))
        session.flush()
        pending_facts = {}
        for fact in report.facts:
            data = fact.model_dump(mode="python")
            data.pop("extraction_confidence", None)
            for key in ("id", "entity_id", "passage_id", "restates_fact_id"):
                if data[key] is not None:
                    data[key] = str(data[key])
            previous = pending_facts.get(data['id'])
            if previous is not None:
                if previous != data:
                    raise ValueError('Conflicting source facts share an identifier; report was not saved')
                continue
            pending_facts[data['id']] = data
            if not session.get(FactModel, data["id"]):
                session.add(FactModel(**data))
        session.flush()
        for calculation in report.calculations:
            data = calculation.model_dump(mode="python")
            data.update(id=str(calculation.id), run_id=str(report.run_id), input_fact_ids=[str(i) for i in calculation.input_fact_ids], parameters=json.loads(json.dumps(calculation.parameters, default=str)))
            if not session.get(CalculationModel, data["id"]):
                session.add(CalculationModel(**data))
                session.flush()
                for position, fact_id in enumerate(calculation.input_fact_ids):
                    session.add(CalculationInputModel(calculation_id=data["id"], fact_id=str(fact_id), position=position))
        session.flush()
        for claim in report.claims:
            if session.get(ClaimModel, str(claim.id)):
                continue
            session.add(ClaimModel(id=str(claim.id), run_id=str(report.run_id), text=claim.text, kind=claim.kind, material=claim.material, verification_status=claim.verification_status, verification_reasons=claim.verification_reasons))
            session.flush()
            for link in claim.evidence_links:
                is_fact = link.passage_or_fact_id in {f.id for f in report.facts}
                session.add(EvidenceLinkModel(claim_id=str(claim.id), fact_id=str(link.passage_or_fact_id) if is_fact else None, passage_id=None if is_fact else str(link.passage_or_fact_id), relation=link.relation, reason=link.reason, entailment_status=link.entailment_status))
            for calc_id in claim.calculation_ids:
                session.add(ClaimCalculationModel(claim_id=str(claim.id), calculation_id=str(calc_id)))

    def find_claim(self, run_id: UUID | str, claim_id: UUID | str) -> dict[str, Any] | None:
        report = self.get_report(run_id)
        if not report:
            return None
        claim = next((c for c in report.claims if str(c.id) == str(claim_id)), None)
        if not claim:
            return None
        links = []
        for link in claim.evidence_links:
            passage = next((p for p in report.passages if p.id == link.passage_or_fact_id), None)
            fact = next((f for f in report.facts if f.id == link.passage_or_fact_id), None)
            if fact:
                passage = next((p for p in report.passages if p.id == fact.passage_id), None)
            document = next((d for d in report.documents if passage and d.id == passage.document_id), None)
            links.append({"link": link.model_dump(mode="json"), "passage": passage.model_dump(mode="json") if passage else None, "fact": fact.model_dump(mode="json") if fact else None, "document": document.model_dump(mode="json") if document else None})
        return {"claim": claim.model_dump(mode="json"), "evidence": links, "calculations": [c.model_dump(mode="json") for c in report.calculations if c.id in claim.calculation_ids]}


def company_schema(row: CompanyModel | None) -> Company:
    if row is None:
        raise KeyError("company not found")
    return Company(
        id=UUID(row.id), legal_name=row.legal_name, symbols=row.symbols or [], isin=row.isin,
        exchange=row.exchange, aliases=row.aliases or [], verified_ir_domains=row.verified_ir_domains or [],
        business_profiles=row.business_profiles or [], identity_source_ids=[UUID(x) for x in row.identity_source_ids or []],
    )


def infer_profile(industry: str) -> str | None:
    if "insurance" in industry and "life" in industry:
        return "life_insurer"
    if "insurance" in industry:
        return "general_insurer"
    if "exchange" in industry or "market infrastructure" in industry:
        return "exchange"
    if "asset management" in industry or "mutual fund" in industry or "amc" in industry:
        return "asset_manager"
    if "bank" in industry:
        return "bank"
    if "finserv" in industry or "financial services" in industry or "holdings" in industry:
        return "diversified"
    if "nbfc" in industry or "finance" in industry or "lending" in industry or "housing" in industry:
        return "nbfc"
    if "securities" in industry or "capital markets" in industry or "investments" in industry:
        return "diversified"
    return None
