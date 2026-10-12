"""Bounded LIVE link checks and retained-file hashes; not human claim verification."""
import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from signal_research.retrieval.transport import PublicTransport
from signal_research.retrieval.url_policy import validate_public_url


def check_link(url):
    with httpx.Client(transport=PublicTransport(), timeout=12, trust_env=False) as client:
        for _ in range(6):
            validate_public_url(url, resolve_dns=False)
            with client.stream('GET', url) as response:
                if response.is_redirect:
                    url = str(response.url.join(response.headers.get('location', '')))
                    continue
                prefix = next(response.iter_bytes(chunk_size=512), b'')
                return {'status': response.status_code, 'final_url': url,
                        'content_type': response.headers.get('content-type'), 'pdf_header': prefix.startswith(b'%PDF')}
        return {'error': 'Redirect limit exceeded'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='data/exports/finals-validation/final')
    parser.add_argument('--output', default='data/exports/finals-validation/source-link-checks.json')
    args = parser.parse_args()
    results = {}
    root = Path(args.root)
    files = {file.parent.name: file for file in root.glob('*/report.json')}
    # Use the same clean-retry selection as the live matrix. Preserve original
    # artifacts, but do not misattribute their links to the later run.
    selected = {}
    for label in sorted({name.removesuffix('-retry') for name in files}):
        selected[label] = files.get(label + '-retry') or files[label]
    for label, file in selected.items():
        report = json.loads(file.read_text(encoding='utf-8'))
        facts = report['facts']
        used_passages = {f['passage_id'] for f in facts}
        used_docs = {p['document_id'] for p in report['passages'] if p['id'] in used_passages}
        documents = sorted(report['documents'], key=lambda d: (d['id'] in used_docs,
                           d['document_type'].startswith('issuer'), d['cutoff_eligibility'] == 'eligible'), reverse=True)[:5]
        checks = []
        for document in documents:
            record = {'url': document['canonical_url'], 'document_id': document['id'],
                      'published_at': document['published_at'], 'eligibility': document['cutoff_eligibility']}
            try:
                record['live_link'] = check_link(document['canonical_url'])
            except Exception as exc:
                record['live_link'] = {'error': str(exc)}
            path = Path(document['local_object_key']) if document.get('local_object_key') else None
            record['retained_hash_matches'] = bool(path and path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == document['content_hash'])
            checks.append(record)
        results[label] = {'checked_at': datetime.now(UTC).isoformat(), 'artifact_folder': file.parent.name,
            'validation_kind': 'actual HTTP prefix retrieval and local hash comparison; NOT manual semantic verification',
            'discovery_claim_support': 'NOT VERIFIED' if not report['discoveries'] else 'Requires manual review', 'checks': checks}
        Path(args.output).write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(label, 'links checked', len(checks), flush=True)


if __name__ == '__main__':
    main()
