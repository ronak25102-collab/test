"""Source-reviewed raw transcriptions for the remaining NIFTY financial issuers.

This is offline editorial assembly. Raw input values are disclosures; every
derived output is calculated by the registered Decimal engine and rebuilt by
build_precomputed.py. Downloads are a separate, explicit research step.
"""
from __future__ import annotations

import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pdfplumber
import pypdfium2 as pdfium
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend/src'))

from signal_research.domain.schemas import (  # noqa: E402
    Calculation,
    Company,
    Passage,
    ResearchReport,
    SourceDocument,
)
from signal_research.extraction.dates import source_dates  # noqa: E402
from signal_research.extraction.models import ExtractedFactCandidate  # noqa: E402
from signal_research.extraction.validate import validate_candidate  # noqa: E402
from signal_research.finance.calculations import calculate, numeric_fact  # noqa: E402
from signal_research.precomputed.authoring import (  # noqa: E402
    expanded_fact_inputs,
    observed_report,
)
from signal_research.precomputed.builder import FIXTURE_DIR, read_json  # noqa: E402
from signal_research.research.live import derive_calculations  # noqa: E402


def uid(text):
    return uuid5(NAMESPACE_URL, 'beyond/precomputed/october-24-additions/' + text)


def receipts():
    rows = read_json(FIXTURE_DIR / 'research_sources/remaining_receipts.json')
    rows.extend(read_json(path) for path in (ROOT / 'data/precomputed-sources').glob('*.receipt.json'))
    rows.extend(read_json(path) for path in (FIXTURE_DIR / 'research_sources').glob('*.receipt.json'))
    merged = {}
    for receipt in rows:
        if receipt.get('sha256'):
            key = receipt['sha256']
            merged[key] = {**merged.get(key, {}), **receipt}
    return merged


class Assembly:
    def __init__(self, symbol):
        self.identity = next(r for r in read_json(FIXTURE_DIR / 'roster.json')['companies'] if r['symbol'] == symbol)
        company = Company(id=self.identity['id'], legal_name=self.identity['legal_name'].removesuffix(' Ltd.'),
            symbols=[symbol], aliases=self.identity['aliases'], isin=self.identity['isin'], exchange='NSE',
            verified_ir_domains=[self.identity['ir_domain']], business_profiles=[self.identity['profile']])
        self.report = ResearchReport(run_id=uid(symbol), company=company, cutoff=date(2026, 10, 24),
            historical_coverage='Only the source-bound observations listed in Verified figures are covered; '
                                'this is not a claim of a complete annual and quarterly history.',
            source_coverage={}, outcome='partial', publication_status='abstained')
        self.sources, self.pages, self.used_receipts = {}, {}, []
        self.receipts = receipts()

    def source(self, digest, title, publication=None, *, table_pages=(), rupee_pages=()):
        receipt = self.receipts[digest]
        location = receipt.get('local_object_key', receipt.get('local_path'))
        location = Path(location)
        if location.is_absolute():
            location = location.relative_to(ROOT)
        path = ROOT / location
        doc = SourceDocument(id=uid(digest), canonical_url=receipt['url'],
            final_url=receipt.get('url_effective', receipt.get('final_url', receipt['url'])),
            publisher=self.report.company.legal_name, origin_family_id=f'issuer:{self.report.company.id}',
            title=title, document_type='issuer_filing', published_at=publication,
            retrieved_at=receipt['retrieved_at'], content_hash=digest,
            mime_type='application/pdf' if path.suffix == '.pdf' else 'text/html',
            local_object_key=location.as_posix(),
            cutoff_eligibility_basis='publication_date' if publication else 'verified_retrieval')
        if digest in self.sources:
            return self.sources[digest]
        self.sources[digest] = doc
        self.report.documents.append(doc)
        self.used_receipts.append({**receipt, 'local_object_key': location.as_posix()})
        texts = []
        if path.suffix == '.pdf':
            reader = pdfium.PdfDocument(path)
            texts = [reader[i].get_textpage().get_text_range() for i in range(len(reader))]
            if table_pages:
                with pdfplumber.open(path) as pdf:
                    for number in table_pages:
                        texts[number - 1] = pdf.pages[number - 1].extract_text() or texts[number - 1]
            for number in rupee_pages:
                # Visually reviewed rendered source uses the rupee glyph; only
                # its corrupt embedded font character is normalized here.
                texts[number - 1] = re.sub(r'\((?:~|`|4)\s*(?=[Ii]n\s)', '(₹ ', texts[number - 1])
                texts[number - 1] = texts[number - 1].replace('`', '₹')
        else:
            soup = BeautifulSoup(path.read_bytes(), 'html.parser')
            texts = [soup.get_text('\n', strip=True)]
        for i, text in enumerate(texts):
            passage = Passage(id=uid(f'{digest}/page/{i}'), document_id=doc.id,
                page_index=i if path.suffix == '.pdf' else None, text=text,
                extraction_method='pdfplumber' if i + 1 in table_pages else 'pdfium' if path.suffix == '.pdf' else 'html')
            self.report.passages.append(passage)
            self.pages[digest, i + 1] = passage
        return doc

    def fact(self, digest, pages, metric, value, end, *, start=None, scope='standalone',
             unit='INR crore', row=None, column=None, segment='all', scope_context=None):
        first, last = (pages, pages) if isinstance(pages, int) else pages
        source = self.pages[digest, first]
        text = '\n'.join(self.pages[digest, i].text for i in range(first, last + 1))
        passage = source.model_copy(update={
            'id': uid(f'{digest}/{first}-{last}/{metric}/{segment}/{start}/{end}'),
            'text': text, 'row_label': row, 'column_label': column,
            'section': f'PDF pages {first}–{last}' if first != last else source.section,
            'extraction_method': 'pdf_table' if row and column else source.extraction_method})
        self.report.passages.append(passage)
        candidate = ExtractedFactCandidate(metric_key=metric, value_raw=value,
            unit_raw=unit, currency=None if unit == 'percent' else 'INR',
            period_start=start, period_end=end, period_type='duration' if start else 'instant',
            scope=scope, segment=segment, passage_id=passage.id, extraction_confidence=1)
        result = validate_candidate(candidate, passage, self.report.company.id,
            self.report.company.business_profiles[0], scope_context=scope_context.text if scope_context else None)
        if result.fact is None:
            raise ValueError(f'{self.report.company.symbols[0]} {metric} {value} {end}: {result.reason}')
        self.report.facts.append(result.fact)
        if scope_context:
            self.report.generation_metadata.setdefault('fact_scope_contexts', {})[str(result.fact.id)] = {
                'passage_id': str(scope_context.id), 'review_note':
                'Same issuer and same filing date: the exchange iXBRL explicitly identifies these company results as standalone. Actuarial figures remain those of the insurance company, not group subsidiary totals.'}
        return result.fact

    def calc(self, formula, inputs):
        result = calculate(formula, [numeric_fact(f) for f in inputs])
        if not result.available:
            raise ValueError(f'{formula}: {result.limitations}')
        calculation = Calculation(id=result.id, formula_id=formula, formula_version=result.formula_version,
            input_fact_ids=result.input_fact_ids, output_value=result.output_value, unit=result.unit,
            scope=inputs[0].scope, period=' / '.join(str(f.period_end) for f in inputs),
            comparability_checks=result.comparability_checks,
            limitations=['Source-reported definitions, scope and precision apply; arithmetic does not establish causality.'])
        if calculation.id not in {c.id for c in self.report.calculations}:
            self.report.calculations.append(calculation)
        return calculation

    def finish(self, lead, *, significance, counterargument, review_note, headline_text=None,
               context=(), context_calculations=(), peers=(), limitations=()):
        review = observed_report(self.report, lead, significance=significance,
            counterargument=counterargument, review_note=review_note, headline_text=headline_text,
            context_fact_ids=[f.id for f in context], context_calculation_ids=[c.id for c in context_calculations],
            peer_sources=peers, limitations=[*limitations,
                *['Publication date not established; cutoff eligibility uses the recorded retrieval: ' + str(d.canonical_url)
                  for d in self.report.documents if d.published_at is None],
                'Coverage breadth is a disclosed target under the user-requested source-verified arithmetic policy; no missing observations or matched peers are invented.',
                'Moderate describes reproducible source arithmetic under the revised policy, not independent proof of a causal mechanism or an investment rating.'])
        data = {'schema_version': '1.0', 'data_as_of': str(self.report.cutoff),
            'publication_policy': 'source_verified_discovery_v2', 'bse_code': self.identity['bse_code'],
            'reviewed_report': self.report.model_dump(mode='json'),
            'facts': expanded_fact_inputs(self.report), 'editorial_review': review,
            'source_receipts': self.used_receipts}
        target = FIXTURE_DIR / 'inputs' / f'{self.report.company.symbols[0]}.yaml'
        target.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding='utf-8')
        print(target.stem, len(self.report.documents), 'documents', len(self.report.facts), 'facts',
              len(self.report.calculations), 'calculations')


def bajaj_finance():
    a = Assembly('BAJFINANCE')
    digest = '40722430396106b1a34e1ca6f84d8c873cf4e15a2650a96afedc5be169841e94'
    a.source(digest, 'Bajaj Finance Q2 FY27 investor presentation', '2026-10-19T00:00:00Z')
    for other, title in [('722a9cb0c1fcbed6d20d313dccc8169ed29bd0faf42e9cc39ce724ab7c0ac72c', 'Bajaj Finance Q3 FY26 investor presentation'),
                         ('45b664db8fd9858654fa6cdd7cf1b696898a4869152cc3831d16e1a21610bb20', 'Bajaj Finance Q1 FY27 investor presentation')]:
        a.source(other, title, '2026-02-03T00:00:00Z' if 'Q3 FY26' in title else None)
    # Rendered PDF page 56, named product rows and the issuer's Total row.
    rows = {
        'MSME Lending': ('53,084', ['2.47', '2.82', '2.98'], ['1.26', '1.08', '1.15']),
        'Gold Loans': ('24,195', ['0.59', '0.35', '0.70'], ['0.56', '0.33', '0.66']),
        'Urban Personal Loans': ('1,15,237', ['1.60', '1.19', '1.43'], ['0.69', '0.36', '0.41']),
        'Rural Personal Loans': ('29,244', ['1.65', '0.84', '1.13'], ['0.53', '0.11', '0.16']),
        'Total': ('5,84,624', ['1.24', '0.96', '1.06'], ['0.60', '0.39', '0.42']),
    }
    facts = {}
    dates = ['2025-09-30', '2026-06-30', '2026-09-30']
    for label, (aum, gross, net) in rows.items():
        segment = 'all' if label == 'Total' else label
        a.fact(digest, 56, 'aum', aum, dates[-1], scope='consolidated', row=label,
               column='30-Sep-26', segment=segment)
        for metric, values in [('gnpa', gross), ('nnpa', net)]:
            for end, value in zip(dates, values, strict=True):
                facts[label, metric, end] = a.fact(digest, 56, metric, value, end,
                    scope='consolidated', unit='percent', row=label, column=date.fromisoformat(end).strftime('%d-%b-%y'), segment=segment)
    a.report.calculations = derive_calculations(a.report.facts)
    primary = a.calc('change_pp', [facts['MSME Lending', 'gnpa', dates[-1]], facts['MSME Lending', 'gnpa', dates[0]]])
    total = a.calc('change_pp', [facts['Total', 'gnpa', dates[-1]], facts['Total', 'gnpa', dates[0]]])
    headline = f'Bajaj Finance recorded a {primary.output_value:.2f} percentage point increase in its MSME gross bad-loan ratio from September 2025 to September 2026 despite an improving consolidated ratio.'
    a.finish(primary, headline_text=headline, context=[facts['Total', 'gnpa', d] for d in (dates[0], dates[-1])],
        context_calculations=[total], significance=[
            'An improving group bad-loan ratio can coexist with deterioration in a named product portfolio; the product-level disclosure changes the interpretation of aggregate asset quality.',
            'Gross and net bad-loan ratios are different measures; a net ratio also reflects provisioning and is not substituted for the gross measure.',
            'Following the same named portfolio in later disclosures can distinguish persistence from a single reporting-date movement.'],
        counterargument='Product mix and denominator growth can change portfolio ratios without a uniform deterioration in underlying borrower performance; this observation does not identify the cause.',
        review_note='Reviewed the rendered Q2 FY27 provisioning-coverage table: MSME and Total gross ratios move in opposite directions on the same reporting dates. Read the accompanying credit-cost and gold-loan qualification; do not generalize the group improvement to every product.',
        limitations=['The full earlier annual and quarterly product series has not been bound. Exact same-product peer comparisons are unavailable in this snapshot.'])


def bajaj_finserv():
    a = Assembly('BAJAJFINSV')
    digest = '98014907d7d80f9978162591236a06c2ace5b40cd421954bfa1cf34bc92a8bd8'
    a.source(digest, 'Bajaj Finserv Q1 FY27 financial results and segment disclosures', '2026-07-31T00:00:00Z',
             table_pages=[9, 10], rupee_pages=[9, 10])
    # Retail, insurance total, investments/others and windmill reconcile exactly
    # to the issuer's reported segment profit before tax, including losses.
    periods = [
        ('2026-04-01', '2026-06-30', ['8,114.93', '1,109.43', '(295.33)', '3.16', '8,932.19']),
        ('2025-04-01', '2025-06-30', ['6,486.93', '908.83', '(196.45)', '4.33', '7,203.64']),
        ('2025-04-01', '2026-03-31', ['25,601.49', '2,171.72', '(902.56)', '12.50', '26,883.15']),
    ]
    groups = []
    for start, end, values in periods:
        group = []
        for segment, value in zip(['Retail financing', 'Insurance total', 'Investments and others', 'Windmill', 'all'], values, strict=True):
            group.append(a.fact(digest, (9, 10), 'segment_profit_total' if segment == 'all' else 'segment_profit', value,
                end, start=start, scope='consolidated', segment=segment,
                row='Total profit before tax' if segment == 'all' else segment,
                column=f'{"Year" if end.endswith("03-31") else "Quarter"} ended {end}'))
        groups.append(group)
    a.report.calculations = derive_calculations(a.report.facts)
    lead = a.calc('segment_profit_share', groups[0])
    a.finish(lead,
        headline_text=f'Bajaj Finserv derived {lead.output_value:.2f}% of reported segment profit before tax from retail financing during April 2026 to June 2026 on a consolidated basis.',
        significance=['Reported business diversification does not imply an equally diversified contribution to segment profit; retail financing dominates this reporting window.',
                      'Losses in investments and other businesses affect the denominator, so a segment share is not a measure of return on capital.',
                      'These are pre-tax segment contributions rather than profit attributable to equity owners; the distinction matters when interpreting the holding company.'],
        counterargument='A segment profit share can rise because another segment makes a loss; accounting timing, investment-market effects and differing segment economics prevent a causal interpretation.',
        review_note='Reviewed the signed Q1 FY27 segment table and reconciled every top-level segment profit component to Total profit before tax. Included the negative investments-and-others component; did not substitute net profit or add life/general insurance twice.',
        context=groups[1], limitations=['Q2 FY27 is scheduled after the cutoff; the current headline uses June 2026. Gross segment revenue and consolidated revenue are not interchangeable.'])


def bse():
    a = Assembly('BSE')
    digest = '34649f3bd60a6745dab5f5ba33cb7cf19a6a97246079743b78c2693c5f935a5d'
    a.source(digest, 'BSE Q1 FY27 investor presentation', '2026-08-04T00:00:00Z')
    signed = next(r for r in a.receipts.values() if r.get('title') == 'BSE Q1 FY27 financial results')
    a.source(signed['sha256'], 'BSE Q1 FY27 reviewed financial results', '2026-08-04T00:00:00Z')
    facts = {}
    # Source table page 26: the issuer labels quarter columns explicitly. The
    # document's dated signed financial statement anchors the fiscal calendar.
    # Exact quarterly month-year headers are handled by the existing parser.
    for end, transaction, revenue, column in [
        ('2026-06-30', '13,277', '15,661', "Jun'26 Quarter"),
        ('2025-06-30', '7,375', '9,580', "Jun'25 Quarter"),
        ('2026-03-31', '13,110', '15,635', 'Mar’26 Quarter'),
    ]:
        for metric, value, label in [('transaction_revenue', transaction, 'Transaction Charges'), ('revenue', revenue, 'Revenue From Operations')]:
            start = end[:4] + ('-04-01' if end.endswith('06-30') else '-01-01')
            facts[metric, end] = a.fact(digest, 26, metric, value, end, start=start,
                scope='consolidated', unit='INR million', row=label, column=column)
    a.report.calculations = derive_calculations(a.report.facts)
    lead = a.calc('growth_gap', [facts['transaction_revenue', '2026-06-30'], facts['transaction_revenue', '2025-06-30'],
                               facts['revenue', '2026-06-30'], facts['revenue', '2025-06-30']])
    a.finish(lead,
        headline_text=f'BSE recorded a {lead.output_value:.2f} percentage point transaction charges versus operating revenue growth gap from June 2025 to June 2026 on a consolidated basis.',
        significance=['Transaction charges grew faster than operating revenue, increasing the importance of activity-sensitive income within the disclosed operating mix.',
                               'The revenue composition should be assessed separately from total income, which also contains investment and other income.',
                               'Activity-sensitive charges can vary with turnover and pricing, so revenue growth alone does not establish a stable recurring-income mix.'],
        counterargument='Transaction fees depend on trading activity and pricing; a strong quarter does not establish a durable trend or show that recurring listing revenue has disappeared.',
        review_note='Read the Q1 FY27 presentation business-model discussion and consolidated income table. Compared the same quarter, scope and million-rupee units for transaction charges and operating revenue; retained issuer rounding rather than replacing it with another statement’s precision.',
        limitations=['The management presentation contains rounded figures and regroupings. Exact same-period exchange peer inputs and a complete quarterly history are not bound.'])


def insurance_values(text, label):
    match = re.search(re.escape(label) + r'(?:\s*\(\d+\)|\d+)?\s+(\d[\d,.]*)\s+(\d[\d,.]*)', text, re.I)
    if not match:
        raise ValueError('Missing reviewed insurance table row: ' + label)
    return match[1], match[2]


def hdfc_life():
    a = Assembly('HDFCLIFE')
    manifest = read_json(FIXTURE_DIR / 'research_sources/remaining_receipts.json')
    selected = [r for r in manifest if r['symbol'] == 'HDFCLIFE' and
                ('12M-FY' in r['title'] and 'Press Release' in r['title'] or 'H1-FY2027 Press Release' in r['title'])]
    for digest, title in [('78f6a8dee9d7db59b880c1d1f861d93f93ba822845fbe1bba3c33969c5c72e07', 'HDFC Life H1-FY2026 Press Release'),
                          ('fe6528921ed5ed19123721a315969876feaa17f595b8c02e42dd0d62d8095c16', 'HDFC Life Q1-FY2027 Press Release')]:
        selected.append({**a.receipts[digest], 'title': title})
    facts = {}
    for receipt in selected:
        digest, title = receipt['sha256'], receipt['title']
        doc = a.source(digest, title)
        count = len([key for key in a.pages if key[0] == digest])
        text = '\n'.join(a.pages[digest, n].text for n in range(1, count + 1))
        dateline = re.search(r'Mumbai,\s*(.{5,50}?)\s*:', re.sub(r'\s+', ' ', text), re.I)
        dates = source_dates(dateline[1]) if dateline else []
        if len(dates) == 1:
            doc.published_at = datetime.combine(dates[0], datetime.min.time(), UTC)
            doc.cutoff_eligibility_basis = 'publication_date'
        year = int(re.search(r'FY(20\d{2})', title)[1])
        kind = 'H1' if 'H1-' in title else 'Q1' if 'Q1-' in title else '12M'
        current_end = date(year - (kind != '12M'), 9 if kind == 'H1' else 6 if kind == 'Q1' else 3,
                           30 if kind != '12M' else 31)
        table = text[text.index('Key Financial Summary'):]
        for offset in [0, 1]:
            end = current_end.replace(year=current_end.year - offset)
            start = date(end.year if kind != '12M' else end.year - 1, 4, 1)
            source_fy = year - offset
            # Select the literal table heading as printed, including compact FY
            # formatting. Fiscal dates are normalized from the complete source caption.
            label_options = ([f'{kind} FY{source_fy % 100:02}', f'{kind}FY{source_fy % 100:02}',
                              f'FY{source_fy % 100:02}'] if kind != 'Q1' else
                             [f'3M FY{source_fy % 100:02}', f'Q1 FY{source_fy % 100:02}'])
            column = next((label for label in label_options if label in table), None)
            if column is None:
                raise ValueError(title + ': reviewed column missing')
            for metric, label in [('ape', 'Total APE'), ('vnb', 'Value of new business'),
                                  ('net_profit', 'Profit After Tax'), ('total_premium', 'Total Premium'),
                                  ('aum', 'Assets Under Management')]:
                values = insurance_values(table, label)
                fact = a.fact(digest, (1, count), metric, values[offset], end, start=None if metric == 'aum' else start,
                              row=label, column=column)
                facts[metric, end, kind] = fact
        if kind == 'H1' and year == 2027:
            match = re.search(r'13M\s*/\s*61M\s+Persistency\s+(\d+)%/(\d+)%\s+(\d+)%/(\d+)%', text)
            if not match:
                raise ValueError('Reviewed persistency row missing')
            for offset in [0, 1]:
                end = current_end.replace(year=current_end.year - offset)
                for metric, index in [('persistency_13m', 1 + 2 * offset), ('persistency_61m', 2 + 2 * offset)]:
                    facts[metric, end, kind] = a.fact(digest, (1, count), metric, match[index], end,
                        unit='percent', row='13M / 61M Persistency', column=f'H1 FY{(year-offset) % 100:02}')
    # Keep the latest source for duplicate comparisons. Different measurement
    # dates/durations and historical merger boundaries remain distinct.
    unique = {}
    for fact in a.report.facts:
        key = (fact.metric_key, fact.scope, fact.segment, fact.period_start, fact.period_end)
        unique[key] = fact
    a.report.facts = list(unique.values())
    a.report.calculations = derive_calculations(a.report.facts)
    primary = a.calc('change_pp', [facts['persistency_13m', date(2026, 9, 30), 'H1'],
                                   facts['persistency_13m', date(2025, 9, 30), 'H1']])
    context = [facts['vnb', date(y, 9, 30), 'H1'] for y in [2025, 2026]]
    growth = a.calc('yoy_growth', list(reversed(context)))
    a.finish(primary,
        headline_text=f'HDFC Life Insurance Company recorded a {primary.output_value:g} percentage point change in early-renewal premium persistency from September 2025 to September 2026 while new-business value grew.',
        context=context, context_calculations=[growth], significance=[
            'Growth in the actuarial value of new business can coexist with weaker early renewals; the two disclosures measure different parts of the insurance franchise.',
            'Persistency reflects renewal experience while new-business value depends on expected future economics, so one should not be treated as a substitute for the other.',
            'Monitoring both measures can distinguish growth in new sales economics from retention of earlier policy cohorts.'],
        counterargument='Changes in product and customer mix can alter persistency without showing the same deterioration in every cohort. New-business value also depends on actuarial assumptions; these observations do not establish cause.',
        review_note='Read the H1 FY27 release, comparative persistency row, VNB rows and metric definitions. The issuer explicitly attributes persistency trends to product and tier mix. Kept the insurance-company figures separate from the larger AUM including its pension subsidiary.',
        limitations=['FY23 is on a merged basis and the issuer says prior years are not comparable; do not treat the full history as a continuous organic-growth series.',
                     'Early-renewal means the source’s 13-month premium persistency measure, not a lapse rate or every policy cohort.'])


def sbi_life():
    a = Assembly('SBILIFE')
    annual = next(r for r in a.receipts.values() if r.get('title') == 'SBI Life FY26 results and investor presentation')
    sources = [
        ('1dcc0495332b311fa39131582e8da65c967334a6505f24dfc717f1bbcc6c87fb', 'SBI Life Q1 FY27 release and presentation', '2026-07-24T00:00:00Z',
         '41fef470640d3d7a660b07ffefd6b2c53299a0149ba86adfb26ae9a584a656c3', 'Q1-FY 2027', 'Q1-FY 2026', date(2026, 6, 30), date(2025, 6, 30)),
        (annual['sha256'], 'SBI Life FY26 release and presentation', '2026-04-22T00:00:00Z',
         '166fc60384917adb03c28c0339caac52d88d092bb3cbb9bdc4eb969138db9fcf', 'FY 2026', 'FY 2025', date(2026, 3, 31), date(2025, 3, 31)),
    ]
    facts = {}
    for digest, title, published, scope_digest, current_label, prior_label, current, prior in sources:
        a.source(digest, title, published, rupee_pages=[2, 3])
        a.source(scope_digest, title + ' – NSE iXBRL standalone scope', published)
        context = a.pages[scope_digest, 1]
        text = '\n'.join(a.pages[digest, n].text for n in range(1, 4))
        table = text[text.index('Key measures of performance'):]
        for offset, end, column in [(0, current, current_label), (1, prior, prior_label)]:
            start = date(end.year - end.month // 12 if end.month != 3 else end.year - 1, 4, 1)
            for metric, label in [('ape', 'Annualized Premium Equivalent (APE)'), ('vnb', 'Value of New Business (VoNB)'),
                                  ('net_profit', 'Profit after Tax (PAT)'), ('aum', 'Assets under Management (AuM)'),
                                  ('new_business_premium', 'New Business Premium (NBP)'), ('renewal_premium', 'Renewal Premium (RP)')]:
                values = insurance_values(table, label)
                facts[metric, end] = a.fact(digest, (1, 3), metric, values[offset], end,
                    start=None if metric == 'aum' else start, unit='INR billion',
                    row=label, column=column, scope_context=context)
    a.report.calculations = derive_calculations(a.report.facts)
    lead = a.calc('growth_gap', [facts['vnb', date(2026, 6, 30)], facts['vnb', date(2025, 6, 30)],
                               facts['ape', date(2026, 6, 30)], facts['ape', date(2025, 6, 30)]])
    hdfc = yaml.safe_load((FIXTURE_DIR / 'inputs/HDFCLIFE.yaml').read_text(encoding='utf-8'))['reviewed_report']
    peer = {k: hdfc[k] for k in ['company', 'documents', 'passages', 'facts']}
    a.finish(lead, headline_text=f'SBI Life Insurance Company recorded a {lead.output_value:.2f} percentage point new-business value versus annualised premium-equivalent growth gap from June 2025 to June 2026 on a standalone basis.',
        peers=[peer], significance=[
            'Premium-equivalent growth exceeded growth in the actuarial value of new business, so sales growth alone overstates the growth in new-business economics.',
            'The disclosed rounded values are retained in the calculation; small differences from the issuer’s growth percentages can reflect rounding.',
            'The relationship concerns new policies written during the quarter, rather than profit recognised from the full back book.'],
        counterargument='Changes in product mix, distribution, discount rates and actuarial assumptions can change new-business value relative to premium-equivalent sales. The gap does not identify which mechanism caused it.',
        review_note='Read the rendered Q1 FY27 performance table and its VNB/APE definitions. Linked the contemporaneous NSE iXBRL standalone designation as separate scope evidence; retained raw billion-rupee inputs and calculated normalized values with the formula engine.',
        limitations=['The quarter is the latest results available at the cutoff; no September 2026 results are fabricated.',
                     'Only one matched listed-insurer peer is supplied. Peer facts lacking their own scope anchors are excluded from numerical peer comparisons.'])


def shriram():
    a = Assembly('SHRIRAMFIN')
    manifest = read_json(FIXTURE_DIR / 'research_sources/remaining_receipts.json')
    selected = [r for r in manifest if r['symbol'] == 'SHRIRAMFIN' and any(
        part in r['title'] for part in ['Q2FY27', 'Q1%20FY%202026-27', 'FY2025-26', 'FY2024-25', 'FY2023-24', 'Q4-FY23'])]
    facts = {}
    skipped = []
    for receipt in selected:
        digest = receipt['sha256']
        doc = a.source(digest, receipt['title'])
        text = re.sub(r'\s+', ' ', a.pages[digest, 1].text)
        ends = source_dates(text)
        # Measurement end is explicitly stated in the opening financial caption;
        # the latest date can instead be the board or a future dividend date.
        first_metric = re.search(r'Net Interest Income', text, re.I)
        prefix = text[:first_metric.start()] if first_metric else text
        captions = list(re.finditer(r'(quarter|year)\s+ended\s+(.{6,35}?(?:20\d{2}))', prefix, re.I))
        end_match = captions[-1] if captions else None
        declared = source_dates(end_match[2]) if end_match else []
        if not declared:
            skipped.append(receipt['title'] + ': reporting caption date not bound')
            continue
        end = declared[0]
        is_annual = end_match[1].lower() == 'year'
        start = date(end.year - 1 if is_annual else end.year, 4 if is_annual else end.month - 2, 1)
        pub = next((d for d in ends if end < d <= date(2026, 10, 24) and (d - end).days < 90), None)
        if pub:
            doc.published_at = datetime.combine(pub, datetime.min.time(), UTC)
            doc.cutoff_eligibility_basis = 'publication_date'
        for metric, pattern in [
            ('net_interest_income', r'Net Interest Income.*?(?:stood at|stands at|was)\s*Rs\.?\s*([\d,]+\.\d+)'),
            ('net_profit', r'profit after tax.*?(?:stood at|stands at|was)\s*Rs\.?\s*([\d,]+\.\d+)'),
            ('aum', r'Total Assets under Management.*?(?:stood at|stands at|was)\s*Rs\.?\s*([\d,]+\.\d+)'),
        ]:
            match = re.search(pattern, text, re.I)
            if not match:
                skipped.append(receipt['title'] + ': ' + metric + ' row not bound')
                continue
            try:
                fact = a.fact(digest, 1, metric, match[1], end, start=None if metric == 'aum' else start,
                    row={'aum': 'Total Assets under Management', 'net_profit': 'profit after tax', 'net_interest_income': 'Net Interest Income'}[metric],
                    column=f'{"Year" if is_annual else "Quarter"} ended {end}')
            except ValueError as error:
                skipped.append(str(error))
                continue
            facts[metric, end, is_annual] = fact
    a.report.calculations = derive_calculations(a.report.facts)
    lead = a.calc('growth_gap', [facts['net_profit', date(2026, 9, 30), False], facts['net_profit', date(2025, 9, 30), False],
                               facts['net_interest_income', date(2026, 9, 30), False], facts['net_interest_income', date(2025, 9, 30), False]])
    a.finish(lead,
        headline_text=f'Shriram Finance recorded a {lead.output_value:.2f} percentage point net profit versus net interest income growth gap from September 2025 to September 2026 on a standalone basis.',
        significance=[
            'Profit growth exceeded net-interest-income growth in the same standalone quarter, so the earnings acceleration is not explained by the top-line interest spread alone.',
            'AUM is a point-in-time stock and is retained separately; it is not mixed into a quarterly income growth calculation.',
            'The distinction directs review toward provisions, operating costs and non-interest items without claiming any of them caused the gap.'],
        counterargument='Profit growth can reflect base effects and changes in provisioning or operating costs. A larger profit-growth rate does not by itself demonstrate a persistent improvement in loan-level economics.',
        review_note='Opened the issuer’s quarterly press releases. Bound each current quarterly profit and net-interest-income value to that release’s own explicit reporting interval and standalone scope; used the earlier release for the prior-year observation rather than inferring its duration from an unlabelled comparison.',
        limitations=['Pre-merger Shriram Transport figures are excluded from the current headline. Do not infer uninterrupted organic growth across the merger.',
                     'December 2024 profit includes the disclosed housing-finance disposal gain; as-reported profits are not silently replaced with adjusted comparisons.',
                     'Own-period AUM figures are retained; later comparative disclosures can differ, and those revisions have not been reconciled.',
                     *skipped, 'Full matched standalone NBFC peer series has not been verified.'])


if __name__ == '__main__':
    actions = {'BAJFINANCE': bajaj_finance, 'BAJAJFINSV': bajaj_finserv, 'BSE': bse,
               'HDFCLIFE': hdfc_life, 'SBILIFE': sbi_life, 'SHRIRAMFIN': shriram}
    for symbol in sys.argv[1:] or actions:
        actions[symbol]()
