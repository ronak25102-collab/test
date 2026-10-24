"""Rebuild stored evidence without invoking search, providers, or network fetches."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend' / 'src'))

from signal_research.precomputed.builder import (  # noqa: E402
    FIXTURE_DIR,
    build_fixture,
    index_entry,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('symbols', nargs='*')
    parser.add_argument('--strict-parity', action='store_true')
    parser.add_argument('--output-dir', type=Path, default=FIXTURE_DIR)
    args = parser.parse_args()
    inputs = FIXTURE_DIR / 'inputs'
    paths = [inputs / f'{symbol.upper()}.yaml' for symbol in args.symbols]
    paths = paths or sorted(inputs.glob('*.yaml'))
    entries, failed = [], []
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for path in paths:
        try:
            report, data = build_fixture(path, strict_parity=args.strict_parity)
            symbol = report.company.symbols[0]
            target = args.output_dir / f'{symbol}.json'
            target.write_text(report.model_dump_json(indent=2), encoding='utf-8')
            entries.append(index_entry(report, data))
            print(f'{symbol}: verified; parity={not report.generation_metadata["parity"]["shortfalls"]}')
        except Exception as error:
            failed.append({'symbol': path.stem, 'error': str(error)})
            print(f'{path.stem}: FAILED: {error}', file=sys.stderr)
    # Partial builds preserve previously generated entries for other symbols.
    index_path = args.output_dir / 'index.json'
    old = json.loads(index_path.read_text(encoding='utf-8')) if index_path.exists() else {}
    replaced = {path.stem for path in paths}
    kept = [entry for entry in old.get('companies', []) if entry['symbol'] not in replaced]
    completed = kept + entries
    complete_symbols = {entry['symbol'] for entry in completed}
    roster_path = FIXTURE_DIR / 'roster.json'
    if roster_path.exists():
        roster = json.loads(roster_path.read_text(encoding='utf-8'))
        failed_symbols = {entry['symbol'] for entry in failed}
        for entry in roster['companies']:
            if entry['symbol'] not in complete_symbols | failed_symbols:
                failed.append({'symbol': entry['symbol'],
                    'error': 'Source-reviewed report, bound financial history and matched peers remain incomplete'})
    index_path.write_text(json.dumps({'schema_version': '1.0',
                                     'companies': completed, 'incomplete': failed},
                                    indent=2), encoding='utf-8')
    # A selected-symbol rebuild fails only for that requested selection. A full
    # catalog build also fails on any unfinished official roster constituent.
    requested = {path.stem for path in paths}
    return 1 if any(entry['symbol'] in requested or not args.symbols for entry in failed) else 0


if __name__ == '__main__':
    raise SystemExit(main())
