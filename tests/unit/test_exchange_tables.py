from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from signal_research.domain.enums import Profile, Scope
from signal_research.extraction.validate import validate_candidate
from signal_research.research.identity import issuer_cover_identity, structured_issuer_identity
from signal_research.retrieval.exchange_tables import exchange_table_batch
from signal_research.retrieval.metadata import source_origin
from signal_research.retrieval.passages import parse_html


def filing(name='Quartz Financial Services Limited', symbol='QFS', scope='Consolidated'):
    return f'''<html><title>NBFC details</title><table>
    <tr><td>Name of company</td><td>{name}</td></tr>
    <tr><td>NSE Symbol</td><td>{symbol}</td></tr>
    <tr><td>Description of presentation currency</td><td>INR</td></tr>
    <tr><td>Level of rounding used in financial results</td><td>Lakhs</td></tr></table>
    <h3>Financial Results</h3><table>
    <tr><th>Particulars</th><th>3 months/ 6 months ended (dd-mm-yyyy)</th><th>Year to date figures for current period</th></tr>
    <tr><td>A</td><td>Date of start of reporting period</td><td>01-01-2026</td><td>01-04-2025</td></tr>
    <tr><td>B</td><td>Date of end of reporting period</td><td>31-03-2026</td><td>31-03-2026</td></tr>
    <tr><td>D</td><td>Nature of report standalone or consolidated</td><td>{scope}</td><td>{scope}</td></tr>
    <tr><td></td><td>Total Revenue From Operations</td><td>12,000.00</td><td>40,000.00</td></tr>
    <tr><td>11</td><td>Net Profit Loss for the period from continuing operations</td><td>2,100.00</td><td>7,000.00</td></tr>
    <tr><td>15</td><td>Total profit (loss) for period</td><td>2,000.00</td><td>6,000.00</td></tr>
    </table></html>'''.encode()


def company():
    return SimpleNamespace(id=uuid4(), legal_name='Quartz Financial Services',
                           symbols=['QFS'], aliases=[], verified_ir_domains=['issuer.example'])


def test_exchange_columns_keep_quarter_and_year_separate_and_convert_lakhs():
    target = company()
    parsed = parse_html(uuid4(), filing())
    assert parsed.extraction_method == 'exchange_table' and len(parsed.passages) == 2
    candidates = [fact for passage in parsed.passages
                  for fact in exchange_table_batch(passage, target, Profile.DIVERSIFIED).facts]
    assert len(candidates) == 4
    assert {f.period_start for f in candidates} == {date(2026, 1, 1), date(2025, 4, 1)}
    verified = [validate_candidate(fact, passage, target.id, Profile.DIVERSIFIED)
                for passage in parsed.passages
                for fact in exchange_table_batch(passage, target, Profile.DIVERSIFIED).facts]
    assert all(v.fact and not v.reason for v in verified)
    assert {v.fact.value_decimal for v in verified} == {Decimal('120'), Decimal('400'), Decimal('20'), Decimal('60')}
    assert all(f.value_raw not in {'2,100.00', '7,000.00'} for f in candidates)
    text = '\n'.join(p.text for p in parsed.passages)
    assert source_origin('https://nsearchives.nseindia.com/filing.html', target, '', text)[2] == 'issuer_disclosure'
    assert source_origin('https://broker.example/filing.html', target, '', text)[2] == 'public_context'


def test_banking_exchange_identity_uses_the_explicit_bank_name_and_symbol():
    target = company()
    raw = filing().replace(b'Name of company', b'Name of bank')
    parsed = parse_html(uuid4(), raw)
    assert len(parsed.passages) == 2
    assert structured_issuer_identity('\n'.join(p.text for p in parsed.passages), target)
    foreign = parse_html(uuid4(), raw.replace(b'Quartz Financial Services Limited', b'Different Bank Limited'))
    assert not structured_issuer_identity('\n'.join(p.text for p in foreign.passages), target)


@pytest.mark.parametrize('name,symbol', [('Different Financial Limited', 'QFS'),
                                       ('Quartz Financial Services Limited', 'OTHER')])
def test_other_issuer_or_symbol_cannot_supply_facts(name, symbol):
    target = company()
    parsed = parse_html(uuid4(), filing(name, symbol))
    assert all(exchange_table_batch(p, target, Profile.DIVERSIFIED) is None for p in parsed.passages)
    assert not structured_issuer_identity('\n'.join(p.text for p in parsed.passages), target)


@pytest.mark.parametrize('old,new', [('31-03-2026', '31-02-2026'),
                                    ('INR', 'USD'), ('Lakhs', 'unknown'), ('Consolidated', 'unclear')])
def test_missing_or_invalid_binding_does_not_create_exchange_candidates(old, new):
    parsed = parse_html(uuid4(), filing().replace(old.encode(), new.encode()))
    assert not any(exchange_table_batch(p, company(), Profile.DIVERSIFIED) for p in parsed.passages)


def test_one_invalid_interval_does_not_contaminate_another_column():
    parsed = parse_html(uuid4(), filing().replace(b'01-01-2026', b'missing'))
    assert len(parsed.passages) == 1
    batch = exchange_table_batch(parsed.passages[0], company(), Profile.DIVERSIFIED)
    assert batch and all(f.period_start == date(2025, 4, 1) for f in batch.facts)


def test_exact_issuer_signature_is_accepted_but_passing_mentions_are_not():
    target = company()
    assert issuer_cover_identity('For Quartz Financial Services Limited', target)
    assert not issuer_cover_identity('We reviewed Quartz Financial Services Limited results', target)
    assert issuer_cover_identity('To the Members of Quartz Financial Services Limited', target)
    assert issuer_cover_identity('To the Board of Directors of Quartz Financial Services Limited', target)
    assert not issuer_cover_identity('Report to the Members of Different Finance Limited mentions Quartz Financial Services Limited', target)


def test_identical_quarter_and_ytd_columns_are_deduplicated():
    raw = filing().replace(b'01-04-2025', b'01-01-2026').replace(b'40,000.00', b'12,000.00').replace(b'7,000.00', b'2,100.00').replace(b'6,000.00', b'2,000.00')
    assert len(parse_html(uuid4(), raw).passages) == 1


def test_scope_question_label_cannot_authorize_the_wrong_scope():
    target = company()
    passage = parse_html(uuid4(), filing()).passages[0]
    candidate = exchange_table_batch(passage, target, Profile.DIVERSIFIED).facts[0]
    assert validate_candidate(candidate.model_copy(update={'scope': Scope.STANDALONE}),
                              passage, target.id, Profile.DIVERSIFIED).reason == 'scope is absent from the cited span'


def test_filing_notes_remain_available_for_counterevidence_review():
    raw = filing().replace(b'</html>', b'<table class="textblocktable"><tr><td>Textual Information(1)</td><td>Prior periods were reclassified after an acquisition.</td></tr></table></html>')
    parsed = parse_html(uuid4(), raw)
    assert any(p.extraction_method == 'exchange_notes' and 'reclassified after an acquisition' in p.text for p in parsed.passages)
