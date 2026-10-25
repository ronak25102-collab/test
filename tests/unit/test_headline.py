from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from signal_research.domain.enums import VerificationStatus
from signal_research.domain.schemas import Fact
from signal_research.finance.calculations import calculate, numeric_fact
from signal_research.research.headline import validate_headline


def test_headline_rejects_new_numbers_jargon_long_text_and_multiple_sentences():
    facts = [SimpleNamespace(value_decimal=Decimal('69'), unit_normalized='percent', period_start=None, period_end=date(y, 3, 31)) for y in (2023, 2026)]
    good = 'Example Finance restored 69% of its pre-event funding mix from 2023 to 2026.'
    assert not validate_headline(good, 'Example Finance', facts, [])
    for bad in [good + ' Another sentence.', good.replace('69%', '78%'), good.replace('funding mix', 'CASA'),
                good.replace('restored', ' '.join(['word'] * 36))]:
        assert validate_headline(bad, 'Example Finance', facts, [])
    assert validate_headline(good.replace('69%', '69 crore'), 'Example Finance', facts, [])


def test_three_invalid_writer_attempts_use_the_source_bound_template(store):
    from signal_research.research.live import LiveResearch
    from signal_research.research.report_builder import build_synthetic_report
    report = build_synthetic_report(uuid4(), store.search_companies('SYNTHBANK')[0], date(2026, 10, 15))
    research = LiveResearch.__new__(LiveResearch)
    research.run_id, research.structural_breaks = report.run_id, []
    research.settings = SimpleNamespace(model_request_timeout_seconds=40, stage_request_seconds={'verifying':40})
    research.budget = SimpleNamespace(remaining_seconds=lambda: 120)
    attempts = []
    def generate(schema, payload, **kwargs):
        attempts.append(payload)
        return schema(sentence='Invented Company gained 999% without a verified period.')
    research.calls = SimpleNamespace(model=generate)
    research.write_plain_headline(report)
    assert len(attempts) == 3
    assert report.generation_metadata['headline']['method'] == 'verified_arithmetic_template'
    assert not validate_headline(report.discoveries[0].discovery_sentence, report.company.legal_name, report.facts, report.calculations)


def test_recovery_is_reproduced_from_verified_ordered_ratio_facts():
    entity = uuid4()
    facts = [Fact(id=uuid4(), entity_id=entity, metric_key='casa_ratio', value_decimal=value,
                  unit_normalized='percent', period_type='instant', scope='standalone',
                  period_end=f'{year}-03-31', definition_id='casa_as_reported_v1', passage_id=uuid4(), status='verified')
             for year, value in [(2026, '43.8'), (2024, '30'), (2023, '50')]]
    result = calculate('recovery_ratio', [numeric_fact(f) for f in facts])
    assert result.available and result.output_value == 69
    assert not calculate('recovery_ratio', [numeric_fact(f) for f in reversed(facts)]).available


def test_funding_mix_template_keeps_denominator_scope_and_actual_quarter_span():
    from signal_research.research.headline import template_headline
    from signal_research.research.live import derive_calculations
    company = SimpleNamespace(legal_name='Quartz Financial Bank Limited')
    facts = [Fact(id=uuid4(), entity_id=uuid4(), metric_key=metric, value_decimal=value,
        unit_normalized='INR_crore', currency='INR', period_type='instant', scope='consolidated',
        period_end=date(year, 6, 30), definition_id=metric, passage_id=uuid4(), status='verified')
        for metric, year, value in [('deposits',2025,100),('deposits',2026,120),('borrowings',2025,30),('borrowings',2026,25)]]
    # All observations belong to one issuer, with exact verified lane inputs.
    for f in facts:
        f.entity_id = facts[0].entity_id
    calculations = derive_calculations(facts)
    text, selected = template_headline(company, facts, calculations)
    assert selected.formula_id == 'deposit_borrowing_mix_change'
    assert 'deposits plus borrowings' in text and 'consolidated' in text
    assert 'June 2025 to June 2026' in text
    assert not validate_headline(text, company.legal_name, facts, calculations)


def test_growth_gap_labels_follow_formula_input_order_when_report_facts_are_interleaved():
    from signal_research.domain.schemas import Calculation
    from signal_research.research.headline import template_headline
    entity = uuid4()
    facts = [Fact(id=uuid4(), entity_id=entity, metric_key=metric, value_decimal=value,
                  unit_normalized='INR_crore', currency='INR', period_type='duration',
                  scope='standalone', period_start=f'{year}-04-01', period_end=f'{year}-06-30',
                  definition_id=metric, passage_id=uuid4(), status='verified')
             for metric, year, value in [('revenue', 2026, 200), ('net_profit', 2026, 40),
                                         ('revenue', 2025, 100), ('net_profit', 2025, 30)]]
    result = calculate('growth_gap', [numeric_fact(facts[i]) for i in [1, 3, 0, 2]])
    assert result.available
    calculation = Calculation(id=result.id, formula_id=result.formula_id,
        formula_version=result.formula_version, input_fact_ids=result.input_fact_ids,
        output_value=result.output_value, unit=result.unit)
    text, _ = template_headline(SimpleNamespace(legal_name='Example Finance'), facts, [calculation])
    assert 'net profit versus revenue growth gap' in text


def reviewed_headline_fixture(store):
    from signal_research.research.live import LiveResearch
    from signal_research.research.report_builder import build_synthetic_report
    report = build_synthetic_report(uuid4(), store.search_companies('SYNTHBANK')[0], date(2026, 10, 15))
    discovery = report.discoveries[0]
    technical = next(claim for claim in report.claims if claim.text == discovery.discovery_sentence)
    technical.text = 'SYNTHBANK recorded a 10 percentage point difference between advances and deposit growth from 2025 to 2026.'
    discovery.discovery_sentence = technical.text
    research = LiveResearch.__new__(LiveResearch)
    research.run_id, research.structural_breaks = report.run_id, []
    research.settings = SimpleNamespace(model_request_timeout_seconds=40, stage_request_seconds={'verifying':40})
    research.budget = SimpleNamespace(remaining_seconds=lambda: 120)
    return research, report, technical


def test_optional_rewrite_cannot_consume_finalization_after_financial_review(store):
    research, report, technical = reviewed_headline_fixture(store)
    technical.text += ' This extra sentence forces the short-headline path.'
    report.discoveries[0].discovery_sentence = technical.text
    research.budget = SimpleNamespace(remaining_seconds=lambda: 80)
    research.calls = SimpleNamespace(model=lambda *a, **k: (_ for _ in ()).throw(AssertionError('Optional provider call')))
    research.write_plain_headline(report)
    assert report.generation_metadata['headline']['method'] == 'verified_arithmetic_template'
    assert report.generation_metadata['headline']['technical_detail'] == technical.text
    assert not validate_headline(report.discoveries[0].discovery_sentence, report.company.legal_name, report.facts, report.calculations)


def test_already_reviewed_valid_headline_preserves_exact_claim_without_provider_calls(store):
    research, report, technical = reviewed_headline_fixture(store)
    def no_request(*args, **kwargs):
        raise AssertionError('An unchanged, independently reviewed valid headline needs no provider request')
    research.calls = SimpleNamespace(model=no_request)
    original_claims = [claim.model_dump() for claim in report.claims]
    original_discovery = report.discoveries[0].model_dump()
    assert technical.verification_status == VerificationStatus.SUPPORTED
    assert not validate_headline(technical.text, report.company.legal_name, report.facts, report.calculations)
    research.write_plain_headline(report)
    metadata = report.generation_metadata['headline']
    assert metadata['method'] == 'already_reviewed_headline'
    assert metadata['claim_id'] == metadata['technical_claim_id'] == str(technical.id)
    assert metadata['technical_detail'] == technical.text and metadata['validation_errors'] == []
    assert [claim.model_dump() for claim in report.claims] == original_claims
    assert report.discoveries[0].model_dump() == original_discovery
    assert set(report.discoveries[0].evidence_claim_ids) <= {claim.id for claim in report.claims}


@pytest.mark.parametrize('unavailable', ['unreviewed', 'structural_break'])
def test_valid_text_does_not_skip_review_when_claim_is_unreviewed_or_break_backed(store, unavailable):
    research, report, technical = reviewed_headline_fixture(store)
    if unavailable == 'unreviewed':
        technical.verification_status = VerificationStatus.PENDING
    else:
        research.structural_breaks = [{'fact_ids': [str(f.id) for f in report.facts if f.metric_key == 'gross_advances']}]
    attempts = []
    def invalid_writer(schema, payload, **kwargs):
        attempts.append(payload)
        return schema(sentence='Unverified Company grew 999% from 2000 to 2001.')
    research.calls = SimpleNamespace(model=invalid_writer)
    research.write_plain_headline(report)
    assert len(attempts) == 3
    assert report.generation_metadata['headline']['method'] == 'verified_arithmetic_template'
    if unavailable == 'structural_break':
        from signal_research.research.structural import break_calculations
        headline = next(c for c in report.claims if str(c.id) == report.generation_metadata['headline']['claim_id'])
        assert not set(headline.calculation_ids) & break_calculations(research.structural_breaks, report.calculations)
