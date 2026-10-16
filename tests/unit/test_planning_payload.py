from copy import deepcopy

from signal_research.research.planning import angle_planning_payload


def test_planner_uses_one_reporting_lane_and_preserves_formula_ids_and_bindings():
    payload = {'facts': [dict(id=i, metric_key=metric, scope=scope, period_end='2026-03-31',
        definition_id=metric + '_reported', value_decimal='100') for i, metric, scope in
        [('a','revenue','standalone'), ('b','net_profit','standalone'), ('c','revenue','consolidated')]],
        'calculations': [dict(id='ratio', input_fact_ids=['b','a'], output_value='20', unit='percent',
            input_bindings=[dict(id=i, role=role, value='100', scope='standalone') for i, role in [('b','numerator'),('a','denominator')]]),
            dict(id='other', input_fact_ids=['c'], output_value='10', unit='percent', input_bindings=[])],
        'compatible_research_lanes': [dict(fact_ids=['a','b'],calculation_ids=['ratio']),
                                      dict(fact_ids=['c'],calculation_ids=['other'])],
        'historical_series': [dict(observations=[dict(fact_id='a'),dict(fact_id='c')])],
        'passages': [{'id': 'counterargument', 'text': 'Independent context retained'}]}
    original = deepcopy(payload)
    result = angle_planning_payload(payload, {'key':'segment_dependency','metrics':['revenue','net_profit']})
    assert [f['id'] for f in result['facts']] == ['a','b']
    assert result['calculations'][0]['input_fact_ids'] == ['b','a']
    assert result['calculations'][0]['input_bindings'] == [{'id':'b','role':'numerator'},{'id':'a','role':'denominator'}]
    assert result['facts'][0]['definition_id'] == 'revenue_reported'
    assert result['historical_series'][0]['observations'] == [{'fact_id':'a'}]
    assert result['passages'] == original['passages'] and payload == original
