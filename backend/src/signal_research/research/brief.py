"""Expose submission completeness without converting rejected leads into findings."""
from uuid import uuid5

from signal_research.domain.enums import DatePrecision
from signal_research.domain.schemas import TimelineEvent
from signal_research.research.history import comparable_series


def observation_timeline(run_id, facts, passages, documents):
    by_passage = {p.id: p for p in passages}
    by_document = {d.id: d for d in documents}
    events = []
    for fact in sorted(facts, key=lambda f: (str(f.period_end), f.metric_key, str(f.id))):
        passage = by_passage.get(fact.passage_id)
        document = by_document.get(passage.document_id) if passage else None
        if not fact.period_end or not document:
            continue
        events.append(TimelineEvent(
            id=uuid5(run_id, f'observed:{fact.id}'), event_date=fact.period_end,
            date_precision=DatePrecision.DAY, published_at=document.published_at,
            description=f'{fact.metric_key}: {fact.value_decimal} {fact.unit_normalized} ({fact.scope.value}; observed reporting date, not trend onset)',
            source_ids=[document.id],
        ))
    return events


def submission_checklist(report):
    discovery = report.discoveries[0] if report.discoveries else None
    series = report.source_coverage.get('historical_series', [])
    dates = {f.period_end for f in report.facts if f.period_end}
    timeline_note = (f'{len(dates)} observed reporting dates; onset is not established by snapshots alone.'
                     if dates else 'No verified reporting dates.')
    items = [
        ('discovery', 'The Discovery', bool(discovery), 'A reviewed non-obvious sentence.'),
        ('significance', 'Why It Matters', bool(discovery and 3 <= len(discovery.why_it_matters) <= 5), 'Three to five verified significance statements.'),
        ('evidence', 'Evidence', bool(discovery), 'Independent relevant support must back the finding; retrieved families alone do not qualify.'),
        ('timeline', 'Timeline', bool(discovery and discovery.timeline_event_ids), timeline_note),
        ('numbers', 'Numbers', bool(report.calculations), f'{len(report.calculations)} independently reproducible calculations; arithmetic alone is not a discovery.'),
        ('counterargument', 'Counterargument', bool(discovery and discovery.counterargument.search_attempted), 'An active opposing search and a reviewed strongest alternative.'),
        ('falsification', 'Falsification Condition', bool(discovery and discovery.falsification_rules), 'An observable condition, observation window and expected source.'),
        ('strength', 'Evidence Strength', bool(discovery and discovery.strength_rationale), 'A justified Strong, Moderate or Weak rating for a published finding.'),
    ]
    checks = [{'key': key, 'label': label, 'status': 'complete' if complete else 'missing', 'reason': reason}
              for key, label, complete, reason in items]
    temporal = report.generation_metadata.get('temporal_reasoning', {})
    if discovery and temporal.get('onset_status') == 'unknown':
        claim = next((c for c in report.claims if str(c.id) == str(temporal.get('claim_id'))), None)
        cited = {link.passage_or_fact_id for link in claim.evidence_links} if claim else set()
        cited.update(i for c in report.calculations if claim and c.id in claim.calculation_ids for i in c.input_fact_ids)
        periods = comparable_series([f for f in report.facts if f.id in cited])
        developed = any(series['comparable_periods'] >= 3 for series in periods)
        checks[3]['status'] = 'complete' if developed else 'limited'
        checks[3]['reason'] = ('Reviewed development across at least three comparable reporting dates; true onset outside the observed window is not claimed.' if developed else
                               timeline_note + ' The verified narrative explicitly leaves emergence unresolved.')
    return {
        'version': '1.0', 'discovery_ready': all(item['status'] == 'complete' for item in checks),
        'items': checks,
        'historical_coverage': {
            'target': 'Five-year context; quarterly detail where available. A target is not verified coverage.',
            'longest_comparable_series': max((s['comparable_periods'] for s in series), default=0),
            'observed_dates': sorted(str(d) for d in dates),
        },
    }


def compatible_candidate(hypothesis, facts, calculations):
    """Reject comparisons across issuer/scope/segment/currency boundaries before search."""
    selected = set(hypothesis.fact_ids)
    selected.update(i for c in calculations if c.id in hypothesis.calculation_ids for i in c.input_fact_ids)
    bound = [f for f in facts if f.id in selected]
    for attribute in ('entity_id', 'scope', 'segment'):
        if len({str(getattr(f, attribute)) for f in bound}) > 1:
            if attribute == 'segment':
                from signal_research.finance.calculations import calculate, numeric_fact
                from signal_research.finance.segments import SEGMENT_FORMULAS
                by_id = {f.id:f for f in facts}
                covered = set()
                for c in calculations:
                    if c.id in hypothesis.calculation_ids and c.available and c.formula_id in SEGMENT_FORMULAS and set(c.input_fact_ids) <= by_id.keys():
                        result = calculate(c.formula_id, [numeric_fact(by_id[i]) for i in c.input_fact_ids])
                        if result.available and result.output_value == c.output_value:
                            covered.update(c.input_fact_ids)
                if covered and all(f.id in covered for f in bound if f.segment != 'all'):
                    continue  # Only explicit, reproduced component/total reconciliation.
            return False, f'Candidate mixes {attribute}; separately reported boundaries need a sourced reconciliation before comparison.'
    currencies = {f.currency for f in bound if f.currency}
    if len(currencies) > 1:
        return False, 'Candidate mixes currencies without a verified conversion.'
    return True, ''


def research_lanes(facts, calculations):
    lanes = {}
    for fact in facts:
        key = (str(fact.entity_id), fact.scope.value, fact.segment)
        lanes.setdefault(key, []).append(fact)
    result = [{'entity_id': key[0], 'scope': key[1], 'segment': key[2],
             'fact_ids': [f.id for f in values],
             'calculation_ids': [c.id for c in calculations if set(c.input_fact_ids) <= {f.id for f in values}],
             'rule': 'Compare within this reporting boundary. Stock and flow periods still require explicit alignment.'}
            for key, values in lanes.items()]
    by_id = {f.id:f for f in facts}
    for c in calculations:
        if c.available and c.formula_id == 'segment_dependency_gap':
            first = by_id[c.input_fact_ids[0]]
            result.append({'entity_id':str(first.entity_id), 'scope':first.scope.value,
                'segment':'reconciled components: '+first.segment, 'fact_ids':list(c.input_fact_ids),
                'calculation_ids':[other.id for other in calculations if set(other.input_fact_ids) <= set(c.input_fact_ids)],
                'rule':'Named segment components reconcile exactly to disclosed segment totals; no unrestricted segment mixing.'})
    return result
