"""Bounded, opt-in live validation. Uses configured credentials without printing them.

Run from the repository root: python scripts/validate_discovery.py HDFCBANK --seconds 480
Creates a separate validation database so it cannot interfere with the website queue.
"""
import argparse
import json
import time
from datetime import date
from pathlib import Path

from signal_research.db.models import Base
from signal_research.db.repositories import Store
from signal_research.db.session import build_engine, session_factory
from signal_research.domain.enums import RunMode
from signal_research.research.readiness import live_readiness
from signal_research.research.verifier import verify_report
from signal_research.settings import Settings
from signal_research.worker.machine import ResearchMachine

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('company')
parser.add_argument('--seconds', type=int, choices=range(120, 901), default=480)
parser.add_argument('--cutoff', type=date.fromisoformat, default=date.today())
parser.add_argument('--reuse-database', type=Path, help='Reuse a prior validation database to measure historical-source caching; current research is still live.')
args = parser.parse_args()
output = Path('data/exports/live-validation') / f'{args.company}-{time.time_ns()}'
output.mkdir(parents=True)
settings = Settings(max_run_seconds=args.seconds, max_search_calls=24, max_fetch_documents=24,
                    max_model_calls=36,
                    max_ocr_pages=8,
                    data_dir=output,
                    database_url=f'sqlite:///{args.reuse_database or output / "validation.db"}')
settings.ensure_directories()
ready = live_readiness(settings)
if not ready['ready']:
    raise SystemExit('Configuration incomplete: ' + ' '.join(ready['issues']))
engine = build_engine(settings.database_url)
Base.metadata.create_all(engine)
store = Store(session_factory(engine), output)
store.bootstrap()
companies = store.search_companies(args.company)
company = next((c for c in companies if args.company.upper() in c.symbols), None)
if company is None:
    raise SystemExit('Company must resolve unambiguously to an existing exchange symbol.')
run_id = store.create_run(company, args.cutoff, RunMode.LIVE)
assert store.lease_next('bounded-validation') == run_id
print(json.dumps({'run_id': str(run_id), 'company': company.legal_name,
                  'deadline_seconds': args.seconds, 'output': str(output)}), flush=True)
started = time.monotonic()
ResearchMachine(store, settings).process(run_id)
summary = store.get_summary(run_id)
report = store.get_report(run_id)
if report:
    verify_report(report)
    (output / 'report.json').write_text(report.model_dump_json(indent=2), encoding='utf-8')
result = {'run_id': str(run_id), 'company': company.legal_name, 'status': summary.status.value,
          'seconds': round(time.monotonic() - started, 1),
          'outcome': report.outcome.value if report else None,
          'facts': len(report.facts) if report else 0,
          'calculations': len(report.calculations) if report else 0,
          'discoveries': len(report.discoveries) if report else 0,
          'budget': summary.budget,
          'limitations': summary.limitations if not report else report.limitations,
          'checks': report.generation_metadata.get('submission_checklist') if report else None}
calls = store.provider_calls(run_id)
result['provider_reported_usage'] = {
    'input_tokens': sum(c.get('input_tokens') or 0 for c in calls),
    'output_tokens': sum(c.get('output_tokens') or 0 for c in calls),
    'note': 'Provider receipts; excludes unknown usage on failed or uncertain requests. Budget reservations are separate.',
}
(output / 'summary.json').write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
print(json.dumps(result, default=str), flush=True)
