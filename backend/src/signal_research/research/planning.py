"""Reduce duplicated planning context while retaining complete review evidence."""
from copy import deepcopy


def angle_planning_payload(payload, angle):
    from .angles import ANGLES

    result = deepcopy(payload)
    relevant = {str(f['id']) for f in result['facts'] if f['metric_key'] in angle['metrics']}
    lanes = []
    groups = next((a.groups for a in ANGLES if a.key == angle['key']), ())
    for lane in result.get('compatible_research_lanes', []):
        ids = set(map(str, lane['fact_ids'])) & relevant
        facts = [f for f in result['facts'] if str(f['id']) in ids]
        calculations = [c for c in result['calculations'] if set(map(str, c['input_fact_ids'])) <= ids]
        if facts and calculations:
            metrics = {f['metric_key'] for f in facts}
            coverage = sum(bool(metrics & set(group)) for group in groups)
            lanes.append((coverage, len(calculations), len({f.get('period_end') for f in facts}), len(facts), ids))
    if lanes:
        # The planner investigates one reporting boundary, never mixed scopes.
        relevant = max(lanes, key=lambda lane: lane[:4])[4]
    result['facts'] = [f for f in result['facts'] if str(f['id']) in relevant]
    result['calculations'] = [c for c in result['calculations'] if set(map(str, c['input_fact_ids'])) <= relevant]
    for calculation in result['calculations']:
        # Roles + ordered fact IDs preserve the formula definition. The facts
        # above already carry values, periods, scope, segment and definitions.
        calculation['input_bindings'] = [{key: binding[key] for key in ('id', 'role')}
                                          for binding in calculation.get('input_bindings', [])]
    calculations = {str(c['id']) for c in result['calculations']}
    result['compatible_research_lanes'] = [lane | {
        'fact_ids': [i for i in lane['fact_ids'] if str(i) in relevant],
        'calculation_ids': [i for i in lane['calculation_ids'] if str(i) in calculations]}
        for lane in result.get('compatible_research_lanes', []) if set(map(str, lane['fact_ids'])) & relevant]
    for series in result.get('historical_series', []):
        series['observations'] = [o for o in series['observations'] if str(o['fact_id']) in relevant]
    result['historical_series'] = [s for s in result.get('historical_series', []) if s['observations']]
    result['research_angle'] = angle
    return result
