"""Unattended real-provider cold regression; no result or company-specific tuning."""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from signal_research.db.models import Base
from signal_research.db.repositories import UNIVERSE_SEED, Store
from signal_research.db.session import build_engine, session_factory
from signal_research.domain.enums import RunMode
from signal_research.research.verifier import verify_report
from signal_research.settings import Settings
from signal_research.worker.machine import ResearchMachine

DEFAULT_COMPANIES = [symbol for _, symbol, _ in UNIVERSE_SEED if symbol != 'SYNTHBANK']


def run_one(symbol, seconds=600, artifact_root=Path('data/exports/cold-regression')):
    started = time.monotonic()
    output = artifact_root / f'{symbol}-{time.time_ns()}'
    output.mkdir(parents=True)
    settings = Settings(cold_start=True, max_run_seconds=seconds, demo_target_seconds=min(seconds, 600), data_dir=output,
                        database_url=f'sqlite:///{output / "validation.db"}')
    settings.ensure_directories()
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(engine)
    store = Store(session_factory(engine), output)
    store.bootstrap()
    from signal_research.research.entity_resolver import resolve
    company = resolve(store, symbol, refresh=True).company
    if company is None:
        raise ValueError('Exchange identity could not be resolved')
    run_id = store.create_run(company, datetime.now(ZoneInfo('Asia/Kolkata')).date(), RunMode.LIVE)
    assert store.lease_next('cold-regression') == run_id
    ResearchMachine(store, settings).process(run_id)
    report, summary = store.get_report(run_id), store.get_summary(run_id)
    if report:
        verify_report(report)
        (output / 'report.json').write_text(report.model_dump_json(indent=2), encoding='utf-8')
    result = {'symbol': symbol, 'run_id': str(run_id), 'seconds': round(time.monotonic() - started, 1),
        'facts': len(report.facts) if report else 0, 'strength': report.discoveries[0].evidence_strength.value if report and report.discoveries else 'Not established',
        'headline': report.discoveries[0].discovery_sentence if report and report.discoveries else '',
        'outcome': report.outcome.value if report else summary.status.value,
        'failures': [*report.limitations, *(report.abstention.next_evidence_needed if report.abstention else [])] if report else summary.limitations,
        'peers_verified': report.generation_metadata.get('peer_benchmark', {}).get('status') == 'verified' if report else False,
        'cache_reused': report.generation_metadata.get('cache_usage', {}).get('reused', 0) if report else 0,
        'budget_seconds': min(seconds, 600), 'output': str(output)}
    result['routing'] = 'nvidia planning; configured final review' if settings.nvidia_planning else 'configured provider with authorized fallbacks'
    result['models'] = {'planning': settings.nvidia_model_research if settings.nvidia_planning else settings.model_for_role('research'),
                        'extraction': settings.nvidia_model_extract if settings.nvidia_planning else settings.model_for_role('extract'),
                        'final_review': settings.model_for_role('research')}
    (output / 'summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    engine.dispose()
    return result


def write_report(results, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ['# Cold-start regression', '', 'Real-provider, empty-database runs. Each company uses the same pipeline and configuration. No manual intervention or historical facts reused.', '',
        f'Published discoveries: {sum(r["strength"] != "Not established" for r in results)} / {len(results)}. Meeting the time limit alone does not pass discovery acceptance.', '',
        '| Company | Seconds | Verified facts | Strength | Peers verified | Outcome |', '| --- | ---: | ---: | --- | --- | --- |']
    for r in results:
        lines.append(f'| {r["symbol"]} | {r["seconds"]} | {r["facts"]} | {r["strength"]} | {r.get("peers_verified", False)} | {r["outcome"]} |')
    for r in results:
        lines.extend(['', f'## {r["symbol"]}', '', r.get('headline') or 'No headline passed publication gates.', '',
                      'Routing: ' + r.get('routing', 'See recorded provider receipts.'), '',
                      f'Runtime target: {"met" if r["seconds"] <= r.get("budget_seconds", 300) + 1 else "exceeded"} ({r.get("budget_seconds", 300)} seconds). Cache facts reused: {r.get("cache_reused", 0)}.', '',
                      *['- ' + str(f).replace('\n', ' ') for f in r.get('failures', [])]])
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--companies', nargs='+', default=DEFAULT_COMPANIES)
    parser.add_argument('--seconds', type=int, default=600)
    parser.add_argument('--workers', type=int, choices=(1, 2, 3), default=2)
    parser.add_argument('--summarize', type=Path, help='Regenerate the Markdown from recorded run artifacts without provider requests.')
    parser.add_argument('--output', type=Path, default=Path('reports/regression.md'))
    parser.add_argument('--artifact-root', type=Path, default=Path('data/exports/cold-regression'))
    args = parser.parse_args()
    results = []
    if args.summarize:
        for path in args.summarize.glob('*/summary.json'):
            result = json.loads(path.read_text(encoding='utf-8'))
            report_path = path.parent / 'report.json'
            if report_path.exists():
                r = json.loads(report_path.read_text(encoding='utf-8'))
                result['failures'] = list(dict.fromkeys([*result['failures'], *(r.get('abstention') or {}).get('next_evidence_needed', [])]))
            results.append(result)
        write_report(sorted(results, key=lambda r: r['symbol']), args.output)
        return
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_one, s, args.seconds, args.artifact_root): s for s in args.companies}
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception as exc:
                result = {'symbol': futures[future], 'seconds': 0, 'facts': 0, 'strength': 'Not established', 'outcome': 'failed', 'failures': [type(exc).__name__ + ': ' + str(exc)]}
            results.append(result)
            write_report(results, args.output)
            print(json.dumps({k: result[k] for k in ('symbol', 'seconds', 'facts', 'strength', 'outcome')}), flush=True)


if __name__ == '__main__':
    main()
