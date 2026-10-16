from datetime import UTC, datetime
from uuid import uuid4

from signal_research.research.entity_resolver import resolve
from signal_research.research.universe import LISTED_URL


def test_refresh_enriches_matching_seed_identity_instead_of_skipping_it(store, monkeypatch):
    company = store.search_companies('BSE')[0]
    assert not company.isin
    calls = []
    def refresh(**kwargs):
        calls.append(kwargs)
        return {'id': str(uuid4()), 'source_url': LISTED_URL,
                'fetched_at': datetime.now(UTC).isoformat(), 'content_hash': 'synthetic-directory',
                'constituents': [{'SYMBOL': company.symbols[0], 'NAME OF COMPANY': company.legal_name,
                                  'ISIN NUMBER': 'INE000A01000'}], 'financial_constituents': []}
    monkeypatch.setattr('signal_research.research.universe.refresh_universe', refresh)
    resolved = resolve(store, company.symbols[0], refresh=True)
    assert resolved.company.id == company.id
    assert resolved.company.isin == 'INE000A01000'
    assert calls == [{'listed': True}]
    resolve(store, company.symbols[0], refresh=True)
    assert len(calls) == 1


def test_unavailable_identifier_directory_preserves_known_entity_without_inventing_isin(store, monkeypatch):
    def unavailable(**kwargs):
        raise TimeoutError('directory unavailable')
    monkeypatch.setattr('signal_research.research.universe.refresh_universe', unavailable)
    resolved = resolve(store, 'BSE', refresh=True)
    assert resolved.company and not resolved.company.isin
