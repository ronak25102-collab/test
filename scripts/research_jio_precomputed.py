"""Author the Jio snapshot from the explicitly reviewed October 2026 sources.

Raw inputs below are transcribed disclosures, never formula outputs. Publication
calculations, source binding, tiering and verification remain in the builder.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pdfplumber
import pypdfium2 as pdfium
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend' / 'src'))

from signal_research.domain.schemas import (  # noqa: E402
    Calculation,
    Claim,
    Counterargument,
    Discovery,
    EvidenceLink,
    FalsificationRule,
    Passage,
    ResearchReport,
    SourceDocument,
    TimelineEvent,
    WhyItMatters,
)
from signal_research.extraction.models import ExtractedFactCandidate  # noqa: E402
from signal_research.extraction.validate import validate_candidate  # noqa: E402
from signal_research.finance.calculations import calculate, numeric_fact  # noqa: E402
from signal_research.precomputed.authoring import expanded_fact_inputs  # noqa: E402
from signal_research.precomputed.builder import FIXTURE_DIR, read_json  # noqa: E402
from signal_research.research.headline import template_headline  # noqa: E402


def identifier(text):
    return uuid5(NAMESPACE_URL, 'beyond/precomputed/jio/' + text)


def main():
    original = ResearchReport.model_validate(read_json(
        FIXTURE_DIR / 'references' / '0f0aaa37.json.gz'))
    report = original.model_copy(deep=True)
    report.run_id = identifier('october-2026-review')
    report.cutoff = date(2026, 10, 24)
    receipts = [json.loads(p.read_text(encoding='utf-8'))
                for p in (ROOT / 'data' / 'precomputed-sources').glob('*.receipt.json')]
    sources = {r['sha256']: r for r in receipts}
    docs, pages = {}, {}

    def source(digest, title, publication=None, origin='issuer:JIOFIN'):
        receipt = sources[digest]
        doc = SourceDocument(
            id=identifier(digest), canonical_url=receipt['url'],
            final_url=receipt['url_effective'], publisher='Jio Financial Services',
            origin_family_id=origin, title=title, document_type='issuer_filing',
            published_at=publication, retrieved_at=receipt['retrieved_at'],
            content_hash=digest, mime_type='application/pdf',
            local_object_key=receipt['local_object_key'],
            cutoff_eligibility_basis='publication_date' if publication else 'verified_retrieval',
        )
        reader = pdfium.PdfDocument(str(ROOT / receipt['local_object_key']))
        docs[digest], pages[digest] = doc, []
        for index in range(len(reader)):
            text = reader[index].get_textpage().get_text_range()
            passage = Passage(id=identifier(f'{digest}/page/{index}'),
                              document_id=doc.id, page_index=index,
                              text=text, extraction_method='pdfium',
                              section=None)
            pages[digest].append(passage)
        return doc

    annual26 = 'c6f8bd5102bbf752171d0ca06bf15350318485401f0754237b3d2f79e9311ee4'
    annual25 = '639ba7cbaeae620bc9e8c9a622641a8d201607012d8b0c363a030b9f5a7ce441'
    quarter2 = 'a4821ad657c1fb9756a569827885c2e4872c837bbf43cd8bb9fe6028e0870fb1'
    source(annual26, 'Jio Financial Services Annual Report FY 2025-26', '2026-08-03T00:00:00Z')
    source(annual25, 'Jio Financial Services Annual Report FY 2024-25')
    source(quarter2, 'Jio Financial Services Q2 and H1 FY27 results, October 15 2026',
           '2026-10-15T00:00:00Z')
    # Coordinate-aware extraction keeps decimal glyphs together on the scanned
    # exchange filing. Do not rewrite numerical text to satisfy a validator.
    for digest, numbers in [(quarter2, [5, 6]), (annual26, [86]), (annual25, [90])]:
        with pdfplumber.open(ROOT / sources[digest]['local_object_key']) as pdf:
            for number in numbers:
                passage = pages[digest][number - 1]
                passage.text = pdf.pages[number - 1].extract_text()
                passage.extraction_method = 'pdfplumber'
                if digest == quarter2:
                    # The rendered source uses the rupee glyph. Its embedded
                    # text layer maps that glyph incorrectly to "ii'".
                    passage.text = passage.text.replace("(ii' in crore)", '(₹ in crore)')
                    passage.text = passage.text.replace('(fin crore', '(₹ in crore')

    new_facts = []

    def fact(digest, page, metric, value, start, end, segment='all', *, entity=None):
        passage = pages[digest][page - 1]
        if digest in {quarter2, annual26, annual25}:
            # Explicit column association checked against the rendered table;
            # leave the original page text intact, including all other columns.
            period_label = 'Year Ended' if end.endswith('03-31') else 'Quarter Ended'
            source_date = date.fromisoformat(end).strftime('%d-%b-%Y')
            row = {'segment_revenue_total': 'Sub Total',
                   'segment_profit_total': 'Total Profit After Tax',
                   'revenue': 'Total revenue from operations',
                   'net_profit': ('Profit for the period/ year' if digest == quarter2
                                  else 'Profit for the year')}.get(metric, segment)
            bound = passage.model_copy(update={
                'id': identifier(f'{digest}/{page}/{metric}/{segment}/{start}/{end}'),
                'column_label': f'{period_label} {source_date}', 'row_label': row,
                'extraction_method': 'pdf_table',
            })
            report.passages.append(bound)
            passage = bound
        candidate = ExtractedFactCandidate(
            metric_key=metric, value_raw=value, unit_raw='INR crore', currency='INR',
            period_start=start, period_end=end, period_type='duration',
            scope='consolidated', segment=segment, passage_id=passage.id,
            extraction_confidence=1,
        )
        validation = validate_candidate(candidate, passage, entity or report.company.id,
                                        report.company.business_profiles[0])
        if validation.fact is None:
            raise ValueError(f'{metric} {segment} {end}: {validation.reason}')
        output = validation.fact
        if entity is None:
            new_facts.append(output)
        return output

    # PDF page 6: full component reconciliation, with the issuer's restated
    # comparable periods. Keep annual and quarterly durations separate.
    periods = [
        ('2026-07-01', '2026-09-30',
         ['521.42', '920.36', '287.55', '1,729.33'],
         ['238.70', '147.90', '(46.16)', '340.44']),
        ('2025-07-01', '2025-09-30',
         ['727.86', '301.08', '158.46', '1,187.40'],
         ['651.26', '75.68', '(31.90)', '695.04']),
        ('2025-04-01', '2026-03-31',
         ['1,523.80', '1,496.41', '657.35', '3,677.56'],
         ['1,222.84', '333.17', '4.89', '1,560.90']),
    ]
    groups = []
    for start, end, revenues, profits in periods:
        group = []
        for metric, values in [('segment_revenue', revenues), ('segment_profit', profits)]:
            for segment, value in zip(['Investing', 'Lending', 'Others', 'all'], values, strict=True):
                group.append(fact(quarter2, 6, metric + ('_total' if segment == 'all' else ''),
                                  value, start, end, segment))
        groups.append(group)
    for digest, page, years in [
        (annual26, 86, [(2026, '3,513.26', '1,560.90'), (2025, '2,042.91', '1,612.59')]),
        (annual25, 90, [(2024, '1,853.88', '1,604.55')]),
    ]:
        for year, revenue, profit in years:
            for metric, value in [('revenue', revenue), ('net_profit', profit)]:
                fact(digest, page, metric, value, f'{year-1}-04-01', f'{year}-03-31')
    for start, end, revenue, profit in [
        ('2026-07-01', '2026-09-30', '1,699.28', '340.44'),
        ('2025-07-01', '2025-09-30', '981.39', '695.04'),
    ]:
        for metric, value in [('revenue', revenue), ('net_profit', profit)]:
            fact(quarter2, 5, metric, value, start, end)
    report.documents.extend(docs.values())
    report.passages.extend(p for group in pages.values() for p in group)
    report.facts.extend(new_facts)

    def calculation(formula, inputs, period):
        result = calculate(formula, [numeric_fact(f) for f in inputs])
        if not result.available:
            raise ValueError(result.limitations)
        c = Calculation(id=identifier(f'{formula}/{period}/' + '/'.join(str(f.id) for f in inputs)),
                        formula_id=formula, formula_version=result.formula_version,
                        input_fact_ids=[f.id for f in inputs], output_value=result.output_value,
                        unit=result.unit, period=period, scope='consolidated',
                        comparability_checks=result.comparability_checks,
                        limitations=result.limitations)
        report.calculations.append(c)
        return c

    segment_calcs = []
    for group in groups:
        segment_calcs.append(calculation('segment_dependency_gap', group, str(group[0].period_end)))
        calculation('segment_revenue_share', group[:4], str(group[0].period_end))
        calculation('segment_profit_share', group[4:], str(group[0].period_end))
    for year in [2024, 2025, 2026]:
        pair = [next(f for f in new_facts if f.metric_key == metric and f.period_end.year == year
                     and f.period_end.month == 3) for metric in ['net_profit', 'revenue']]
        calculation('profit_margin', pair, str(pair[0].period_end))
    for metric in ['revenue', 'net_profit']:
        annual = sorted([f for f in new_facts if f.metric_key == metric and f.period_end.month == 3],
                        key=lambda f: f.period_end, reverse=True)
        for current, prior in zip(annual, annual[1:]):
            calculation('yoy_growth', [current, prior], str(current.period_end))
    peer_sources = []
    for symbol, name, digest, page, publication, values in [
        ('BAJAJFINSV', 'Bajaj Finserv',
         '4eea5d6345a94e67fb1091518ebb2d5b947692210fb5870067a6c962c4e33fd5',
         16, '2026-04-30T00:00:00Z', ['19,669.47', '17,557.64']),
        ('ABCAPITAL', 'Aditya Birla Capital',
         '6f414ca6e0d2358225a6ffff0c3450dde5909d138ea5d31ffe01c05b74153b28',
         9, '2026-05-04T00:00:00Z', ['3,863.80', '3,409.89']),
    ]:
        company = report.company.model_copy(update={
            'id': uuid5(NAMESPACE_URL, f'signal-research/company/{symbol}'),
            'legal_name': name, 'symbols': [symbol], 'aliases': [], 'isin': None,
            'verified_ir_domains': [], 'identity_source_ids': []})
        doc = source(digest, f'{name} audited consolidated FY26 results', publication,
                     origin=f'issuer:{symbol}')
        doc.publisher = name
        with pdfplumber.open(ROOT / sources[digest]['local_object_key']) as pdf:
            text = pdf.pages[page - 1].extract_text()
        if symbol == 'BAJAJFINSV':
            # Visually checked against the original rendered financial table.
            text = text.replace('ff In Clore)', '(₹ In Crore)')
        peer_passages, peer_facts = [], []
        for year, raw in zip([2026, 2025], values, strict=True):
            passage = Passage(id=identifier(f'{symbol}/net-profit/{year}'),
                document_id=doc.id, page_index=page - 1, text=text,
                row_label='Profit after tax' if symbol == 'BAJAJFINSV' else
                          'Profit After Tax for the period / year from Total Operations',
                column_label=f'Year ended 31 March {year}', extraction_method='pdf_table')
            candidate = ExtractedFactCandidate(metric_key='net_profit', value_raw=raw,
                unit_raw='INR crore', currency='INR', period_start=f'{year-1}-04-01',
                period_end=f'{year}-03-31', period_type='duration', scope='consolidated',
                passage_id=passage.id, extraction_confidence=1)
            validation = validate_candidate(candidate, passage, company.id,
                                            company.business_profiles[0])
            if validation.fact is None:
                raise ValueError(f'{symbol} {year}: {validation.reason}')
            peer_passages.append(passage)
            peer_facts.append(validation.fact)
        peer_sources.append({'company': company.model_dump(mode='json'),
            'documents': [doc.model_dump(mode='json')],
            'passages': [p.model_dump(mode='json') for p in peer_passages],
            'facts': [f.model_dump(mode='json') for f in peer_facts]})
    latest = groups[0]
    headline, headline_calculation = template_headline(report.company, latest, [segment_calcs[0]])
    report.claims, report.timeline_events = [], []

    def claim(text, inputs, calcs=(), passages=(), kind='derived'):
        cid = identifier('claim/' + text)
        links = [EvidenceLink(claim_id=cid, passage_or_fact_id=f.id,
                              relation='supporting', reason='Source table and exact column reviewed.',
                              entailment_status='supported') for f in inputs]
        links += [EvidenceLink(claim_id=cid, passage_or_fact_id=p.id,
                               relation='supporting', reason='Exact issuer disclosure reviewed.',
                               entailment_status='supported') for p in passages]
        c = Claim(id=cid, run_id=report.run_id, text=text, kind=kind,
                  evidence_links=links, calculation_ids=[c.id for c in calcs],
                  verification_status='supported',
                  verification_reasons=['Source-based editorial review of the original table, '
                                        'unit, period, issuer and calculation inputs.'])
        report.claims.append(c)
        return c

    lead = claim(headline, latest, [headline_calculation])
    a = claim('Investing contributes a larger share of reported segment profit than of gross '
              'segment revenue, even after Lending became the largest revenue segment in '
              'July–September 2026.', latest, [segment_calcs[0]])
    b = claim('The positive concentration gap appears in both retrieved September quarters '
              'and the intervening full financial year; this establishes repeated observations, '
              'not the date the relationship first began.',
              [f for group in groups for f in group], segment_calcs)
    c = claim('Gross segment revenue includes inter-segment revenue; reported segment profits '
              'must be reconciled using the issuer’s own totals. Investing includes financial '
              'investments and associates and joint ventures, so the arithmetic does not prove '
              'a sustainable operating margin.', latest, [segment_calcs[0]],
              [pages[quarter2][5]], kind='observed')
    counter = claim('Dividend timing, investment gains, joint venture results and changes in '
                    'business mix can explain a quarterly profit concentration. The current '
                    'filing says prior segment periods were compiled to match the current '
                    'presentation; the historical comparison therefore uses those restated '
                    'columns and does not establish causality.', latest, passages=[pages[quarter2][5]],
                    kind='observed')
    for group, calc in zip(groups, segment_calcs, strict=True):
        tclaim = claim('Investing profit share exceeded its gross revenue share in the '
                       f'issuer’s comparable period ending {group[0].period_end}.', group, [calc])
        report.timeline_events.append(TimelineEvent(
            id=identifier('timeline/' + str(group[0].period_end)),
            event_date=group[0].period_end, date_precision='day',
            published_at=docs[quarter2].published_at, description=tclaim.text,
            claim_ids=[tclaim.id], source_ids=[docs[quarter2].id]))
    report.discoveries = [Discovery(
        id=identifier('discovery'), discovery_sentence=headline,
        why_it_matters=[WhyItMatters(text=x.text, claim_id=x.id) for x in [a, b, c]],
        evidence_claim_ids=[x.id for x in report.claims],
        timeline_event_ids=[x.id for x in report.timeline_events],
        calculation_ids=[x.id for x in segment_calcs],
        counterargument=Counterargument(statement=counter.text,
            evidence_claim_ids=[counter.id], search_attempted=True,
            search_summary='Opened the FY25 and FY26 annual statements, the FY26 result '
                           'filing and the October 15 2026 quarterly filing. Checked '
                           'inter-segment eliminations and the restatement note; '
                           'the concentration persists across the comparable columns.',
            unresolved=True),
        falsification_rules=[FalsificationRule(id=identifier('falsification'),
            observable_metric_or_event='Investing profit share no longer exceeds its gross '
                                       'segment revenue share in the next comparable quarter.',
            operator='<=', threshold=0, unit='percentage_points',
            expected_source_type='Original consolidated issuer segment filing',
            interpretation='Test the quarter ending December 2026 with the same segment '
                           'definitions and component reconciliation; a reversal challenges '
                           'continuation without erasing the observed history.',
            dependencies=[segment_calcs[0].id])],
        evidence_strength='Weak', strength_rationale='Computed by the evidence tier function.')]
    report.historical_coverage = ('Verified annual revenue and net profit for FY24–FY26; '
        'source-restated segment periods for FY26 and September quarters FY26/FY27; '
        'original Q1 FY27 facts retained. FY22/FY23 and eight-quarter coverage are incomplete.')
    report.limitations = [
        'Matched peer context compares consolidated FY25–FY26 profit after tax before '
        'allocation to non-controlling interests. It does not benchmark Investing segment '
        'shares: different companies’ segment boundaries cannot be relabelled to force a match. '
        'Insurance mix, discontinued operations and differences in business maturity limit '
        'economic comparability even when the accounting metric and dates match.',
        'The observed concentration is descriptive; investment returns, dividend timing '
        'and joint venture contributions limit any operating-margin interpretation.',
        'Annual and quarterly durations are separate. True onset and a complete eight-quarter '
        'history are not established; pre-demerger FY22/FY23 operations are not assumed comparable.',
        'The September 2026 PDF is an opened mirror of the original issuer filing, '
        'and retains the issuer origin rather than creating an independent origin.',
    ]
    meta = report.generation_metadata
    meta['headline'] = {**original.generation_metadata.get('headline', {}),
                        'claim_id': str(lead.id), 'technical_claim_id': str(lead.id),
                        'technical_detail': headline}
    meta.update(pipeline='precomputed-source-editorial-v1', novelty_status='additional_supported_synthesis',
                novelty_rationale='Comparison of reconciled profit and gross revenue shares across '
                                  'the issuer’s restated periods rather than a restatement of growth.',
                non_obvious_synthesis_reviewed=True,
                strength_trace={'rules': {'non_issuer_support': False,
                                         'counterargument_addressed': True},
                                'origin_families': ['issuer:JIOFIN'],
                                'caps': ['All verified issuer-company figures originate with the issuer.']},
                peer_benchmark={'sources': peer_sources, 'comparisons': [], 'status': 'inconclusive',
                    'limitations': [report.limitations[0]]},
                research_decisions=[], challenge_reviews=[],
                falsification_tests={'conditions': [{'kind': 'current_reconciliation',
                    'status': 'supported', 'interpretation': 'Original current segment table '
                    'reconciles; its note explicitly recompiles prior periods to current presentation.',
                    'passage_ids': [str(pages[quarter2][5].id)]}]},
                temporal_reasoning={'onset_status': 'unknown', 'note': report.historical_coverage})
    review_time = datetime.now(UTC).isoformat()
    data = {'schema_version': '1.0', 'company': report.company.model_dump(mode='json'),
            'data_as_of': str(report.cutoff), 'bse_code': '543940',
            'reviewed_report': report.model_dump(mode='json'),
            'facts': expanded_fact_inputs(report),
            'peer_sources': peer_sources,
            'source_receipts': receipts,
            'editorial_review': {'reviewer': 'Codex source-based editorial review',
                'reviewed_at': review_time, 'method': 'source-based editorial review',
                'claim_ids': [str(x.id) for x in report.claims],
                'notes': 'Opened the actual source bytes, read the segment and annual tables, '
                         'checked prior-period restatement, reconciled components, and reviewed '
                         'each descriptive claim. No LLM/provider research run performed.'}}
    (FIXTURE_DIR / 'inputs' / 'JIOFIN.yaml').write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding='utf-8')
    print('JIOFIN source input updated:', len(report.facts), 'facts;', headline)


if __name__ == '__main__':
    main()
