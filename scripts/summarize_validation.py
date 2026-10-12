"""Build an evidence-based live matrix; an abstention never becomes a PASS."""
import argparse
import json
from pathlib import Path

from validate_live import ROSTER


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='data/exports/finals-validation/final')
    parser.add_argument('--output', default='docs/LIVE-RESULTS.md')
    args = parser.parse_args()
    root = Path(args.root)
    lines = ['# Actual live validation results', '',
        'Actual local API/background-worker runs using existing free NVIDIA/Tavily access. No mocks or synthetic data.',
        'Abstention is honest failure to establish a discovery, not a successful discovery. Dates and revisions are retained in run artifacts.',
        'Clean retry folders replace interrupted/cancelled rows in the main matrix; originals remain preserved and documented. Revisions differ where later recovery/identity fixes were tested.', '',
        '| Company | Status | Runtime s | Outcome | Known model input/output | Search credits reserved | Facts/calculations | Remaining issues |',
        '|---|---|---:|---|---:|---:|---:|---|']
    details = []
    extras = sorted(p.name for p in root.iterdir() if p.is_dir() and p.name not in ROSTER and not p.name.endswith('-retry'))
    for label in ROSTER + extras:
        if extras and label == extras[0]:
            lines.extend(['', '## Unseen, sparse and repeated live runs', '',
                '| Company | Status | Runtime s | Outcome | Known model input/output | Search credits reserved | Facts/calculations | Remaining issues |',
                '|---|---|---:|---|---:|---:|---:|---|'])
        folder = root / label
        retry = root / (label + '-retry')
        if (retry / 'summary.json').exists():
            folder = retry
        if not (folder / 'summary.json').exists():
            lines.append(f'| {label} | NOT VERIFIED | — | Not finished | — | — | — | Pending live run |')
            continue
        summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
        report = json.loads((folder / 'report.json').read_text(encoding='utf-8')) if (folder / 'report.json').exists() else {}
        calls = json.loads((folder / 'provider-usage.json').read_text(encoding='utf-8'))
        model = [c for c in calls if c['provider'] == 'nvidia']
        known_in = sum(c.get('input_tokens', 0) for c in model if c['status'] == 'ok')
        known_out = sum(c.get('output_tokens', 0) for c in model if c['status'] == 'ok')
        unknown = sum(c['status'] != 'ok' for c in model)
        facts, calcs = len(report.get('facts', [])), len(report.get('calculations', []))
        outcome = 'discovery' if report.get('discoveries') else 'failure' if summary['status'] == 'failed' else 'abstention' if summary.get('outcome') == 'insufficient_evidence' else summary.get('outcome', summary['status'])
        status = 'PARTIAL' if facts or report.get('discoveries') else 'FAIL'
        issues = summary.get('limitations', [])
        missing = report.get('abstention', {}).get('missing_requirements', []) if report.get('abstention') else []
        short = '; '.join(missing[:2] or issues[-2:]) or 'Discovery quality needs human validation'
        short = short.replace('|', '/')[:260]
        usage = f'{known_in}/{known_out}' + (f' + {unknown} unknown calls' if unknown else '')
        seconds = summary.get('observed_runtime_seconds', 0)
        name = summary.get('company', {}).get('legal_name', label)
        if label not in ROSTER:
            name += f' ({label})'
        manifest = json.loads((folder / 'run.json').read_text(encoding='utf-8'))
        search_credits = summary['budget']['search_calls'] * (2 if manifest['configuration'].get('tavily_search_depth') == 'advanced' else 1)
        lines.append(f'| {name} | {status} | {seconds:.1f} | {outcome} | {usage} | {search_credits} | {facts}/{calcs} | {short} |')
        details.extend([f'## {label}: {summary["id"]}', '', f'Live artifacts: `{folder.as_posix()}`. Status {summary["status"]}; outcome {summary.get("outcome")}.', '',
            'Issues actually recorded:', '', *[f'- {issue}' for issue in issues], '',
            'Missing requirements:', '', *[f'- {item}' for item in missing], ''])
    lines += ['', 'Known tokens are provider-reported successful calls only. Failed/uncertain response usage is unknown; durable budget reservations remain charged conservatively.',
        'Search credits reserve one per basic request or two per advanced request. They are not an independently measured account billing statement. Configured monetary cost is zero for verified included/free access.',
        'No row receives PASS solely from automated checks or successful publication. Published discoveries also require manual source and calculation review.', '', *details]
    Path(args.output).write_text('\n'.join(lines), encoding='utf-8')
    print(args.output)


if __name__ == '__main__':
    main()
