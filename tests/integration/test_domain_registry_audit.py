import json
from uuid import uuid4

from signal_research.domain.enums import RunMode
from signal_research.retrieval.issuer_identity import ISSUER_REFERENCE_POLICY


def test_legacy_third_party_domains_are_quarantined_with_a_backup(store, tmp_path):
    company = store.search_companies('BSE')[0]
    source = uuid4()
    store.add_verified_issuer_domains(company.id, ['trustee.example', 'different.example', 'www'], source)
    store.bootstrap()
    repaired = store.get_company(company.id)
    assert repaired.verified_ir_domains == ['bseindia.com']
    assert source in repaired.identity_source_ids
    backups = list((tmp_path / 'exports/domain-audits').glob('registry-before-*.json'))
    assert len(backups) == 1
    record = json.loads(backups[0].read_text())['changes'][0]
    assert record['before'] == ['bseindia.com', 'trustee.example', 'different.example', 'www']
    assert record['after'] == ['bseindia.com']


def test_current_proof_and_domain_are_saved_together_and_survive_startup(store):
    from datetime import date

    company = store.search_companies('HDFCBANK')[0]
    run_id = store.create_run(company, date(2026, 10, 14), RunMode.LIVE)
    source = uuid4()
    proof = {'reference_policy': ISSUER_REFERENCE_POLICY, 'company_id': str(company.id),
             'document_id': str(source), 'domains': ['verified-new.example']}
    store.add_verified_issuer_domains(company.id, proof['domains'], source, run_id=run_id, proof=proof)
    assert len(store.artifacts(run_id, 'issuer_domain_verification')) == 1
    store.bootstrap()
    assert 'verified-new.example' in store.get_company(company.id).verified_ir_domains


def test_a_different_run_company_cannot_supply_a_domain_proof(store):
    from datetime import date

    import pytest

    owner = store.search_companies('HDFCBANK')[0]
    other = store.search_companies('BSE')[0]
    run_id = store.create_run(other, date(2026, 10, 14), RunMode.LIVE)
    source = uuid4()
    proof = {'reference_policy': ISSUER_REFERENCE_POLICY, 'company_id': str(owner.id),
             'document_id': str(source), 'domains': ['wrong.example']}
    with pytest.raises(ValueError, match='does not bind'):
        store.add_verified_issuer_domains(owner.id, proof['domains'], source, run_id=run_id, proof=proof)
    assert 'wrong.example' not in store.get_company(owner.id).verified_ir_domains


def test_saved_reference_audit_restores_only_owned_sites_from_original_hashed_sources(store, settings):
    import hashlib
    import importlib.util
    from datetime import date
    from pathlib import Path

    path = Path(__file__).parents[2] / 'scripts/audit_issuer_domains.py'
    spec = importlib.util.spec_from_file_location('domain_audit_script', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    company = store.search_companies('HDFCBANK')[0]
    run_id = store.create_run(company, date(2026, 10, 14), RunMode.LIVE)
    raw = b'<p>HDFC Bank</p><a href="https://verified-new.example">Company website</a>'
    digest = hashlib.sha256(raw).hexdigest()
    folder = settings.data_dir / 'raw'
    folder.mkdir(exist_ok=True)
    (folder / (digest + '.html')).write_bytes(raw)
    source = uuid4()
    store.artifact(run_id, 'issuer_domain_verification', {'source_url': 'https://nseindia.com/directory',
        'document_id': str(source), 'domains': ['verified-new.example', 'registrar.example'], 'content_hash': digest})
    dry = module.audit_saved_references(store, settings)
    assert dry[0]['accepted_domains'] == ['verified-new.example'] and not dry[0]['applied']
    assert 'verified-new.example' not in store.get_company(company.id).verified_ir_domains
    applied = module.audit_saved_references(store, settings, apply=True)
    assert applied[0]['applied']
    store.bootstrap()
    assert 'verified-new.example' in store.get_company(company.id).verified_ir_domains
    assert 'registrar.example' not in store.get_company(company.id).verified_ir_domains
