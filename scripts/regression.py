"""Unattended real-provider cold regression; no result or company-specific tuning."""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from signal_research.db.models import Base
from signal_research.db.repositories import Store
from signal_research.db.session import build_engine, session_factory
from signal_research.domain.enums import RunMode
from signal_research.research.verifier import verify_report
from signal_research.settings import Settings
from signal_research.worker.machine import ResearchMachine

DEFAULT_COMPANIES = ['HDFCBANK', 'ICICIBANK', 'SBIN', 'KOTAKBANK', 'AXISBANK', 'BAJFINANCE', 'BAJAJFINSV', 'SBILIFE']


def run_one(symbol, seconds=300):
    started = time.monotonic()
    output = Path('data/exports/cold-regression') / f'{symbol}-{time.time_ns()}'
    output.mkdir(parents=True)
    settings = Settings(cold_start=True, max_run_seconds=seconds, data_dir=output,
                        database_url=f'sqlite:///{output / "validation.db"}')
    settings.ensure_directories()
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(engine)
    store = Store(session_factory(engine), output)
    store.bootstrap()
    company = next(c for c in store.search_companies(symbol) if symbol in c.symbols)
    run_id = store.create_run(company, date.today(), RunMode.LIVE)
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
        'failures': report.limitations if report else summary.limitations,
        'peers_verified': report.generation_metadata.get('peer_benchmark', {}).get('status') == 'verified' if report else False,
        'cache_reused': 0, 'output': str(output)}
    (output / 'summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    engine.dispose()
    return result


def write_report(results, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ['# Cold-start regression', '', 'Real-provider, empty-database runs. Each company uses the same pipeline and configuration. No manual intervention or historical facts reused.', '',
        '| Company | Seconds | Verified facts | Strength | Peers verified | Outcome |', '| --- | ---: | ---: | --- | --- | --- |']
    for r in results:
        lines.append(f'| {r["symbol"]} | {r["seconds"]} | {r["facts"]} | {r["strength"]} | {r.get("peers_verified", False)} | {r["outcome"]} |')
    for r in results:
        lines.extend(['', f'## {r["symbol"]}', '', r.get('headline') or 'No headline passed publication gates.', '',
                      f'Runtime target: {"met" if r["seconds"] <= 300 else "exceeded"}. Cache facts reused: 0.', '',
                      *['- ' + str(f).replace('\n', ' ') for f in r.get('failures', [])]])
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--companies', nargs='+', default=DEFAULT_COMPANIES)
    parser.add_argument('--seconds', type=int, default=300)
    parser.add_argument('--workers', type=int, choices=(1, 2, 3), default=3)
    args = parser.parse_args()
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_one, s, args.seconds): s for s in args.companies}
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception as exc:
                result = {'symbol': futures[future], 'seconds': 0, 'facts': 0, 'strength': 'Not established', 'outcome': 'failed', 'failures': [type(exc).__name__ + ': ' + str(exc)]}
            results.append(result)
            write_report(results, Path('reports/regression.md'))
            print(json.dumps({k: result[k] for k in ('symbol', 'seconds', 'facts', 'strength', 'outcome')}), flush=True)


if __name__ == '__main__':
    main()
