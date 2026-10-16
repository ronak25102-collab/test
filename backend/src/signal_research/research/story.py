"""Observed events and bounded onset estimates; no inferred causal dates."""
import calendar
from datetime import date
from decimal import Decimal

from signal_research.research.history import comparable_series


def quarter_ends(cutoff, count=12):
    ends, year, month = [], cutoff.year, (cutoff.month - 1) // 3 * 3 + 3
    while len(ends) < count:
        end = date(year, month, calendar.monthrange(year, month)[1])
        if end <= cutoff:
            ends.append(end)
        month -= 3
        if month <= 0:
            year, month = year - 1, 12
    return ends


def timeline_story(facts, calculations, passages, documents, breaks):
    by_passage, by_doc = {p.id: p for p in passages}, {d.id: d for d in documents}
    events, onsets, seen = [], [], set()
    for series in comparable_series(facts):
        observations, changes = series['observations'], []
        for index, observation in enumerate(observations):
            passage = by_passage.get(observation['passage_id'])
            if not passage or passage.document_id not in by_doc:
                continue
            previous = observations[index - 1] if index else None
            calc = next((c for c in calculations if previous and c.input_fact_ids == [observation['fact_id'], previous['fact_id']]
                         and c.formula_id in {'period_change', 'change_pp', 'yoy_growth'}), None)
            if calc:
                changes.append((observation, calc))
            if observation['fact_id'] in seen:
                continue
            seen.add(observation['fact_id'])
            events.append({'date': str(observation['period_end']), 'metric': series['metric'], 'scope': series['scope'],
                'fact_id': str(observation['fact_id']), 'passage_id': str(passage.id),
                'source_id': str(passage.document_id), 'source_url': str(by_doc[passage.document_id].canonical_url),
                'value': str(observation['value']), 'unit': series['unit'],
                'calculation_id': str(calc.id) if calc else None, 'change': str(calc.output_value) if calc else None,
                'change_unit': calc.unit if calc else None,
                'what_changed': series['metric'].replace('_', ' ') + (' changed relative to the preceding comparable observation.' if calc else ' was disclosed for this reporting date.'),
                'why_it_matters': 'Tests the observed relationship across time; this measurement does not establish its cause.'})
        if series['cadence'] != 'quarterly':
            continue
        onset = None
        for (_, a), (current, b) in zip(changes, changes[1:]):
            if any(e['start'] < str(current['period_end']) <= e['end'] for e in breaks):
                continue
            if a.output_value * b.output_value < 0 or abs(b.output_value - a.output_value) >= Decimal('5'):
                onset = {'date': str(current['period_end']), 'fact_id': str(current['fact_id']),
                    'calculation_ids': [str(a.id), str(b.id)], 'passage_id': str(current['passage_id']),
                    'confidence': 'Moderate' if len(observations) >= 4 else 'Low',
                    'reason': 'First observed quarterly sign reversal or slope change of at least five percentage points; bounded to the observed series, not causal onset.'}
                break
        onsets.append({'metric': series['metric'], 'scope': series['scope'], 'estimate': onset,
            'missing': [] if onset else ['Earlier and subsequent consecutive quarterly disclosures with the same definition and scope, showing a direction reversal or slope change beyond the declared threshold.']})
    return {'events': sorted(events, key=lambda e: (e['date'], e['metric'])), 'breaks': breaks, 'onsets': onsets,
        'missing': [] if onsets else ['At least three consecutive verified quarter ends with matching metric, definition, scope and duration; annual endpoints cannot establish quarterly onset.']}
