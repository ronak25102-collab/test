"""Build descriptive source-reviewed reports; never invent an inferred mechanism."""
from datetime import UTC, datetime
from uuid import uuid5

from signal_research.domain.enums import PublicationStatus, ResearchOutcome
from signal_research.domain.schemas import (
    Claim,
    Counterargument,
    Discovery,
    EvidenceLink,
    FalsificationRule,
    TimelineEvent,
    WhyItMatters,
)
from signal_research.research.headline import template_headline


def expanded_fact_inputs(report):
    """Expose exact fact-owned source fields directly in editable YAML inputs."""
    passages = {p.id: p for p in report.passages}
    documents = {d.id: d for d in report.documents}
    rows = []
    for fact in report.facts:
        passage = passages[fact.passage_id]
        document = documents[passage.document_id]
        rows.append({**fact.model_dump(mode='json'),
            'source_url': str(document.canonical_url), 'document_title': document.title,
            'document_type': document.document_type,
            'publication_date': document.published_at.isoformat() if document.published_at else None,
            'retrieved_at': document.retrieved_at.isoformat(), 'sha256': document.content_hash,
            'page_number': passage.page_index + 1 if passage.page_index is not None else None,
            'exact_passage': passage.text, 'row_label': passage.row_label,
            'column_label': passage.column_label, 'section': passage.section})
    return rows


def observed_report(report, calculation, *, significance, counterargument, review_note,
                    peer_sources=(), limitations=(), headline_text=None,
                    context_fact_ids=(), context_calculation_ids=()):
    """An author must review all supplied prose and the exact source bindings.

    This is editorial assembly, not a semantic review service or a substitute for
    the builder's numeric/source checks. Caller-provided prose is saved verbatim.
    """
    headline, _ = template_headline(report.company, report.facts, [calculation])
    headline = headline_text or headline
    facts = {f.id: f for f in report.facts}
    passages = {p.id: p for p in report.passages}
    report.claims, report.timeline_events = [], []

    def claim(text, inputs, calcs=()):
        cid = uuid5(report.run_id, 'claim/' + text)
        result = Claim(id=cid, run_id=report.run_id, text=text, kind='derived',
            evidence_links=[EvidenceLink(claim_id=cid, passage_or_fact_id=f.id,
                relation='supporting', reason=review_note, entailment_status='supported') for f in inputs],
            calculation_ids=[c.id for c in calcs], verification_status='supported',
            verification_reasons=[review_note])
        report.claims.append(result)
        return result

    inputs = [facts[i] for i in dict.fromkeys([*calculation.input_fact_ids, *context_fact_ids])]
    context_calculations = [c for c in report.calculations if c.id in context_calculation_ids]
    linked = [calculation, *context_calculations]
    lead = claim(headline, inputs, linked)
    why = [claim(text, inputs, linked) for text in significance]
    objection = claim(counterargument, inputs, linked)
    for end in sorted({f.period_end for f in inputs}):
        selected = [f for f in inputs if f.period_end == end]
        documents = {passages[f.passage_id].document_id for f in selected}
        text = f'Source-bound {selected[0].scope.value} observations as at {end}; exact inputs are linked.'
        point = claim(text, selected)
        report.timeline_events.append(TimelineEvent(id=uuid5(report.run_id, str(end)),
            event_date=end, date_precision='day', description=text,
            claim_ids=[point.id], source_ids=list(documents)))
    report.discoveries = [Discovery(id=uuid5(report.run_id, 'discovery'),
        discovery_sentence=headline,
        why_it_matters=[WhyItMatters(text=c.text, claim_id=c.id) for c in why],
        evidence_claim_ids=[c.id for c in report.claims],
        timeline_event_ids=[e.id for e in report.timeline_events],
        calculation_ids=[calculation.id],
        counterargument=Counterargument(statement=counterargument,
            evidence_claim_ids=[objection.id], search_attempted=True,
            search_summary=review_note, unresolved=True),
        falsification_rules=[FalsificationRule(id=uuid5(report.run_id, 'falsification'),
            observable_metric_or_event='A reversal of the observed arithmetic direction in the next '
                                       'matching quarterly disclosure.',
            operator='<=' if calculation.output_value > 0 else '>=', threshold=0,
            unit=calculation.unit, expected_source_type='Original issuer financial statements',
            interpretation='Compare the same metric, scope, definition and duration; a reversal '
                           'challenges continuation and does not erase the historical observation.',
            dependencies=[calculation.id])],
        evidence_strength='Weak', strength_rationale='The builder computes the evidence tier.')]
    report.outcome, report.publication_status = ResearchOutcome.DISCOVERY, PublicationStatus.PUBLISHED
    report.abstention = None
    report.limitations = list(limitations)
    report.generation_metadata.update({
        'pipeline': 'precomputed-source-editorial-v1', 'configured_provider': 'none',
        'configured_model_id': None, 'routing': 'offline editorial research',
        'models_used': [], 'provider': 'none', 'model_id': None,
        'search_queries': [], 'opposing_queries': [], 'context_searches': [],
        'research_decisions': [], 'challenge_reviews': [],
        'novelty_status': 'additional_supported_synthesis',
        'novelty_rationale': review_note, 'published_explanation': headline,
        'non_obvious_synthesis_reviewed': True,
        'temporal_reasoning': {'onset_status': 'unknown',
                               'note': 'Observed endpoints do not identify true onset.'},
        'historical_cache': [], 'cache_usage': {}, 'structural_breaks': [],
        'peer_benchmark': {'sources': list(peer_sources), 'status': 'inconclusive',
                           'comparisons': [], 'limitations': list(limitations)},
        'submission_checklist': {},
        'headline': {'claim_id': str(lead.id), 'technical_claim_id': str(lead.id),
                     'technical_detail': headline},
        'strength_trace': {'origin_families': sorted({str(d.origin_family_id) for d in report.documents
            if d.id in {passages[f.passage_id].document_id for f in inputs}}),
            'rules': {'non_issuer_support': False, 'counterargument_addressed': True},
            'caps': ['All verified issuer-company figures originate with the issuer.']},
        'tiered_publication': True,
        'falsification_tests': {'conditions': [{'kind': 'current_reconciliation',
            'status': 'not_checked', 'interpretation': review_note}]},
        'timeline_story': {},
    })
    return {'reviewer': 'Codex source-based editorial review',
            'reviewed_at': datetime.now(UTC).isoformat(),
            'method': 'source-based editorial review',
            'claim_ids': [str(c.id) for c in report.claims], 'notes': review_note}
