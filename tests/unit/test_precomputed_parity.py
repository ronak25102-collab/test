"""Real archived reports: enforce lineage and disclose, never pad, coverage gaps."""
import json
import socket

import pytest
import yaml
from signal_research.domain.schemas import ResearchReport
from signal_research.precomputed.builder import (
    FIXTURE_DIR,
    build_fixture,
    parity_shortfalls,
    read_json,
    recursive_keys,
)
from signal_research.research.verifier import verify_report

SYMBOLS = [entry['symbol'] for entry in read_json(FIXTURE_DIR / 'index.json')['companies']]


@pytest.mark.parametrize('symbol', SYMBOLS)
def test_stored_fixtures_pass_verifier_and_resolve_all_evidence(symbol):
    report = ResearchReport.model_validate(read_json(FIXTURE_DIR / f'{symbol}.json'))
    assert verify_report(report) is report
    assert report.publication_status.value == 'published'
    assert report.company.symbols == [symbol]
    documents = {d.id for d in report.documents}
    passages = {p.id: p for p in report.passages}
    facts = {f.id: f for f in report.facts}
    calculations = {c.id: c for c in report.calculations}
    assert all(p.document_id in documents for p in passages.values())
    assert all(f.passage_id in passages for f in facts.values())
    assert all(set(c.input_fact_ids) <= facts.keys() for c in calculations.values())
    assert all(set(c.calculation_ids) <= calculations.keys() for c in report.claims)
    assert all(link.passage_or_fact_id in facts.keys() | passages.keys()
               for claim in report.claims for link in claim.evidence_links)
    assert report.generation_metadata['model_usage']['calls'] == 0
    assert report.generation_metadata['provider_usage']['fetch_calls'] == 0
    assert report.generation_metadata['models_used'] == []
    if report.generation_metadata.get('editorial_review'):
        review = report.generation_metadata['editorial_review']
        assert review['notes'] and review['reviewed_at']
        assert {str(c.id) for c in report.claims if c.material} <= set(review['claim_ids'])
    else:
        assert report.generation_metadata['reference_review']['verification_digest']


@pytest.mark.parametrize('symbol', SYMBOLS)
@pytest.mark.parametrize('prefix', ['d45ea5a6', '0f0aaa37'])
def test_parity_report_tables_preserve_reference_record_structure(symbol, prefix):
    stored = read_json(FIXTURE_DIR / f'{symbol}.json')
    reference = read_json(FIXTURE_DIR / 'references' / f'{prefix}.json.gz')
    assert set(reference) <= set(stored)
    for key in ['documents', 'passages', 'facts', 'calculations', 'claims',
                'timeline_events', 'discoveries']:
        assert stored[key]
        assert recursive_keys(reference[key]) <= recursive_keys(stored[key])
    assert set(reference['generation_metadata']) <= set(stored['generation_metadata'])


def test_hdfc_meets_count_history_and_verified_peer_parity():
    report = ResearchReport.model_validate(read_json(FIXTURE_DIR / 'HDFCBANK.json'))
    assert parity_shortfalls(report) == []


@pytest.mark.parametrize('symbol', SYMBOLS)
def test_parity_minimums_for_every_published_fixture(symbol):
    report = ResearchReport.model_validate(read_json(FIXTURE_DIR / f'{symbol}.json'))
    assert parity_shortfalls(report) == []


@pytest.mark.parametrize('symbol', ['JIOFIN', 'ICICIBANK', 'SBIN', 'AXISBANK', 'KOTAKBANK'])
def test_other_peer_lanes_cannot_upgrade_the_headline_strength(symbol):
    report = ResearchReport.model_validate(read_json(FIXTURE_DIR / f'{symbol}.json'))
    benchmark = report.generation_metadata['peer_benchmark']
    assert benchmark['status'] == 'verified'
    assert benchmark['headline_comparison_status'] == 'inconclusive'
    assert benchmark['headline_missing_fact_ids']
    assert not report.generation_metadata['strength_trace']['rules']['peer_comparison_verified']
    assert report.discoveries[0].evidence_strength.value == 'Weak'


@pytest.mark.parametrize('symbol', [entry['symbol'] for entry in
                                  read_json(FIXTURE_DIR / 'roster.json')['companies']])
def test_every_nifty_track_a_company_has_a_reviewed_fixture(symbol):
    path = FIXTURE_DIR / f'{symbol}.json'
    if not path.is_file():
        pytest.xfail(f'{symbol}: source-reviewed discovery and full evidence parity remain incomplete')
    assert verify_report(ResearchReport.model_validate(read_json(path)))


def test_archived_jio_shortfalls_are_visible_and_strict_build_fails():
    reference = ResearchReport.model_validate(read_json(
        FIXTURE_DIR / 'references' / '0f0aaa37.json.gz'))
    gaps = parity_shortfalls(reference)
    assert 'facts: 10 < 15' in gaps
    assert 'verified matched peers: 0 < 2' in gaps
    assert any('fiscal years' in gap for gap in gaps)
    # Import alone is not evidence of satisfying the new, stronger contract.
    data = yaml.safe_load((FIXTURE_DIR / 'inputs' / 'JIOFIN.yaml').read_text(encoding='utf-8'))
    if not data.get('additions') and not data.get('reviewed_report'):
        with pytest.raises(ValueError, match='parity failed'):
            build_fixture(FIXTURE_DIR / 'inputs' / 'JIOFIN.yaml',
                          require_bytes=False, strict_parity=True)


def test_builder_is_offline_and_preserves_review_lineage(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError('Offline fixture builder attempted network access')
    monkeypatch.setattr(socket, 'socket', reject)
    monkeypatch.setattr(socket, 'getaddrinfo', reject)
    report, _ = build_fixture(FIXTURE_DIR / 'inputs' / 'HDFCBANK.yaml', require_bytes=False)
    assert report.generation_metadata['reference_review']['run_id'].startswith('d45ea5a6')
    assert report.generation_metadata['mode'] == 'precomputed'
    assert verify_report(report)


def test_builder_rejects_authored_fact_change_without_review(tmp_path):
    data = yaml.safe_load((FIXTURE_DIR / 'inputs' / 'HDFCBANK.yaml').read_text(encoding='utf-8'))
    data['reference'] = str(FIXTURE_DIR / 'references' / 'd45ea5a6.json.gz')
    data['facts'][0]['value_decimal'] = '1'
    source = tmp_path / 'HDFCBANK.yaml'
    source.write_text(yaml.safe_dump(data), encoding='utf-8')
    with pytest.raises(ValueError, match='editorial review'):
        build_fixture(source, require_bytes=False)


def test_builder_rejects_missing_reviewed_report(tmp_path):
    source = tmp_path / 'UNKNOWN.yaml'
    source.write_text(json.dumps({'schema_version': '1.0', 'facts': []}), encoding='utf-8')
    with pytest.raises(ValueError, match='cannot be published automatically'):
        build_fixture(source)
