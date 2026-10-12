"""Sequential real API/worker validation, resumable without repeating completed runs.

No synthetic responses, account changes, automatic uncertain-call retries or keys
in artifacts. Run from the repository with its installed Python environment.
"""
import argparse
import hashlib
import json
import time
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from signal_research.cli import context
from signal_research.providers.search.account import free_account_usage

ROSTER = ['AXISBANK', 'HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'SBIN',
          'BAJFINANCE', 'BAJAJFINSV', 'SHRIRAMFIN', 'HDFCLIFE', 'SBILIFE', 'JIOFIN', 'BSE']
TERMINAL = {'completed', 'failed', 'cancelled'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--companies', nargs='+', default=ROSTER + ['FEDERALBNK', 'CHOLAFIN', 'HDFCBANK:repeat', 'BAJFINANCE:repeat'])
    parser.add_argument('--output', default='data/exports/finals-validation')
    parser.add_argument('--as-of', default=datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat(), type=lambda value: date.fromisoformat(value).isoformat())
    args = parser.parse_args()
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)
    settings, store = context()
    cutoff = args.as_of
    source_root = Path(__file__).resolve().parents[1] / 'backend/src/signal_research'
    fingerprint = hashlib.sha256()
    for path in sorted(source_root.rglob('*')):
        if path.suffix in {'.py', '.yaml'}:
            fingerprint.update(str(path.relative_to(source_root)).encode())
            fingerprint.update(path.read_bytes())
    with httpx.Client(base_url='http://127.0.0.1:8000', timeout=60) as client:
        for label in args.companies:
            folder = root / label.replace(':', '-')
            folder.mkdir(exist_ok=True)
            completed = folder / 'summary.json'
            if completed.exists():
                summary = json.loads(completed.read_text(encoding='utf-8'))
                if summary['status'] in TERMINAL:
                    print(label, 'previous result:', summary['status'], summary.get('outcome'), flush=True)
                    continue
            allowance = free_account_usage(settings)
            if allowance < settings.max_search_calls * (2 if settings.tavily_search_depth == 'advanced' else 1):
                raise RuntimeError('Insufficient verified free search allowance for another bounded run')
            run_file = folder / 'run.json'
            if run_file.exists():
                run_id = json.loads(run_file.read_text(encoding='utf-8'))['run_id']
            else:
                response = client.post('/api/v1/companies/resolve', json={'query': label.split(':')[0]})
                response.raise_for_status()
                company = response.json()['resolved']
                response = client.post('/api/v1/runs', json={'company_id': company['id'], 'as_of': cutoff, 'mode': 'live'})
                response.raise_for_status()
                run_id = response.json()['run_id']
                run_file.write_text(json.dumps({'run_id': run_id, 'free_search_credits_before': allowance,
                    'backend_source_sha256': fingerprint.hexdigest(), 'as_of': cutoff,
                    'configuration': {key: getattr(settings, key) for key in ('max_run_seconds', 'max_input_tokens', 'max_output_tokens', 'max_model_calls', 'max_search_calls', 'max_fetch_documents', 'tavily_search_depth', 'nvidia_model_research', 'nvidia_model_extract')},
                    'validation_kind': 'real live API/worker; no mocks'}, indent=2), encoding='utf-8')
            print(label, 'run', run_id, 'free searches available', allowance, flush=True)
            previous = None
            started = time.monotonic()
            while True:
                response = client.get('/api/v1/runs/' + run_id)
                response.raise_for_status()
                summary = response.json()
                state = (summary['status'], summary['budget'].get('model_calls'), summary['progress'].get('documents_parsed'))
                if state != previous:
                    print(label, state, 'elapsed', round(time.monotonic() - started), flush=True)
                    previous = state
                if summary['status'] in TERMINAL:
                    break
                execution_started = datetime.fromisoformat(summary['started_at']) if summary.get('started_at') else None
                if execution_started and execution_started.tzinfo is None:
                    execution_started = execution_started.replace(tzinfo=UTC)
                if execution_started and (datetime.now(UTC) - execution_started).total_seconds() > settings.max_run_seconds + 150:
                    client.post('/api/v1/runs/' + run_id + '/cancel').raise_for_status()
                    print(label, 'requested cancellation after wall-clock overrun', flush=True)
                time.sleep(10)
            if summary.get('ended_at') and summary.get('started_at'):
                summary['observed_runtime_seconds'] = (datetime.fromisoformat(summary['ended_at']) - datetime.fromisoformat(summary['started_at'])).total_seconds()
            completed.write_text(json.dumps(summary, indent=2), encoding='utf-8')
            for endpoint, filename in [('report', 'report.json'), ('events', 'events.json')]:
                response = client.get(f'/api/v1/runs/{run_id}/{endpoint}')
                if response.is_success:
                    folder.joinpath(filename).write_text(json.dumps(response.json(), indent=2), encoding='utf-8')
            folder.joinpath('provider-usage.json').write_text(json.dumps(store.provider_calls(run_id), indent=2, default=str), encoding='utf-8')
            print(label, 'DONE', summary['status'], summary.get('outcome'), summary.get('observed_runtime_seconds'), flush=True)
            errors = ' '.join(summary.get('limitations', [])).lower()
            if any(word in errors for word in ('quota check failed', 'authentication failed', 'unauthorized', 'quota exceeded', 'credits exhausted', 'free allowance is exhausted')):
                raise RuntimeError('Account access/quota failure; stopping matrix instead of repeating paid or invalid requests')


if __name__ == '__main__':
    main()
