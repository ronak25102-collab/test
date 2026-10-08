from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from uuid import uuid4

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
    Base.metadata.create_all(engine)
    store = Store(session_factory(engine), settings.data_dir)
    store.bootstrap()
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
    resolution = resolve(store, company)
    if not resolution.company:
        typer.echo(resolution.reason or "company could not be resolved", err=True)
        raise typer.Exit(2)
    try:
        cutoff = date.fromisoformat(as_of) if as_of else date.today()
    except ValueError:
        typer.echo("as-of must be YYYY-MM-DD", err=True)
        raise typer.Exit(2)
    if cutoff > date.today():
        typer.echo("cutoff cannot be in the future", err=True)
        raise typer.Exit(2)
    run_id = store.create_run(resolution.company, cutoff, mode, f"cli-{uuid4()}")
    owner = f"cli-{uuid4()}"
    leased = store.lease_next(owner)
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
    settings, store = context()
    resolution = resolve(store, "SYNTHBANK")
    run_id = store.create_run(resolution.company, date(2026, 10, 8), RunMode.REPLAY, f"eval-{uuid4()}")
    owner = f"eval-{uuid4()}"
    store.lease_next(owner)
    ResearchMachine(store, settings).process(run_id)
    report = store.get_report(run_id)
    typer.echo(json.dumps({"suite": str(suite), "offline": True, "run_id": str(run_id), "outcome": report.outcome.value if report else None, "discoveries": len(report.discoveries) if report else 0}, indent=2))
