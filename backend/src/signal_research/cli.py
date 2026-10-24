from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import typer

from signal_research.db.models import Base
from signal_research.db.repositories import Store
from signal_research.db.session import build_engine, session_factory
from signal_research.domain.enums import RunMode
from signal_research.research.entity_resolver import resolve
from signal_research.research.universe import refresh_universe
from signal_research.settings import get_settings
from signal_research.worker.machine import ResearchMachine

app = typer.Typer(help="Auditable Track A financial research")
universe_app = typer.Typer(help="Manage the runtime constituent universe")
app.add_typer(universe_app, name="universe")


def context():
    settings = get_settings()
    engine = build_engine(settings.database_url)
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(engine)
    store = Store(session_factory(engine), settings.data_dir)
    store.bootstrap()
    if settings.pipeline_mode == 'precomputed':
        from signal_research.precomputed.catalog import bootstrap_catalog
        bootstrap_catalog(store, settings)
    return settings, store


@universe_app.command("refresh")
def universe_refresh():
    try:
        payload = refresh_universe()
        _, store = context()
        added = store.save_universe_snapshot(payload)
        typer.echo(json.dumps({"fetched_at": payload["fetched_at"], "content_hash": payload["content_hash"], "financial_constituents": payload["financial_constituents"], "new_identities": added}, indent=2))
    except Exception as exc:
        typer.echo(f"Universe refresh failed: {exc}", err=True)
        raise typer.Exit(1)


@app.command()
def research(company: str = typer.Option(..., help="Legal name or exchange symbol"), as_of: str | None = typer.Option(None, help="YYYY-MM-DD cutoff"), mode: RunMode = typer.Option(RunMode.LIVE)):
    """Start and process one run using the same worker service as the API."""
    settings, store = context()
    resolution = resolve(store, company, refresh=settings.pipeline_mode != 'precomputed')
    if not resolution.company:
        typer.echo(resolution.reason or "company could not be resolved", err=True)
        raise typer.Exit(2)
    try:
        cutoff = date.fromisoformat(as_of) if as_of else datetime.now(ZoneInfo("Asia/Kolkata")).date()
    except ValueError:
        typer.echo("as-of must be YYYY-MM-DD", err=True)
        raise typer.Exit(2)
    if cutoff > datetime.now(ZoneInfo("Asia/Kolkata")).date():
        typer.echo("cutoff cannot be in the future", err=True)
        raise typer.Exit(2)
    if (mode == RunMode.REPLAY) != ("SYNTHBANK" in resolution.company.symbols):
        typer.echo("Replay requires SYNTHBANK; live/deep requires a real listed company", err=True)
        raise typer.Exit(2)
    if mode != RunMode.REPLAY and settings.pipeline_mode == 'precomputed':
        from signal_research.precomputed.catalog import PrecomputedUnavailable, load_report
        try:
            load_report(settings, resolution.company, cutoff)
        except PrecomputedUnavailable as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(2) from exc
    elif mode != RunMode.REPLAY:
        from signal_research.research.readiness import live_readiness
        readiness = live_readiness(settings)
        if not readiness["ready"]:
            typer.echo("Live configuration incomplete: " + " ".join(readiness["issues"]), err=True)
            raise typer.Exit(2)
    run_id = store.create_run(resolution.company, cutoff, mode, f"cli-{uuid4()}",
                              pipeline_mode=settings.pipeline_mode,
                              replay_duration_seconds=settings.replay_duration_seconds)
    owner = f"cli-{uuid4()}"
    leased = store.lease_next(owner, settings.max_active_runs)
    if leased != run_id:
        typer.echo(f"run {run_id} was queued; start the worker to process it")
    else:
        ResearchMachine(store, settings).process(run_id)
    typer.echo(json.dumps({"run_id": str(run_id), "status_url": f"/api/v1/runs/{run_id}", "status": store.get_summary(run_id).status.value}, indent=2))


@app.command()
def status(run_id: str):
    _, store = context()
    summary = store.get_summary(run_id)
    if not summary:
        typer.echo("run not found", err=True)
        raise typer.Exit(1)
    typer.echo(summary.model_dump_json(indent=2))
    events = store.get_events(run_id)
    for event in events[-5:]:
        typer.echo(f"[{event.sequence}] {event.stage}: {event.public_summary}")


@app.command()
def cancel(run_id: str):
    _, store = context()
    try:
        typer.echo(store.request_cancel(run_id))
    except KeyError:
        typer.echo("run not found", err=True)
        raise typer.Exit(1)


@app.command()
def resume(run_id: str):
    _, store = context()
    try:
        typer.echo(store.resume(run_id))
    except (KeyError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)


@app.command()
def export(run_id: str, format: str = typer.Option("json"), out: Path = typer.Option(...)):
    _, store = context()
    report = store.get_report(run_id)
    if not report:
        typer.echo("report is not ready", err=True)
        raise typer.Exit(1)
    out.parent.mkdir(parents=True, exist_ok=True)
    if format == "json":
        out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    elif format == "csv":
        lines = ["id,metric_key,value_raw,value_decimal,unit,period_end,scope,status"]
        for fact in report.facts:
            values = [str(fact.id), fact.metric_key, fact.value_raw or "", str(fact.value_decimal or ""), fact.unit_normalized or "", str(fact.period_end or ""), str(fact.scope), str(fact.status)]
            lines.append(",".join('"' + value.replace('"', '""') + '"' for value in values))
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        typer.echo("format must be json or csv", err=True)
        raise typer.Exit(2)
    typer.echo(str(out))


@app.command()
def evaluate(suite: Path = typer.Option(Path("tests/evaluation/cases.yaml")), offline: bool = typer.Option(False)):
    if not offline:
        typer.echo("evaluation requires --offline or an explicitly configured live suite", err=True)
        raise typer.Exit(2)
    import yaml
    try:
        cases = yaml.safe_load(suite.read_text(encoding="utf-8"))["cases"]
        if not isinstance(cases, list) or not cases:
            raise ValueError("suite requires a nonempty cases list")
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as exc:
        typer.echo(f"Invalid evaluation suite: {exc}", err=True)
        raise typer.Exit(2)
    settings, store = context()
    results = []
    for case in cases:
        if case.get("mode") != "replay" or not case.get("synthetic"):
            typer.echo("Offline suites may contain only explicitly synthetic replay cases", err=True)
            raise typer.Exit(2)
        resolution = resolve(store, case["company"])
        if not resolution.company or "SYNTHBANK" not in resolution.company.symbols:
            raise typer.Exit(2)
        cutoff = date.fromisoformat(case.get("as_of", "2026-10-08"))
        run_id = store.create_run(resolution.company, cutoff, RunMode.REPLAY, f"eval-{uuid4()}")
        leased = store.lease_next(f"eval-{uuid4()}", settings.max_active_runs)
        if leased != run_id:
            typer.echo("Evaluation is blocked by another queued/active run; use an isolated evaluation database", err=True)
            raise typer.Exit(2)
        ResearchMachine(store, settings).process(run_id)
        report = store.get_report(run_id)
        actual = {c.formula_id for c in report.calculations} if report else set()
        passed = bool(report and report.outcome.value == case["expected_outcome"] and set(case.get("expected_calculations", [])) <= actual)
        results.append({"case": case["id"], "run_id": str(run_id), "outcome": report.outcome.value if report else None, "passed": passed})
    typer.echo(json.dumps({"suite": str(suite), "offline": True, "results": results, "passed": all(r["passed"] for r in results)}, indent=2))
    if not all(r["passed"] for r in results):
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
