"""Re-check retained domain references locally; no provider or network requests.

Startup quarantines unproven legacy entries. This script can restore a legacy
domain only after its original hashed document passes the current issuer-bound
reference policy. Existing reports and historical proof records remain intact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from uuid import UUID

from signal_research.db.models import ArtifactModel, ResearchRunModel
from signal_research.db.repositories import Store
from signal_research.db.session import build_engine, session_factory
from signal_research.retrieval.issuer_identity import (
    ISSUER_REFERENCE_POLICY,
    exchange_issuer_domains,
)
from signal_research.retrieval.passages import bounded_parse_pdf, parse_html
from signal_research.settings import get_settings
from sqlalchemy import select


def audit_saved_references(store, settings, *, apply=False):
    with store.session_factory() as session:
        records = [(row.run_id, dict(row.payload)) for row in session.scalars(
            select(ArtifactModel).where(ArtifactModel.kind == 'issuer_domain_verification'))
            if row.payload.get('reference_policy') != ISSUER_REFERENCE_POLICY]
        owners = {run_id: session.get(ResearchRunModel, run_id).company_id for run_id, _ in records}
    parsed_cache, reviewed, results = {}, set(), []
    raw_root = (settings.data_dir / 'raw').resolve()
    for run_id, proof in records:
        owner, digest = owners[run_id], proof.get('content_hash', '')
        key = (owner, proof.get('document_id'), proof.get('source_url'))
        if key in reviewed:
            continue
        reviewed.add(key)
        company = store.get_company(owner)
        record = {'company_id': owner, 'legal_name': company.legal_name,
                  'source_url': proof.get('source_url'), 'legacy_domains': proof.get('domains', []),
                  'accepted_domains': [], 'applied': False}
        try:
            if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                raise ValueError('Original source hash is missing or invalid')
            if digest not in parsed_cache:
                candidates = list(raw_root.glob(digest + '.*'))
                if len(candidates) != 1:
                    raise ValueError('Original retained source is missing or ambiguous')
                path = candidates[0].resolve()
                if not path.is_relative_to(raw_root) or path.stat().st_size > settings.max_source_bytes:
                    raise ValueError('Retained source lies outside its allowed location or size')
                raw = path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != digest:
                    raise ValueError('Retained source hash does not match')
                parsed = (bounded_parse_pdf(UUID(proof['document_id']), path, settings.pdf_parse_timeout_seconds)
                          if raw.startswith(b'%PDF') else parse_html(UUID(proof['document_id']), raw))
                parsed_cache[digest] = (raw, '\n'.join(p.text for p in parsed.passages))
            raw, text = parsed_cache[digest]
            accepted = exchange_issuer_domains(raw, text, proof['source_url'], company)
            record['accepted_domains'] = accepted
            record['reason'] = 'Issuer-bound reference verified' if accepted else 'Reference ownership not established'
            if apply and accepted:
                current = proof | {'reference_policy': ISSUER_REFERENCE_POLICY, 'company_id': owner,
                                   'domains': accepted, 'revalidated_from_retained_hash': True}
                store.add_verified_issuer_domains(owner, accepted, UUID(proof['document_id']),
                                                 run_id=run_id, proof=current)
                record['applied'] = True
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            record['reason'] = str(exc)
        results.append(record)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', default='data/exports/domain-audits/reference-revalidation.json')
    args = parser.parse_args()
    settings = get_settings()
    store = Store(session_factory(build_engine(settings.database_url)), settings.data_dir)
    results = audit_saved_references(store, settings, apply=args.apply)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'reference_policy': ISSUER_REFERENCE_POLICY,
        'validation_kind': 'retained source hashes and issuer-bound reference ownership; no network calls',
        'results': results}, indent=2), encoding='utf-8')
    print(json.dumps({'references_reviewed': len(results), 'references_restored': sum(r['applied'] for r in results),
                      'output': str(output)}, indent=2))


if __name__ == '__main__':
    main()
