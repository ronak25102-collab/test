"""Offline, fail-closed assembly of source-owned, reviewed report fixtures.

An imported review is checked before any changes. Deterministic recomputation
does not constitute a new semantic/model review, and is recorded as such.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from signal_research.domain.schemas import (
    Calculation,
    Fact,
    Passage,
    ResearchReport,
    SourceDocument,
)
from signal_research.evidence.tiers import evidence_tier
from signal_research.extraction.models import ExtractedFactCandidate
from signal_research.extraction.validate import validate_candidate
from signal_research.finance.calculations import calculate, numeric_fact
from signal_research.research.brief import submission_checklist
from signal_research.research.falsification import observable_tests
from signal_research.research.headline import validate_headline
from signal_research.research.history import comparable_series
from signal_research.research.integrity import report_digest
from signal_research.research.peers import compare_peers
from signal_research.research.story import timeline_story
from signal_research.research.structural import detect_breaks
from signal_research.research.verifier import verify_report

ROOT = Path(__file__).resolve().parents[4]
FIXTURE_DIR = Path(__file__).parent


def read_json(path: Path):
    if path.suffix == '.gz':
        return json.loads(gzip.decompress(path.read_bytes()))
    return json.loads(path.read_text(encoding='utf-8'))


def json_value(value):
    """Convert the existing history helpers' Decimal/date/UUID output to JSON."""
    return json.loads(json.dumps(value, default=str))


def fiscal_years(report):
    return sorted({f.period_end.year + (f.period_end.month > 3)
                   for f in report.facts if f.period_end})


def parity_shortfalls(report):
    """Do not fill absent history/peers with duplicate passages or invented facts."""
    gaps = []
    for key, minimum in [('documents', 6), ('passages', 300), ('facts', 15),
                         ('calculations', 8)]:
        actual = len(getattr(report, key))
        if actual < minimum:
            gaps.append(f'{key}: {actual} < {minimum}')
    benchmark = report.generation_metadata.get('peer_benchmark', {})
    peers = {identifier for row in benchmark.get('comparisons', [])
             for identifier in row.get('peers', {})}
    if len(peers) < 2:
        gaps.append(f'verified matched peers: {len(peers)} < 2')
    years = fiscal_years(report)
    if len(years) < 3:
        gaps.append(f'fiscal years with verified facts: {len(years)} < 3 ({years})')
    for key in ['discoveries', 'claims', 'timeline_events']:
        if not getattr(report, key):
            gaps.append(f'{key}: empty')
    return gaps


def recursive_keys(value, prefix=''):
    """Union recursive keys across array records, independent of record counts."""
    found = set()
    if isinstance(value, dict):
        for key, item in value.items():
            path = f'{prefix}.{key}' if prefix else key
            found.add(path)
            found.update(recursive_keys(item, path))
    elif isinstance(value, list):
        for item in value:
            found.update(recursive_keys(item, prefix + '[]'))
    return found


def validate_source_bindings(report, *, require_bytes=True):
    passages = {p.id: p for p in report.passages}
    documents = {d.id: d for d in report.documents}
    for passage in report.passages:
        if passage.document_id not in documents:
            raise ValueError(f'Orphan passage {passage.id}')
    for document in report.documents:
        if not require_bytes:
            continue
        if not document.local_object_key:
            raise ValueError(f'Source bytes unavailable: {document.canonical_url}')
        source = Path(document.local_object_key.replace('\\', '/'))
        source = source if source.is_absolute() else ROOT / source
        if not source.is_file():
            raise ValueError(f'Source bytes unavailable: {source}')
        if hashlib.sha256(source.read_bytes()).hexdigest() != document.content_hash:
            raise ValueError(f'Source byte hash mismatch: {source}')
    for fact in report.facts:
        passage = passages.get(fact.passage_id)
        if passage is None:
            raise ValueError(f'Fact {fact.id} lacks source passage')
        candidate = ExtractedFactCandidate(
            **{key: getattr(fact, key) for key in (
                'metric_key', 'value_raw', 'unit_raw', 'currency', 'period_start',
                'period_end', 'period_type', 'scope', 'segment', 'passage_id')},
            extraction_confidence=fact.extraction_confidence or 1,
        )
        # Match LiveResearch.extract: issuer identity belongs to the verified
        # document, because a continuation balance-sheet page need not repeat it.
        result = validate_candidate(candidate, passage, fact.entity_id,
                                    report.company.business_profiles[0])
        if result.fact is None:
            raise ValueError(f'Fact {fact.id} rejected: {result.reason}')
        for key in ['value_decimal', 'unit_normalized', 'definition_id', 'currency']:
            if getattr(result.fact, key) != getattr(fact, key):
                raise ValueError(f'Fact {fact.id} normalization mismatch: {key}')


def recompute_calculations(report):
    facts = {f.id: f for f in report.facts}
    rebuilt = []
    for calculation in report.calculations:
        result = calculate(calculation.formula_id,
                           [numeric_fact(facts[i]) for i in calculation.input_fact_ids],
                           calculation.parameters)
        if not result.available:
            raise ValueError(f'{calculation.formula_id}: {result.limitations}')
        if (calculation.output_value is not None
                and calculation.output_value != result.output_value):
            raise ValueError(f'Authored output differs from formula: {calculation.id}')
        rebuilt.append(calculation.model_copy(update={
            'output_value': result.output_value, 'formula_version': result.formula_version,
            'unit': result.unit, 'available': result.available,
            'comparability_checks': result.comparability_checks,
        }))
    report.calculations = rebuilt


def build_fixture(input_path: Path, *, require_bytes=True, strict_parity=False):
    data = yaml.safe_load(input_path.read_text(encoding='utf-8'))
    imported = data.get('reference')
    if imported:
        source = (input_path.parent / imported).resolve()
        report = ResearchReport.model_validate(read_json(source))
        # A transport or metadata change cannot repair a failed prior review.
        verify_report(report)
    elif data.get('reviewed_report'):
        report = ResearchReport.model_validate(data['reviewed_report'])
    else:
        raise ValueError(f'{input_path.stem}: no source-reviewed report; research inputs '
                         'are incomplete and cannot be published automatically')
    original_digest = report.generation_metadata.get('verification_digest')
    original_run = str(report.run_id)
    additions = data.get('additions', {})
    changed = bool(additions or data.get('reviewed_report'))
    if imported and data.get('reviewed_report'):
        report = ResearchReport.model_validate(data['reviewed_report'])
    if data.get('facts'):
        # Expanded YAML rows are the editable fact inputs, not decorative copies.
        # Source context fields below are checked against their report passages.
        authored = [Fact.model_validate({key: value for key, value in row.items()
                                        if key in Fact.model_fields})
                    for row in data['facts']]
        changed = changed or authored != report.facts
        report.facts = authored
        passages = {str(p.id): p for p in report.passages}
        documents = {p.id: p for p in report.documents}
        for row in data['facts']:
            passage = passages.get(str(row.get('passage_id')))
            if passage is None:
                raise ValueError('YAML fact references an unknown source passage')
            document = documents[passage.document_id]
            expected = {
                'source_url': str(document.canonical_url), 'document_title': document.title,
                'document_type': document.document_type,
                'publication_date': document.published_at.isoformat() if document.published_at else None,
                'sha256': document.content_hash, 'exact_passage': passage.text,
                'row_label': passage.row_label, 'column_label': passage.column_label,
                'section': passage.section,
                'page_number': passage.page_index + 1 if passage.page_index is not None else None,
            }
            for key, value in expected.items():
                actual = row.get(key)
                if key == 'publication_date' and actual:
                    actual = str(actual).replace('+00:00', 'Z')
                    value = str(value).replace('+00:00', 'Z')
                if key in row and actual != value:
                    raise ValueError(f'YAML fact source binding differs: {key}')
    if changed:
        review = data.get('editorial_review', {})
        required = {str(c.id) for c in report.claims if c.material}
        if (not review.get('reviewer') or not review.get('reviewed_at')
                or not review.get('notes')
                or not required <= set(review.get('claim_ids', []))):
            raise ValueError('Changed/authored content requires explicit source-based '
                             'editorial review of every material claim')
    for key, model in [('documents', SourceDocument), ('passages', Passage),
                       ('facts', Fact), ('calculations', Calculation)]:
        getattr(report, key).extend(model.model_validate(item)
                                   for item in additions.get(key, []))
    if report.publication_status.value != 'published':
        raise ValueError('A precomputed discovery must be published')
    validate_source_bindings(report, require_bytes=require_bytes)
    recompute_calculations(report)
    metadata = report.generation_metadata
    original_trace = metadata.get('strength_trace', {})
    benchmark = metadata.get('peer_benchmark', {})
    bundles = additions.get('peer_sources', data.get('peer_sources',
                            benchmark.get('sources', [])))
    for bundle in bundles:
        peer_report = ResearchReport.model_validate({
            'run_id': str(report.run_id), 'company': bundle['company'],
            'cutoff': str(report.cutoff), 'historical_coverage': 'Peer source inputs',
            'source_coverage': {}, 'outcome': 'partial', 'publication_status': 'abstained',
            'documents': bundle.get('documents', []), 'passages': bundle.get('passages', []),
            'facts': bundle.get('facts', []),
        })
        validate_source_bindings(peer_report, require_bytes=require_bytes)
    peer_facts = [Fact.model_validate(f) for b in bundles for f in b.get('facts', [])]
    reproduced = compare_peers(report.facts, peer_facts)
    metadata['peer_benchmark'] = {
        **benchmark, **json_value(reproduced), 'sources': bundles,
        'limitations': benchmark.get('limitations', []),
    }
    headline_claim_id = metadata.get('headline', {}).get('claim_id')
    headline_claim = next((c for c in report.claims if str(c.id) == str(headline_claim_id)), None)
    headline_calculations = {i for i in headline_claim.calculation_ids} if headline_claim else set()
    headline_facts = {str(i) for c in report.calculations if c.id in headline_calculations
                      for i in c.input_fact_ids}
    if not headline_facts and headline_claim:
        identifiers = {f.id for f in report.facts}
        headline_facts = {str(link.passage_or_fact_id) for link in headline_claim.evidence_links
                          if link.passage_or_fact_id in identifiers}
    benchmarked = {identifier for comparison in reproduced['comparisons']
                   for identifier in comparison['target_fact_ids']}
    headline_peer_covered = bool(headline_facts) and headline_facts <= benchmarked
    metadata['peer_benchmark'].update({
        'headline_comparison_status': 'verified' if headline_peer_covered else 'inconclusive',
        'headline_missing_fact_ids': sorted(headline_facts - benchmarked),
    })
    breaks = detect_breaks(report.facts, report.passages, report.documents)
    metadata['structural_breaks'] = breaks
    metadata['timeline_story'] = json_value(timeline_story(
        report.facts, report.calculations, report.passages, report.documents, breaks))
    report.source_coverage['historical_series'] = json_value(comparable_series(report.facts))
    passages_by_id = {p.id: p for p in report.passages}
    used_documents = {passages_by_id[f.passage_id].document_id for f in report.facts
                      if f.passage_id in passages_by_id}
    used_documents.update(passages_by_id[link.passage_or_fact_id].document_id
                          for claim in report.claims for link in claim.evidence_links
                          if link.passage_or_fact_id in passages_by_id)
    report.source_coverage.update({
        'documents_found': len(report.documents), 'documents_used': len(used_documents),
        'eligible_origin_families': len({d.origin_family_id for d in report.documents
                                       if d.id in used_documents and d.cutoff_eligibility == 'eligible'}),
        'primary_source': any(d.id in used_documents and d.document_type.startswith('issuer')
                              for d in report.documents),
    })
    metadata['submission_checklist'] = json_value(submission_checklist(report))
    tests = metadata.get('falsification_tests', {}).get('conditions', [])
    now_check = next((test for test in tests if test.get('kind') == 'current_reconciliation'),
                     {'status': 'not_checked', 'interpretation':
                      'No current reconciliation was reviewed in the archived evidence.'})
    metadata['falsification_tests'] = json_value(observable_tests(
        report.facts, report.calculations, report.passages, report.documents,
        report.cutoff, now_check))
    rules = original_trace.get('rules', {})
    families = original_trace.get('origin_families', [])
    # Preserve source-reviewed qualitative predicates; compute the tier ourselves.
    # An input lacking these predicates cannot silently earn a stronger rating.
    strength, trace = evidence_tier(
        origin_families=families,
        non_issuer=bool(rules.get('non_issuer_support', False)),
        peer_comparison_done=headline_peer_covered,
        unresolved_break=any('requires_' in b['status'] for b in breaks),
        counterargument_searched=all(d.counterargument.search_attempted
                                    for d in report.discoveries),
        counterargument_addressed=bool(rules.get('counterargument_addressed', False)),
        issuer_only_facts=bool(original_trace.get('caps') and any(
            'issuer-company figures originate' in cap for cap in original_trace['caps'])),
    )
    metadata['strength_trace'] = trace
    if reproduced['status'] == 'verified' and not headline_peer_covered:
        note = ('Matched peer context exists, but it does not benchmark all exact '
                'metric/scope/period inputs of the published headline; strength is capped at Weak.')
        if note not in report.limitations:
            report.limitations.append(note)
    for discovery in report.discoveries:
        discovery.evidence_strength = strength
        discovery.strength_rationale = ' '.join([trace['note'], *trace['caps']])
        errors = validate_headline(discovery.discovery_sentence, report.company.legal_name,
                                   report.facts, report.calculations)
        if errors:
            raise ValueError(f'Headline failed: {errors}')
    metadata.setdefault('headline', {}).setdefault('method', 'verified_arithmetic_template')
    metadata['headline']['validation_errors'] = []
    generated_at = (data.get('generated_at') or data.get('editorial_review', {}).get('reviewed_at')
                    or datetime.now(UTC).isoformat())
    data_as_of = str(data.get('data_as_of', report.cutoff))
    provenance = {key: metadata.get(key) for key in [
        'configured_provider', 'routing', 'configured_model_id', 'models_used',
        'provider', 'model_id', 'search_queries', 'opposing_queries', 'context_searches']}
    metadata.update({
        'mode': 'precomputed', 'pipeline': 'precomputed-reviewed-evidence-v1',
        'generated_at': generated_at, 'data_as_of': data_as_of,
        'reference_review': {'run_id': original_run, 'verification_digest': original_digest,
                             'provenance': provenance,
                             'note': 'Archived review; no new model review is claimed.'},
        'editorial_review': data.get('editorial_review'),
        'configured_provider': 'none', 'routing': 'offline stored evidence',
        'configured_model_id': None, 'models_used': [], 'provider': 'none', 'model_id': None,
        'model_usage': {'calls': 0, 'input_tokens': 0, 'output_tokens': 0,
                        'estimated_cost_usd': 0, 'note': 'No model used by this replay.'},
        'provider_usage': {'search_calls': 0, 'fetch_calls': 0, 'model_calls': 0},
        'cache_usage': {'cold_start': False, 'reused': len(report.facts), 'fresh': 0},
        'historical_cache': [], 'stage_durations': {},
        'budget': {'search_calls': 0, 'fetch_documents': 0, 'model_calls': 0,
                   'input_tokens': 0, 'output_tokens': 0, 'reserved_cost_usd': 0},
        'source_receipts': data.get('source_receipts', []),
        'publication_status': report.publication_status.value,
        'cutoff': str(report.cutoff),
    })
    # Historical search records are archived provenance, never this run's activity.
    for key in ['search_queries', 'opposing_queries', 'context_searches']:
        metadata[key] = []
    report.source_coverage['mode'] = 'precomputed'
    report.source_coverage['synthetic'] = False
    report.source_coverage['data_as_of'] = data_as_of
    gaps = parity_shortfalls(report)
    metadata['parity'] = {'passed': not gaps, 'shortfalls': gaps}
    for gap in gaps:
        note = 'Stored evidence coverage shortfall: ' + gap
        if note not in report.limitations:
            report.limitations.append(note)
    # The source review was verified above. Rebind its unchanged semantic claims
    # after deterministic recomputation/metadata transport, with explicit lineage.
    metadata['verification_digest'] = report_digest(report)
    verify_report(report)
    if strict_parity and gaps:
        raise ValueError(f'{input_path.stem} parity failed: ' + '; '.join(gaps))
    return report, data


def index_entry(report, data):
    metadata = report.generation_metadata
    symbol = report.company.symbols[0]
    roster = read_json(FIXTURE_DIR / 'roster.json')['companies']
    identity = next((entry for entry in roster if entry['symbol'] == symbol), {})
    return {
        'symbol': symbol, 'legal_name': identity.get('legal_name', report.company.legal_name),
        'aliases': list(dict.fromkeys([*report.company.aliases, *identity.get('aliases', [])])),
        'nse_code': symbol,
        'bse_code': identity.get('bse_code', data.get('bse_code')),
        'profile': report.company.business_profiles[0].value,
        'generated_at': metadata['generated_at'], 'data_as_of': metadata['data_as_of'],
        'outcome': 'published', 'evidence_strength': report.discoveries[0].evidence_strength.value,
        'sources': [{'url': str(d.canonical_url), 'retrieved_at': d.retrieved_at.isoformat(),
                     'sha256': d.content_hash} for d in report.documents],
        'parity': metadata['parity'],
    }
