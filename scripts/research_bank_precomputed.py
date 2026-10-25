"""Assemble manually reviewed bank source inputs without provider requests."""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pypdfium2 as pdfium
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend' / 'src'))

from signal_research.domain.schemas import (  # noqa: E402
    Company,
    Passage,
    ResearchReport,
    SourceDocument,
)
from signal_research.extraction.bank_tables import comparative_bank_batch  # noqa: E402
from signal_research.extraction.dates import source_dates  # noqa: E402
from signal_research.extraction.models import ExtractedFactCandidate  # noqa: E402
from signal_research.extraction.validate import validate_candidate  # noqa: E402
from signal_research.precomputed.authoring import (  # noqa: E402
    expanded_fact_inputs,
    observed_report,
)
from signal_research.precomputed.builder import FIXTURE_DIR, read_json  # noqa: E402
from signal_research.research.live import derive_calculations  # noqa: E402


def uid(text):
    return uuid5(NAMESPACE_URL, 'beyond/research/banks/' + text)


def save_input(report, review, bse_code, receipts):
    data = {'schema_version': '1.0', 'data_as_of': str(report.cutoff),
            'publication_policy': 'source_verified_discovery_v2',
            'bse_code': bse_code, 'reviewed_report': report.model_dump(mode='json'),
            'facts': expanded_fact_inputs(report),
            'editorial_review': review, 'source_receipts': receipts}
    (FIXTURE_DIR / 'inputs' / f'{report.company.symbols[0]}.yaml').write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding='utf-8')


def icici():
    hdfc = ResearchReport.model_validate(read_json(FIXTURE_DIR / 'HDFCBANK.json'))
    sources = hdfc.generation_metadata['peer_benchmark']['sources']
    source = next(x for x in sources if x['company']['symbols'] == ['ICICIBANK'])
    report = ResearchReport(run_id=uid('ICICIBANK'), company=source['company'],
        cutoff=date(2026, 10, 24), historical_coverage='Source-bound FY22–FY26 annual balance '
        'figures and September 2026 quarterly updates; gaps remain in the complete quarterly series.',
        source_coverage={}, outcome='partial', publication_status='abstained',
        documents=source['documents'], passages=source['passages'], facts=source['facts'])
    receipts = []
    directory = FIXTURE_DIR / 'research_sources'
    for path in sorted(directory.glob('ICICIBANK_Q*.html')):
        receipt = read_json(path.with_suffix(path.suffix + '.receipt.json'))
        receipts.append(receipt)
        soup = BeautifulSoup(path.read_bytes(), 'html.parser')
        text = soup.get_text('\n', strip=True)
        document = SourceDocument(id=uid(receipt['sha256']),
            canonical_url=receipt['url'], final_url=receipt['final_url'],
            publisher=report.company.legal_name, origin_family_id=f'issuer:{report.company.id}',
            title=soup.title.get_text(' ', strip=True), document_type='issuer_disclosure',
            retrieved_at=receipt['retrieved_at'], content_hash=receipt['sha256'],
            mime_type='text/html', local_object_key=receipt['local_path'],
            cutoff_eligibility_basis='verified_retrieval')
        report.documents.append(document)
        for table in soup.find_all('table'):
            table_text = table.get_text('\n', strip=True)
            table_start = text.find(table_text)
            headings = list(re.finditer(r'Summary\s+Profit', text[:table_start], re.I))
            context_start = headings[-1].start() if headings else max(0, table_start - 250)
            source_span = text[context_start:table_start + len(table_text)]
            rows = [[cell.get_text(' ', strip=True) for cell in row.find_all(['td', 'th'])]
                    for row in table.find_all('tr')]
            headers = next((row for row in rows
                            if sum(bool(source_dates(cell)) for cell in row) >= 2), None)
            if not headers:
                continue
            columns = [source_dates(cell) for cell in headers[1:]]
            if not all(len(dates) == 1 for dates in columns):
                continue
            dates = [values[0] for values in columns]
            for row in rows:
                if not row:
                    continue
                label = row[0]
                metric = ('deposits' if label.lower() == 'deposits' else
                          'borrowings' if label.lower().startswith('borrowings') else
                          'advances_as_reported' if label.lower() == 'advances' else None)
                if not metric or len(row) != len(dates) + 1:
                    continue
                span = Passage(id=uid(f'{path.name}/{label}'), document_id=document.id,
                    section='Summary Balance Sheet', row_label=label,
                    column_label=' | '.join(headers[1:]), text=source_span,
                    extraction_method='html_table')
                report.passages.append(span)
                for end, raw in zip(dates, row[1:], strict=True):
                    candidate = ExtractedFactCandidate(metric_key=metric, value_raw=raw,
                        unit_raw='INR crore', currency='INR', period_end=end,
                        scope='standalone', passage_id=span.id, extraction_confidence=1)
                    validation = validate_candidate(candidate, span, report.company.id,
                                                    report.company.business_profiles[0])
                    if validation.fact is None:
                        raise ValueError(f'{path.name}/{label}/{end}: {validation.reason}')
                    report.facts.append(validation.fact)
    # Preserve natural PDF paragraphs and rows as exact passages. Their IDs and
    # offsets are independent of a requested count; nothing is duplicated to pad.
    for path in sorted(directory.glob('ICICI*.pdf')):
        receipt_path = path.with_suffix(path.suffix + '.receipt.json')
        if not receipt_path.exists():
            continue
        receipt = read_json(receipt_path)
        receipts.append(receipt)
        doc = SourceDocument(id=uid(receipt['sha256']),
            canonical_url=receipt['url'], final_url=receipt['final_url'],
            publisher=report.company.legal_name, origin_family_id=f'issuer:{report.company.id}',
            title=path.stem.replace('_', ' '), document_type='issuer_filing',
            retrieved_at=receipt['retrieved_at'], content_hash=receipt['sha256'],
            mime_type='application/pdf', local_object_key=receipt['local_path'],
            cutoff_eligibility_basis='verified_retrieval')
        if any(d.content_hash == doc.content_hash for d in report.documents):
            continue
        report.documents.append(doc)
        reader = pdfium.PdfDocument(str(path))
        for index in range(len(reader)):
            text = reader[index].get_textpage().get_text_range()
            for number, paragraph in enumerate(re.split(r'\r?\n\s*\r?\n', text)):
                if len(paragraph.strip()) < 40:
                    continue
                report.passages.append(Passage(id=uid(f'{doc.id}/{index}/{number}'),
                    document_id=doc.id, page_index=index, text=paragraph,
                    extraction_method='pdfium'))
    report.calculations = derive_calculations(report.facts)
    choices = [c for c in report.calculations if c.formula_id == 'deposit_borrowing_mix_change'
               and c.scope.value == 'standalone']
    calculation = max(choices, key=lambda c: c.period or '')
    peer_sources = [sources[0], {'company': hdfc.company.model_dump(mode='json'),
        'documents': [d.model_dump(mode='json') for d in hdfc.documents],
        'passages': [p.model_dump(mode='json') for p in hdfc.passages],
        'facts': [f.model_dump(mode='json') for f in hdfc.facts]}]
    review = observed_report(report, calculation, significance=[
        'The source-bound funding mix compares deposits with deposits plus reported '
        'borrowings; it distinguishes deposit expansion from reliance on the borrowing denominator.',
        'The same issuer’s deposits and borrowings use matching dates, scope and monetary '
        'scale. Other liabilities are outside this deliberately limited denominator.',
        'The latest release discloses the foreign currency deposit mobilisation program; '
        'a change in this funding mix is not evidence of funding stress or of a causal mechanism.',
    ], counterargument='Foreign currency deposits and the matching asset deployment can change '
        'the observed denominator without indicating funding pressure; the ratio does not '
        'measure all liabilities, liquidity risk, or the quality of the lending franchise.',
        review_note='Opened the issuer FY22–FY26 and September 2026 performance releases, '
        'checked the standalone summary balance-sheet columns and the disclosed foreign '
        'currency funding explanation, and reproduced the registered arithmetic.',
        peer_sources=peer_sources, limitations=[
            'Peer comparisons use the matched June 2025/2026 consolidated lane; they do not '
            'benchmark the newer September standalone headline or prove causality.',
            'Borrowings are the issuer’s reported balance, including subordinated debt where '
            'the source says so. Other liabilities are excluded from the funding-share denominator.',
            'The earlier annual observations and current quarter do not establish true onset. '
            'A full eight-quarter comparable history has not been independently established.',
            'Publication dates not established in the source are unknown; actual dated '
            'retrieval receipts establish availability only at this snapshot cutoff.',
        ])
    save_input(report, review, '532174', receipts)
    print('ICICIBANK:', len(report.facts), 'facts;', len(report.passages), 'passages')


def axis():
    bundle = read_json(ROOT / 'tmp-axis-bundle.json')
    report = ResearchReport(run_id=uid('AXISBANK'), company=bundle['company'],
        cutoff=date(2026, 10, 24), historical_coverage='Verified FY25/FY26 annual balances '
        'and June/September FY27 quarterly balances. Five full annual periods and eight '
        'quarters remain incomplete.', source_coverage={}, outcome='partial',
        publication_status='abstained', documents=bundle['documents'],
        passages=bundle['passages'], facts=bundle['facts'])
    receipt = read_json(ROOT / 'tmp-axis-annual-receipt.json')
    annual = SourceDocument(id=uid(receipt['sha256']), canonical_url=receipt['url'],
        final_url=receipt['final_url'], publisher=report.company.legal_name,
        origin_family_id=f'issuer:{report.company.id}',
        title='Axis Bank Integrated Annual Report 2025-26', document_type='issuer_annual_report',
        retrieved_at=receipt['retrieved_at'], content_hash=receipt['sha256'],
        mime_type='application/pdf', local_object_key=receipt['path'],
        cutoff_eligibility_basis='verified_retrieval')
    report.documents.append(annual)
    annual_pdf = pdfium.PdfDocument(receipt['path'])
    quarterly = report.documents[4]
    quarterly_pdf = pdfium.PdfDocument(quarterly.local_object_key)
    tables = [
        (annual, annual_pdf, 459, 'consolidated', 'INR crore', ['2026-03-31', '2025-03-31'], {
            'deposits': ['1,333,791.44', '1,170,920.89'],
            'borrowings': ['280,510.62', '220,686.75'],
            'advances_as_reported': ['1,282,392.17', '1,081,229.47']}),
        (annual, annual_pdf, 347, 'standalone', 'INR thousand', ['2026-03-31', '2025-03-31'], {
            'deposits': ['13,358,339,715', '11,729,520,224'],
            'borrowings': ['2,352,706,087', '1,841,465,165'],
            'advances_as_reported': ['12,335,698,765', '10,408,113,203']}),
        (quarterly, quarterly_pdf, 8, 'consolidated', 'INR crore', ['2026-09-30', '2025-09-30'], {
            'deposits': ['14,50,287.83', '12,01,655.60'],
            'borrowings': ['3,24,487.88', '2,40,841.49'],
            'advances_as_reported': ['14,31,452.73', '11,61,625.74']}),
    ]
    for document, pdf, page, scope, unit, ends, rows in tables:
        text = pdf[page - 1].get_textpage().get_text_range()
        if document == quarterly:
            # Consecutive preceding page carries the consolidated table title
            # and currency. Preserve both pages in their original reading order.
            text = pdf[page - 2].get_textpage().get_text_range() + '\n' + text
        # The embedded font maps the printed rupee glyph to a backtick. The
        # annual table has been checked visually against its rendered source.
        text = text.replace('`', '₹')
        for metric, values in rows.items():
            span = Passage(id=uid(f'{document.id}/{page}/{metric}'), document_id=document.id,
                page_index=page - (2 if document == quarterly else 1),
                printed_page_label='460' if page == 459 else '348' if page == 347 else None,
                text=text, row_label='Advances' if metric == 'advances_as_reported' else metric.title(),
                column_label=' | '.join(ends), extraction_method='pdfium')
            report.passages.append(span)
            for end, raw in zip(ends, values, strict=True):
                candidate = ExtractedFactCandidate(metric_key=metric, value_raw=raw,
                    unit_raw=unit, currency='INR', period_end=end, scope=scope,
                    passage_id=span.id, extraction_confidence=1)
                result = validate_candidate(candidate, span, report.company.id,
                                            report.company.business_profiles[0])
                if not result.fact:
                    raise ValueError(f'AXISBANK {page} {metric} {end}: {result.reason}')
                report.facts.append(result.fact)
    report.calculations = derive_calculations(report.facts)
    calculation = max([c for c in report.calculations if c.formula_id == 'deposit_borrowing_mix_change'
                       and c.scope.value == 'consolidated'], key=lambda c: c.period or '')
    hdfc = ResearchReport.model_validate(read_json(FIXTURE_DIR / 'HDFCBANK.json'))
    icici_source = next(b for b in hdfc.generation_metadata['peer_benchmark']['sources']
                        if b['company']['symbols'] == ['ICICIBANK'])
    peers = [icici_source, {'company': hdfc.company.model_dump(mode='json'),
        'documents': [d.model_dump(mode='json') for d in hdfc.documents],
        'passages': [p.model_dump(mode='json') for p in hdfc.passages],
        'facts': [f.model_dump(mode='json') for f in hdfc.facts]}]
    note = ('Opened Axis’s annual FY26 financial statements and the current September '
            '2026 result/press release; checked original consolidated deposits and '
            'borrowings columns, the foreign-currency deposit disclosure and scope separation.')
    review = observed_report(report, calculation, significance=[
        'Deposit growth alone does not describe this funding mix: the original consolidated '
        'borrowing and deposit balances move at different rates.',
        'The denominator includes only deposits and borrowings, so this comparison cannot '
        'be interpreted as the share of deposits in all liabilities.',
        'The bank’s current foreign-currency deposit mobilisation and subsidiary funding '
        'context are reasons to qualify the ratio rather than infer a funding shortage.',
    ], counterargument='Foreign currency deposit mobilisation, matching asset deployment and '
        'consolidated subsidiaries’ financing can change the reported mix without showing '
        'liquidity stress. The calculation is a descriptive accounting comparison.',
        review_note=note, peer_sources=peers, limitations=[
            'Peers match the June 2025/2026 consolidated lane; the newer September '
            'headline is not represented as a verified current peer median.',
            'Other liabilities and liquidity buffers are outside the denominator. '
            'Standalone and consolidated balances are kept in separate calculation lanes.',
            'Annual history is incomplete before FY25; the verified observations cover '
            'FY25, FY26 and FY27, not five full fiscal years or eight verified quarters.',
            'No onset or causal funding-stress claim is established.',
        ])
    save_input(report, review, '532215', [receipt])
    print('AXISBANK:', len(report.facts), 'facts')


def kotak():
    path = ROOT / 'tmp/kotak-5ced3593-b321-44fc-ae07-d41f82099a13.json'
    report = ResearchReport.model_validate(read_json(path))
    report.run_id, report.cutoff = uid('KOTAKBANK'), date(2026, 10, 24)
    report.calculations = derive_calculations(report.facts)
    calculation = max([c for c in report.calculations if c.formula_id == 'deposit_borrowing_mix_change'
                       and c.scope.value == 'standalone'], key=lambda c: c.period or '')
    peer_sources = []
    for symbol in ['AXISBANK', 'ICICIBANK']:
        peer = ResearchReport.model_validate(read_json(FIXTURE_DIR / f'{symbol}.json'))
        # Compare total deposits only: ICICI's borrowing label explicitly includes
        # subordinated debt, so it is not silently equated to another definition.
        facts = [f for f in peer.facts if f.metric_key == 'deposits'
                 and f.scope.value == 'standalone' and f.period_end in
                 {date(2025, 3, 31), date(2026, 3, 31)}]
        # Repeated rounded releases are alternative observations, not extra peers.
        selected = {}
        for fact in facts:
            selected.setdefault(fact.period_end, fact)
        passage_ids = {f.passage_id for f in selected.values()}
        passages = [p for p in peer.passages if p.id in passage_ids]
        document_ids = {p.document_id for p in passages}
        peer_sources.append({'company': peer.company.model_dump(mode='json'),
            'documents': [d.model_dump(mode='json') for d in peer.documents if d.id in document_ids],
            'passages': [p.model_dump(mode='json') for p in passages],
            'facts': [f.model_dump(mode='json') for f in selected.values()]})
    note = ('Opened and hash-checked the issuer’s saved original annual and quarterly '
            'filings; reviewed the FY25/FY26 standalone deposits and borrowings against '
            'the current source definitions and kept older consolidated history separate. '
            'Current Q2 FY27 press-release evidence was inspected and its FCNR explanation '
            'does not retrospectively establish a mechanism for the March annual comparison.')
    review = observed_report(report, calculation, significance=[
        'The increase in deposits as a share of deposits plus borrowings combines deposit '
        'growth with a reduction in the reported borrowing balance.',
        'The original standalone net-advance and deposit observations provide lending '
        'context; net advances are not relabelled as gross advances or compared across scopes.',
        'Matched same-period deposit growth from Axis and ICICI is contextual evidence; '
        'it does not establish that changes in borrowing balances share a common cause.',
    ], counterargument='A borrowing contraction can reflect financing choices and balance-sheet '
        'composition rather than a durable funding advantage. Foreign currency funding in '
        'later quarters also limits extrapolation of this annual snapshot.',
        review_note=note, peer_sources=peer_sources, limitations=[
            'The finding concerns March 2025 to March 2026, not a newly measured September '
            'funding ratio. The September 2026 result is available but its complete comparable '
            'balance-sheet inputs have not been incorporated into this fixture.',
            'Peer verification is limited to deposits with matching annual endpoints; '
            'borrowings with different subordinated-debt definitions are excluded.',
            'Other liabilities are excluded. Older consolidated observations do not extend '
            'the standalone annual lane or establish true onset.',
        ])
    receipts = read_json(FIXTURE_DIR / 'research_sources/KOTAKBANK/receipts.json')
    save_input(report, review, '500247', receipts)
    print('KOTAKBANK:', len(report.facts), 'facts')


def sbi():
    entry = next(e for e in read_json(FIXTURE_DIR / 'roster.json')['companies']
                 if e['symbol'] == 'SBIN')
    company = Company(id=entry['id'], legal_name=entry['legal_name'], symbols=['SBIN'],
        aliases=entry['aliases'], business_profiles=['bank'], verified_ir_domains=[entry['ir_domain']])
    report = ResearchReport(run_id=uid('SBIN'), company=company, cutoff=date(2026, 10, 24),
        historical_coverage='Original standalone balance tables span FY22–FY26 and the '
        'eight quarters through June 2026. Latest verified reporting quarter is Q1 FY27.',
        source_coverage={}, outcome='partial', publication_status='abstained')
    receipts = []
    for path in sorted((FIXTURE_DIR / 'research_sources').glob('SBIN_*.pdf')):
        receipt = read_json(path.with_suffix(path.suffix + '.receipt.json'))
        if receipt['http_status'] != 200:
            raise ValueError(f'{path.name}: source did not return HTTP 200')
        receipts.append(receipt)
        reader = pdfium.PdfDocument(str(path))
        title = reader[0].get_textpage().get_text_range().strip()
        dates = source_dates(title)
        doc = SourceDocument(id=uid(receipt['sha256']), canonical_url=receipt['url'],
            final_url=receipt['final_url'], publisher=company.legal_name,
            origin_family_id=f'issuer:{company.id}', title=title,
            document_type='issuer_investor_presentation', retrieved_at=receipt['retrieved_at'],
            published_at=f'{dates[0]}T00:00:00Z' if len(dates) == 1 else None,
            content_hash=receipt['sha256'], mime_type='application/pdf',
            local_object_key=receipt['local_path'],
            cutoff_eligibility_basis='publication_date' if len(dates) == 1 else 'verified_retrieval')
        report.documents.append(doc)
        for index in range(len(reader)):
            text = reader[index].get_textpage().get_text_range()
            page = Passage(id=uid(f'{doc.id}/{index}'), document_id=doc.id,
                page_index=index, text=text, extraction_method='pdfium')
            batch = comparative_bank_batch(page, company, document_issuer_verified=True,
                                           preferred_scope='standalone')
            if batch:
                report.passages.append(page)
                for candidate in batch.facts:
                    result = validate_candidate(candidate, page, company.id, company.business_profiles[0])
                    if not result.fact:
                        raise ValueError(f'{path.name}/{index}: {result.reason}')
                    report.facts.append(result.fact)
            for number, paragraph in enumerate(re.split(r'\r?\n\s*\r?\n', text)):
                if len(paragraph.strip()) >= 40:
                    report.passages.append(Passage(id=uid(f'{doc.id}/{index}/paragraph/{number}'),
                        document_id=doc.id, page_index=index, text=paragraph,
                        extraction_method='pdfium'))
    report.calculations = derive_calculations(report.facts)
    calculation = max([c for c in report.calculations if c.formula_id == 'deposit_borrowing_mix_change'
                       and c.scope.value == 'standalone'], key=lambda c: c.period or '')
    peers = []
    for symbol in ['ICICIBANK', 'AXISBANK']:
        peer = ResearchReport.model_validate(read_json(FIXTURE_DIR / f'{symbol}.json'))
        selected = {}
        for fact in peer.facts:
            if (fact.metric_key == 'deposits' and fact.scope.value == 'standalone'
                    and fact.period_end in {date(2025, 3, 31), date(2026, 3, 31)}):
                selected.setdefault(fact.period_end, fact)
        pids = {f.passage_id for f in selected.values()}
        passages = [p for p in peer.passages if p.id in pids]
        dids = {p.document_id for p in passages}
        peers.append({'company': peer.company.model_dump(mode='json'),
            'facts': [f.model_dump(mode='json') for f in selected.values()],
            'passages': [p.model_dump(mode='json') for p in passages],
            'documents': [d.model_dump(mode='json') for d in peer.documents if d.id in dids]})
    review = observed_report(report, calculation, significance=[
        'Growth in the deposit balance does not necessarily raise deposits’ share of this '
        'funding denominator when reported borrowings also expand.',
        'The history uses the issuer’s SBI SOLO columns. SBI GROUP columns and net advances '
        'are kept separate rather than substituted into the standalone funding ratio.',
        'The eight observed quarter ends provide a funding-mix history; they do not by '
        'themselves identify the economic cause or the true onset of a funding change.',
    ], counterargument='Borrowings can support balance-sheet deployment and financing choices '
        'rather than indicate a deposit shortage. Other liabilities, currency composition, '
        'liquidity buffers and lending quality are outside this accounting denominator.',
        review_note='Opened the original SBI FY23–FY26 and Q1 FY27 analyst PDFs, reviewed '
        'the explicit SBI SOLO/SBI GROUP balance columns and monetary scale, and reproduced '
        'the reported deposits and borrowings series without provider requests.',
        peer_sources=peers, limitations=[
            'Peer comparisons are annual deposit growth at March 2025/2026; they do not '
            'establish a matched June-quarter funding-mix median.',
            'The denominator excludes other liabilities and is not a liquidity-stress test. '
            'No causal explanation or true onset is established.',
            'There is no September 2026 result in this evidence snapshot. The latest '
            'verified quarter is June 2026; no later figures are estimated.',
        ])
    save_input(report, review, '500112', receipts)
    print('SBIN:', len(report.facts), 'facts;', len(report.passages), 'passages')


if __name__ == '__main__':
    functions = {'ICICIBANK': icici, 'AXISBANK': axis, 'KOTAKBANK': kotak, 'SBIN': sbi}
    for symbol in sys.argv[1:] or ['ICICIBANK']:
        functions[symbol.upper()]()
