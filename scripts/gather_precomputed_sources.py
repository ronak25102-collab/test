"""Download explicitly selected source URLs for offline fixture authoring.

This script is a build-time research utility. Runtime playback never invokes it.
HTTP failures and HTML error pages cannot become financial PDF sources.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def fetch_source(url: str, directory: Path, *, timeout: int = 30) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / (hashlib.sha256(url.encode()).hexdigest() + '.download')
    result = subprocess.run(
        [shutil.which('curl.exe') or shutil.which('curl') or 'curl',
         '--location', '--silent', '--show-error', '--max-time', str(timeout),
         '--user-agent', 'Mozilla/5.0', '--output', str(temporary), '--write-out',
         '%{json}', url], capture_output=True, text=True, check=False,
    )
    receipt = json.loads(result.stdout) if result.stdout.strip() else {}
    receipt = {key: receipt.get(key) for key in
               ['http_code', 'url_effective', 'content_type', 'size_download', 'time_total']}
    receipt.update(url=url, retrieved_at=datetime.now(UTC).isoformat(),
                   curl_exit_code=result.returncode)
    if result.returncode or receipt['http_code'] != 200:
        raise ValueError(f'Source request failed: {receipt}; {result.stderr}')
    body = temporary.read_bytes()
    if '.pdf' in url.lower() and not body.startswith(b'%PDF'):
        raise ValueError(f'Source returned HTTP 200 but is not a PDF: {url}')
    digest = hashlib.sha256(body).hexdigest()
    suffix = '.pdf' if body.startswith(b'%PDF') else '.html'
    target = directory / (digest + suffix)
    temporary.replace(target)
    receipt.update(sha256=digest, local_object_key=target.as_posix())
    (directory / (digest + '.receipt.json')).write_text(
        json.dumps(receipt, indent=2), encoding='utf-8')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('urls', nargs='*')
    parser.add_argument('--restore-fixtures', action='store_true')
    parser.add_argument('--directory', type=Path, default=Path('data/precomputed-sources'))
    args = parser.parse_args()
    if args.restore_fixtures:
        root = Path(__file__).resolve().parents[1]
        fixture_dir = root / 'backend' / 'src' / 'signal_research' / 'precomputed'
        index = json.loads((fixture_dir / 'index.json').read_text(encoding='utf-8'))
        documents = {}
        for entry in index['companies']:
            report = json.loads((fixture_dir / f'{entry["symbol"]}.json').read_text(encoding='utf-8'))
            bundles = [report, *report['generation_metadata'].get('peer_benchmark', {}).get('sources', [])]
            for bundle in bundles:
                for document in bundle.get('documents', []):
                    documents[(document['content_hash'], document['local_object_key'])] = document
        for (expected, location), document in documents.items():
            if not location:
                raise ValueError('Cited source has no local byte location')
            target = (root / location.replace('\\', '/')).resolve()
            target.relative_to(root)
            if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
                continue
            receipt = fetch_source(document['canonical_url'], args.directory)
            if receipt['sha256'] != expected:
                raise ValueError(f'Source bytes changed; source review required: {document["canonical_url"]}')
            target.parent.mkdir(parents=True, exist_ok=True)
            downloaded = Path(receipt['local_object_key']).resolve()
            if downloaded != target:
                shutil.copyfile(downloaded, target)
            print(f'Restored {document["title"]}')
    for url in args.urls:
        print(json.dumps(fetch_source(url, args.directory)))


if __name__ == '__main__':
    main()
