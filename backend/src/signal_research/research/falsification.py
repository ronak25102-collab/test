"""Near-term observable tests with empirically estimated, explicitly uncertain filing dates."""
import calendar
from datetime import date, timedelta
from statistics import median

from signal_research.research.story import quarter_ends


def filing_cadence(facts, passages, documents, cutoff):
    by_passage = {p.id: p for p in passages}
    samples = []
    for document in documents:
        if not document.published_at or not document.document_type.startswith('issuer'):
            continue
        periods = [f.period_end for f in facts if f.period_end and f.passage_id in by_passage
                   and by_passage[f.passage_id].document_id == document.id]
        if not periods:
            continue
        period = max(periods)
        lag = (document.published_at.date() - period).days
        if period in quarter_ends(cutoff, 20) and 0 <= lag <= 120:
            samples.append({'period_end': str(period), 'published': str(document.published_at.date()),
                            'lag_days': lag, 'document_id': str(document.id)})
    # Multiple copies of one disclosure are not multiple cadence observations.
    unique = {s['period_end']: s for s in samples}
    lag = int(median([s['lag_days'] for s in unique.values()])) if len(unique) >= 2 else None
    periods = sorted({f.period_end for f in facts if f.period_end})
    next_end = None
    if periods:
        anchor = periods[-1]
        month = ((anchor.month - 1) // 3 + 1) * 3 + 3
        year = anchor.year
        if month > 12:
            year, month = year + 1, month - 12
        next_end = date(year, month, calendar.monthrange(year, month)[1])
        while lag is not None and next_end + timedelta(days=lag) <= cutoff:
            month, year = next_end.month + 3, next_end.year
            if month > 12:
                year, month = year + 1, month - 12
            next_end = date(year, month, calendar.monthrange(year, month)[1])
    return {'next_quarter_end': str(next_end) if next_end else None,
            'expected_disclosure_date': str(next_end + timedelta(days=lag)) if next_end and lag is not None else None,
            'estimated_lag_days': lag, 'confidence': 'Moderate' if lag is not None else 'Unknown',
            'samples': list(unique.values()), 'missing': [] if lag is not None else ['Two source-owned quarterly filing dates linked to their actual latest reporting periods.'],
            'note': 'Cadence estimate, not an announced or guaranteed publication date.'}


def observable_tests(facts, calculations, passages, documents, cutoff, now_check):
    cadence = filing_cadence(facts, passages, documents, cutoff)
    usable = [c for c in calculations if c.available and c.output_value is not None and c.formula_id in {'growth_gap', 'change_pp', 'deposit_borrowing_mix_change', 'period_change'}]
    c = max(usable, key=lambda c: c.period or '') if usable else next((c for c in calculations if c.available), None)
    tests = []
    if c:
        tests.append({'kind': 'next_quarter', 'metric': c.formula_id, 'operator': '<=' if c.output_value > 0 else '>=',
            'threshold': '0', 'unit': c.unit, 'calculation_id': str(c.id), 'fact_ids': [str(i) for i in c.input_fact_ids],
            'window': cadence['next_quarter_end'], 'expected_disclosure_date': cadence['expected_disclosure_date'],
            'source_type': 'Issuer quarterly results with matching scope, definition and duration', 'checkable_now': False,
            'status': 'pending', 'interpretation': 'A comparable reversal of this observed direction challenges its continuation; it does not erase the historical measurement.'})
        tests.append({'kind': 'next_annual', 'metric': c.formula_id, 'operator': tests[0]['operator'], 'threshold': '0',
            'unit': c.unit, 'calculation_id': str(c.id), 'fact_ids': [str(i) for i in c.input_fact_ids],
            'window': 'Next annual disclosure after the cutoff', 'source_type': 'Issuer annual financial statements and reconciliation notes',
            'checkable_now': False, 'status': 'pending', 'interpretation': 'Secondary test of the same observed direction over a longer reporting window.'})
    tests.append({'kind': 'current_reconciliation', 'metric': 'material structural reconciliation disclosed',
        'operator': '=', 'threshold': '1', 'unit': 'documented event', 'checkable_now': True,
        'source_type': 'Original issuer merger, acquired-balance, restatement or reclassification notes',
        'window': str(cutoff), **now_check})
    return {'cadence': cadence, 'conditions': tests}
