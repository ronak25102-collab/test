from decimal import Decimal
from uuid import uuid4

from signal_research.domain.schemas import Fact
from signal_research.research.peers import compare_peers, peer_model_context


def test_peer_comparison_requires_two_matching_issuers_and_reproduces_growth():
    def facts(entity, growth):
        return [Fact(id=uuid4(), entity_id=entity, metric_key='aum', value_decimal=value,
                     currency='INR', unit_normalized='INR_crore', period_end=f'{year}-03-31',
                     period_type='instant', scope='standalone', definition_id='aum_as_reported_v1',
                     passage_id=uuid4(), status='verified') for year, value in [(2024, 100), (2025, 100 + growth)]]
    target, a, b = facts(uuid4(), 40), facts(uuid4(), 10), facts(uuid4(), 20)
    assert compare_peers(target, a)['status'] == 'inconclusive'
    row = compare_peers(target, a + b)['comparisons'][0]
    assert Decimal(row['peer_median']) == 15 and Decimal(row['gap']) == 25
    assert row['classification'] == 'company-specific'
    b[1] = b[1].model_copy(update={'scope': 'consolidated'})
    assert compare_peers(target, a + b)['status'] == 'inconclusive'


def test_peer_prompt_excludes_unverified_reports_and_bounds_exact_used_passages():
    import json
    bundle = {'company': {'legal_name': 'Synthetic Peer'},
        'facts': [{'id': 'f1', 'passage_id': 'p1', 'value_raw': '100'}],
        'passages': [{'id': 'p1', 'document_id': 'd1', 'text': 'Standalone assets 100 INR crore. ' + 'Original page text. ' * 30000},
                     {'id': 'p2', 'document_id': 'd1', 'text': 'Unverified narrative 999999'}],
        'documents': [{'id': 'd1', 'canonical_url': 'https://peer.example/results', 'title': 'Results', 'origin_family_id': 'issuer:peer'}]}
    benchmark = {'status': 'inconclusive', 'comparisons': [], 'sources': [bundle]}
    assert peer_model_context(benchmark)['evidence'] == []
    benchmark['comparisons'] = [{'peers': {'peer': {'fact_ids': ['f1']}}}]
    benchmark['status'] = 'verified'
    context = peer_model_context(benchmark)
    assert len(json.dumps(context)) < 8000
    assert '999999' not in json.dumps(context)
    assert '100' in context['evidence'][0]['passages'][0]['text']
    assert len(bundle['passages'][0]['text']) > 500000


def test_peer_query_uses_source_labels_and_month_not_internal_names_or_iso_dates():
    from types import SimpleNamespace

    from signal_research.research.peers import peer_search_query
    facts = [Fact(id=uuid4(), entity_id=uuid4(), metric_key=key, value_decimal=100,
        currency='INR', unit_normalized='INR_crore', period_end='2026-06-30',
        period_type='instant', scope='consolidated', definition_id=key+'_as_reported_v1',
        passage_id=uuid4(), status='verified') for key in ['advances_as_reported','deposits']]
    peer = SimpleNamespace(legal_name='Quartz Bank')
    query = peer_search_query(peer, facts)
    assert query.startswith('"Quartz Bank" financial results')
    assert 'June 2026' in query and 'consolidated' in query and 'advances' in query
    assert 'as reported' not in query and '2026-06-30' not in query
    broad = peer_search_query(peer, facts, broad=True)
    assert broad == '"Quartz Bank" financial results June 2026'
