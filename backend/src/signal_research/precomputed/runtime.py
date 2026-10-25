"""Resume-safe playback of a verified report, with no research/provider work."""
import json
import time
from datetime import UTC, datetime
from uuid import UUID, uuid5

from signal_research.domain.enums import RunStatus
from signal_research.domain.schemas import ResearchReport
from signal_research.report_memory import report_memory
from signal_research.research.integrity import report_digest
from signal_research.research.verifier import verify_report

from .catalog import load_report
from .guard import offline_playback

STAGE_TEXT = {
    "resolving": "Loading the selected company's stored identity and evidence snapshot",
    "planning": "Loading the recorded research scope and coverage checklist",
    "discovering": "Loading the stored source inventory and provenance",
    "fetching": "Loading archived document records; no sources are fetched during playback",
    "extracting": "Loading stored passages and their page, row and column bindings",
    "normalizing": "Checking stored verified figures and their units, periods and scopes",
    "hypothesizing": "Loading the reviewed discovery and its supporting relationships",
    "investigating": "Reproducing registered calculations from stored verified inputs",
    "challenging": "Loading the recorded counterargument and falsification checks",
    "verifying": "Checking stored citations, arithmetic and publication gates",
    "composing": "Preparing the stored reviewed report and its evidence navigation",
}
DEFAULT_STAGES = [
    (0, "resolving"), (.02, "planning"), (.05, "discovering"), (.14, "fetching"),
    (.28, "extracting"), (.52, "normalizing"), (.65, "hypothesizing"),
    (.73, "investigating"), (.82, "challenging"), (.92, "verifying"), (.98, "composing"),
]


def now():
    return datetime.now(UTC)


def aware(timestamp):
    return timestamp.replace(tzinfo=UTC) if timestamp.tzinfo is None else timestamp


def event_schedule(settings, symbol):
    """Keep reference stage proportions, replacing claims of newly performed research."""
    candidates = [settings.precomputed_dir / f"{symbol}.events.json",
                  settings.precomputed_dir / "references" / "d45ea5a6.events.json"]
    for path in candidates:
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        events = payload.get("items", []) if isinstance(payload, dict) else payload
        timed = [(datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")), e["stage"])
                 for e in events if e.get("timestamp")]
        if len(timed) < 2:
            continue
        start, end = min(t for t, _ in timed), max(t for t, _ in timed)
        duration = (end - start).total_seconds()
        if duration <= 0:
            continue
        return [(min(.99, max(0, (t - start).total_seconds() / duration)), stage)
                for t, stage in timed if stage in STAGE_TEXT]
    return DEFAULT_STAGES


def remap_report(fixture, run_id, cutoff, elapsed, stage_durations):
    """Rebind reviewed content to a new run, preserving its original review receipt."""
    verify_report(fixture)
    payload = fixture.model_dump(mode="json")
    mapping = {str(fixture.run_id): str(run_id)}

    def collect(value):
        if isinstance(value, dict):
            identifier = value.get("id")
            if identifier and "legal_name" not in value:
                try:
                    UUID(identifier)
                except (ValueError, TypeError):
                    pass
                else:
                    mapping[identifier] = str(uuid5(UUID(str(run_id)), identifier))
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(payload)

    def replace(value):
        if isinstance(value, dict):
            for key in list(value):
                child = replace(value[key])
                replacement = mapping.get(key, key)
                if replacement != key:
                    del value[key]
                value[replacement] = child
            return value
        if isinstance(value, list):
            for index, child in enumerate(value):
                value[index] = replace(child)
            return value
        if isinstance(value, str):
            if value.startswith("peer:") and value[5:] in mapping:
                return "peer:" + mapping[value[5:]]
            return mapping.get(value, value)
        return value

    payload = replace(payload)
    for key in ("reference_review", "editorial_review", "historical_cache"):
        if key in fixture.generation_metadata:
            # Archived review/cache receipts refer to their original run and IDs.
            payload["generation_metadata"][key] = fixture.generation_metadata[key]
    payload["cutoff"] = cutoff.isoformat()
    metadata = payload["generation_metadata"]
    metadata["precomputed_provenance"] = {
        "source_run_id": str(fixture.run_id),
        "source_verification_digest": fixture.generation_metadata.get("verification_digest"),
        "review": "Existing reviewed content replayed; no new model review performed",
        "generated_at": fixture.generation_metadata.get("generated_at"),
        "data_as_of": str(fixture.cutoff),
        "sources": [{"url": str(d.canonical_url), "retrieved_at": d.retrieved_at.isoformat(),
                     "sha256": d.content_hash} for d in fixture.documents],
    }
    metadata.update({"mode": "precomputed", "data_as_of": str(fixture.cutoff),
                     "configured_provider": "none", "configured_model_id": None,
                     "provider": "none", "model_id": None, "models_used": [],
                     "model_usage": {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                                     "estimated_cost_usd": 0, "note": "No model used by this replay."},
                     "provider_usage": {"search_calls": 0, "fetch_calls": 0, "model_calls": 0},
                     "input_tokens": 0, "output_tokens": 0, "model_calls": 0,
                     "search_calls": 0, "fetch_documents": 0,
                     "cache_usage": {"cold_start": False, "reused": len(fixture.facts), "fresh": 0},
                     "stage_durations": stage_durations,
                     "stage_durations_basis": "Scheduled playback seconds, not live research time",
                     "elapsed_seconds": elapsed, "cutoff": cutoff.isoformat()})
    payload["source_coverage"]["mode"] = "precomputed"
    report = ResearchReport.model_validate(payload)
    # This checksum records an ID/metadata rebinding of already verified content,
    # never an invented semantic-review receipt. The original digest remains above.
    report.generation_metadata["verification_digest"] = report_digest(report)
    return verify_report(report)


def process_precomputed(machine, run_id):
    with offline_playback():
        return _process_precomputed(machine, run_id)


def _process_precomputed(machine, run_id):
    store, settings = machine.store, machine.settings
    summary = store.get_summary(run_id)
    with report_memory():
        fixture = load_report(settings, summary.company, summary.as_of)
        counts = {"documents": len(fixture.documents), "facts": len(fixture.facts),
                  "calculations": len(fixture.calculations),
                  "challenges": len(fixture.generation_metadata.get("challenge_reviews", []))}
        # Concurrent playbacks keep only small counters during their timer.
        del fixture
    saved = summary.budget
    configured = store.run_configuration(run_id).get('replay_duration_seconds')
    duration = saved.get("replay_duration_seconds", configured if configured is not None else settings.replay_duration_seconds)
    budget = {"mode": "precomputed", "replay_duration_seconds": duration,
              "search_calls": 0, "fetch_documents": 0, "model_calls": 0,
              "ocr_pages": 0, "input_tokens": 0, "output_tokens": 0,
              "reserved_cost_usd": 0, "cost_accounting": "No outbound calls during playback"}
    store.update_run(run_id, budget=budget)
    started = aware(summary.started_at)
    schedule = event_schedule(settings, summary.company.symbols[0])
    emitted = {e.event_type for e in store.get_events(run_id)}
    stage_durations = {}
    for index, (fraction, stage) in enumerate(schedule):
        next_fraction = schedule[index + 1][0] if index + 1 < len(schedule) else 1
        stage_durations[stage] = stage_durations.get(stage, 0) + max(0, next_fraction - fraction) * duration
    last_progress = None
    while True:
        if machine.lease_error:
            raise machine.lease_error
        if machine._cancelled(run_id):
            return
        elapsed = max(0, (now() - started).total_seconds())
        for index, (fraction, stage) in enumerate(schedule):
            marker = f"precomputed_step_{index}"
            if elapsed < fraction * duration or marker in emitted:
                continue
            machine._set_stage(run_id, RunStatus(stage), marker, STAGE_TEXT[stage])
            emitted.add(marker)
        progress_fraction = min(1, elapsed / duration) if duration else 1
        progress = {
            "sources_found": min(counts["documents"], int(counts["documents"] * min(1, progress_fraction / .25))),
            "documents_parsed": min(counts["documents"], int(counts["documents"] * min(1, progress_fraction / .52))),
            "facts_verified": int(counts["facts"] * min(1, progress_fraction / .65)),
            "facts_reused": int(counts["facts"] * min(1, progress_fraction / .65)),
            "facts_fresh": 0,
            "calculations_completed": int(counts["calculations"] * min(1, progress_fraction / .82)),
            "counterevidence_checks": int(counts["challenges"] * min(1, progress_fraction / .92)),
        }
        if progress != last_progress:
            store.update_run(run_id, progress=progress)
            last_progress = progress
        if elapsed >= duration:
            break
        time.sleep(min(.5, duration - elapsed))
    if machine._cancelled(run_id):
        return
    # Re-load and publish one report at a time. Timers overlap without holding
    # multiple large evidence graphs in memory or racing shared source inserts.
    with report_memory():
        if machine._cancelled(run_id):
            return
        fixture = load_report(settings, summary.company, summary.as_of)
        report = remap_report(fixture, run_id, summary.as_of, elapsed, stage_durations)
        del fixture
        if machine._cancelled(run_id):
            return
        store.save_report(report)
        del report
