from types import SimpleNamespace
from uuid import uuid4

from signal_research.domain.enums import Profile
from signal_research.research.angles import route_angles


def test_nbfc_and_insurer_angles_are_selected_by_schema_without_deposits():
    def route(profile, metrics):
        company = SimpleNamespace(legal_name='Example Financial Services', business_profiles=[profile])
        facts = [SimpleNamespace(id=uuid4(), metric_key=m) for m in metrics]
        return route_angles(company, facts, [])
    nbfc = route(Profile.NBFC, ['aum', 'bank_borrowings', 'borrowings', 'stage3_ratio'])
    assert nbfc[0]['coverage_groups'] == 2
    assert 'funding_mix' not in [a['key'] for a in nbfc]
    life = route(Profile.LIFE_INSURER, ['ape', 'vnb', 'persistency_13m'])
    assert life[0]['key'] == 'insurance_distribution' and life[0]['coverage_groups'] == 2
