"""Package LOCAL validation evidence, never credentials, raw PDFs or databases."""
import hashlib
import json
import re
import zipfile
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    base = root / 'data/exports/finals-validation'
    live = base / 'final-validation'
    folders = {folder.name: folder for folder in live.iterdir() if folder.is_dir()}
    files = []
    for label in sorted({name.removesuffix('-retry') for name in folders}):
        folder = folders.get(label + '-retry') or folders[label]
        for name in ('summary.json', 'report.json', 'run.json', 'events.json', 'provider-usage.json'):
            file = folder / name
            if file.is_file():
                files.append(file)
    for pattern in ('manual-*.json', '*-balance.png', '*-page-*.png'):
        files.extend(base.glob(pattern))
    for name in ('final-source-link-checks.json', 'official-nifty50.csv',
                 'real-inflight-cancellation.json', 'real-cancellation.json',
                 'fresh-current.json', 'fresh-latest.json', 'restart-exports.json',
                 'resolution.json'):
        file = base / name
        if file.is_file():
            files.append(file)
    entries = {}
    for file in sorted(set(files)):
        if file.is_symlink() or not file.resolve().is_relative_to(base):
            raise RuntimeError('Validation path is outside the approved artifact directory')
        data = file.read_bytes()
        if re.search(rb'(?:nvapi-[A-Za-z0-9_-]{20,}|tvly-(?:dev|prod)-[A-Za-z0-9_-]{20,})', data):
            raise RuntimeError('Credential-shaped data found; no archive created')
        entries[file.relative_to(base).as_posix()] = data
    entries['README.txt'] = (
        b'LOCAL validation evidence, not submitted or published. Reports retain public '
        b'parsed source passages; respect source reuse terms. No raw PDFs, API keys or '
        b'database included. HTTP checks are not semantic claim verification. '
        b'All clean final runs abstained: zero verified discoveries. Clean retries '
        b'supersede interrupted/cancelled records; originals remain on the demo PC. '
        b'Mocks/replay are not real-company discovery validation. Read docs/FINAL-AUDIT.md '
        b'and docs/SOURCE-CHECKS.md in the separate source archive.\n'
    )
    output = root / 'output/validation-evidence.zip'
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
        archive.writestr('EVIDENCE-MANIFEST.json', json.dumps(
            {name: hashlib.sha256(data).hexdigest() for name, data in entries.items()}, indent=2))
    print(json.dumps({'local_archive': str(output), 'files': len(entries),
                      'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                      'submitted_or_published': False}, indent=2))


if __name__ == '__main__':
    main()
