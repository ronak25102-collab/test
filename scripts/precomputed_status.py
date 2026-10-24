"""Write measured fixture coverage without treating missing issuers as successes."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend' / 'src'))

from signal_research.domain.schemas import ResearchReport  # noqa: E402
from signal_research.precomputed.builder import (  # noqa: E402
    FIXTURE_DIR,
    fiscal_years,
    parity_shortfalls,
    read_json,
)
from signal_research.research.verifier import verify_report  # noqa: E402


def main():
    index = read_json(FIXTURE_DIR / 'index.json')
    available = {entry['symbol']: entry for entry in index['companies']}
    roster = read_json(FIXTURE_DIR / 'roster.json')['companies']
    lines = [
        '# Precomputed coverage and outstanding work', '',
        f'**{len(available)} of {len(roster)} official NIFTY 50 Track A companies have '
        'published stored fixtures. The catalog is incomplete.**', '',
        'The report schema and frontend are unchanged. Playback is offline and defaults '
        'to 120 seconds, using the database start time. New run IDs own remapped report '
        'and evidence IDs; original review receipts retain their original identities.', '',
        '| Company | Symbol | Discovery | Strength | Fiscal years observed | Data as of | '
        'Report documents | Verifier | Minimum parity |',
        '| --- | --- | --- | --- | --- | --- | ---: | --- | --- |',
    ]
    details = []
    order = ['HDFCBANK', 'JIOFIN', 'ICICIBANK', 'SBIN', 'BAJFINANCE',
             'KOTAKBANK', 'AXISBANK', 'BSE', 'BAJAJFINSV', 'HDFCLIFE', 'SBILIFE', 'SHRIRAMFIN']
    by_symbol = {entry['symbol']: entry for entry in roster}
    for symbol in order:
        entry = by_symbol[symbol]
        if symbol not in available:
            lines.append(f'| {entry["legal_name"]} | {symbol} | Not published | — | — | — | '
                         '— | Not run | Not passed |')
            details += [f'## {symbol}: incomplete', '',
                'Research-only YAML is present. Missing: reviewed discovery/significance, '
                'bound financial history, matched peer series, and final report/evidence/export '
                'parity. Downloaded leads and identity receipts are not published findings. '
                'The API returns the existing unsupported error and never substitutes '
                'another company’s report.', '']
            continue
        report = ResearchReport.model_validate(read_json(FIXTURE_DIR / f'{symbol}.json'))
        verify_report(report)
        years = ', '.join(f'FY{year % 100:02}' for year in fiscal_years(report))
        metadata = report.generation_metadata
        headline = report.discoveries[0].discovery_sentence.replace('|', '/')
        gaps = parity_shortfalls(report)
        lines.append(f'| {entry["legal_name"]} | {symbol} | {headline} | '
                     f'{report.discoveries[0].evidence_strength.value} | {years} | '
                     f'{metadata["data_as_of"]} | {len(report.documents)} | Passed | '
                     f'{"Passed" if not gaps else "; ".join(gaps)} |')
        details += [f'## {symbol}: measured evidence', '',
            f'{len(report.documents)} documents; {len(report.passages)} passages; '
            f'{len(report.facts)} verified facts; {len(report.calculations)} reproducible calculations.', '',
            report.historical_coverage, '',
            'Relevant limitations:', '',
            *['- ' + limitation for limitation in report.limitations], '',
            'Source inventory (actual recorded receipt and byte digest):', '',
            '| Source | Retrieved at | SHA-256 |', '| --- | --- | --- |']
        details += [f'| [{doc.title.replace(chr(10), " ").replace(chr(13), " ").replace("|", "/")[:120]}]'
                    f'({doc.canonical_url}) | {doc.retrieved_at.isoformat()} | `{doc.content_hash}` |'
                    for doc in report.documents]
        details.append('')
    lines += ['', 'Fiscal years list verified observation dates, including partial current '
              'years; they do not imply a complete annual or quarterly history. Minimum parity '
              'means at least 6 documents, 300 real passages, 15 facts, 8 calculations, '
              '2 matched peers and observations in 3 fiscal years, with valid evidence chains. '
              'It does not assert economic equivalence of different segment boundaries, '
              'true onset, all five annual years/eight quarters, or currently accessible URLs.', '',
              '## Source availability exceptions', '',
              'Archived source byte hashes validate locally. The refresh did not establish '
              'HTTP 200 for every legacy link. No success status or replacement hash was invented.', '']
    for receipt in read_json(FIXTURE_DIR / 'references/source-link-audit.json'):
        status = receipt.get('http_status', receipt.get('status_code'))
        if receipt.get('error') or (status is not None and status != 200):
            lines.append(f'- {receipt["url"]}: {receipt.get("error") or status}.')
    lines += ['', *details]
    (ROOT / 'docs' / 'PRECOMPUTED_STATUS.md').write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')
    print(f'{len(available)}/{len(roster)} published fixtures; outstanding issuers remain explicit')


if __name__ == '__main__':
    main()
