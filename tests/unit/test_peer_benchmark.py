from decimal import Decimal
from uuid import uuid4

from signal_research.domain.schemas import Fact
from signal_research.research.peers import compare_peers


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
