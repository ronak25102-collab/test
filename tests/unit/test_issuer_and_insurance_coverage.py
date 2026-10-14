from types import SimpleNamespace
from uuid import uuid4

import pytest
from signal_research.domain.enums import Profile
from signal_research.domain.schemas import Company, Passage
from signal_research.extraction.financial_tables import financial_table_batch
from signal_research.extraction.validate import validate_candidate
from signal_research.retrieval.disclosures import verified_disclosure_indexes
from signal_research.retrieval.metadata import source_origin


def test_both_current_and_legacy_verified_websites_have_bounded_entrypoints():
    company = SimpleNamespace(verified_ir_domains=['new.example', 'old.example', 'extra.example'])
    assert [h.url for h in verified_disclosure_indexes(company)] == ['https://new.example/', 'https://old.example/']


def test_an_exchange_audit_binds_its_subject_but_an_addressee_does_not():
    company = Company(id=uuid4(), legal_name='Quartz Exchange Limited', business_profiles=[Profile.EXCHANGE],
                      verified_ir_domains=['bseindia.com'])
    url = 'https://bseindia.com/annual-report.pdf'
    own = 'We audited the consolidated financial statements of Quartz Exchange Limited for the year ended 31 March 2026.'
    foreign = 'To Quartz Exchange Limited. We audited the consolidated financial statements of Different Issuer Limited.'
    assert source_origin(url, company, 'Annual report', own)[2] == 'issuer_disclosure'
    assert source_origin(url, company, 'Annual report', foreign)[2] == 'public_context'


@pytest.mark.parametrize('text', [
    'BSE Limited\nAnnual Report\nDelay of two days for BSE\nFor Engineering Services Limited',
    'BSE Limited\nAnnual Report\nPenalty imposed for BSE Limited shares.\nFor Other Issuer Limited',
    'BSE Limited\nAnnual Report\nFor BSE\nRegulation 23(9)',
    'We audited consolidated financial statements of BSE Securities Limited.',
])
def test_exchange_recipient_and_incidental_prepositions_never_establish_authorship(text):
    company = Company(id=uuid4(), legal_name='BSE Limited', business_profiles=[Profile.EXCHANGE],
        verified_ir_domains=['bseindia.com'])
    assert source_origin('https://bseindia.com/report.pdf', company, 'Annual Report', text)[2] == 'public_context'


@pytest.mark.parametrize('text', ['Annual Report\nFor BSE Limited\nCompany Secretary',
                                'Annual Report\nFor BSE Ltd.\nCompany Secretary',
                                'We audited the standalone financial statements of BSE Limited.'])
def test_exchange_own_full_signature_or_audited_subject_establishes_authorship(text):
    company = Company(id=uuid4(), legal_name='BSE Limited', business_profiles=[Profile.EXCHANGE],
        verified_ir_domains=['bseindia.com'])
    assert source_origin('https://bseindia.com/report.pdf', company, 'Annual Report', text)[2] == 'issuer_disclosure'


def test_exchange_copy_of_another_issuer_requires_authorship_not_a_mention():
    company = Company(id=uuid4(), legal_name='Quartz Bank', isin='INE000000001',
        business_profiles=[Profile.BANK], verified_ir_domains=['quartz.example'])
    url = 'https://bseindia.com/report.pdf'
    foreign = 'Standalone results of Another Issuer Limited. Our lender is Quartz Bank. For Another Issuer Limited.'
    own = 'Quartz Bank\nStandalone results\nFor Quartz Bank\nCompany Secretary'
    assert source_origin(url, company, 'Financial results', foreign)[2] == 'public_context'
    assert source_origin(url, company, 'Financial results', own)[1:] == (f'issuer:{company.id}', 'issuer_disclosure')


def test_named_parent_cover_defeats_a_subsidiary_mention():
    from signal_research.research.identity import foreign_cover_identity

    company = SimpleNamespace(legal_name='Quartz Finance Limited')
    foreign = '19th Annual Report\nQuartz Holdings Limited\nContents\nOur companies: Quartz Finance Limited'
    own = 'Annual Report\nQuartz Finance Limited\nOur parent is Quartz Holdings Limited'
    assert foreign_cover_identity(foreign, company)
    assert not foreign_cover_identity(own, company)
    assert not foreign_cover_identity('BSE Limited\nNational Stock Exchange of India Limited\nFor Quartz Finance Limited', company)
    assert not foreign_cover_identity('National Stock Exchange of India Limited BSE Limited\nFor Quartz Finance Limited', company)
    assert foreign_cover_identity('National Stock Exchange of India Limited BSE Limited\nQuartz Holdings Limited', company)


@pytest.mark.parametrize('text,expected', [
    ('NSE Symbol: QUARTZLIFE BSE Code: 500123', True),
    ('NSE Code: QUARTZLIFE', True),
    ('NSE Security Symbol: QUARTZLIFE', True),
    ('Holdings include QUARTZLIFE', False),
    ('NSE Symbol: QUARTZLIFEOTHER', False),
    ('NSE Symbol: QUARTZLIFE-OTHER', False),
    ('NSE Symbol: OTHERLIFE', False),
])
def test_registered_filing_symbol_requires_an_explicit_complete_cover_binding(text, expected):
    from signal_research.research.identity import issuer_symbol_reference

    company = SimpleNamespace(symbols=['QUARTZLIFE'])
    assert issuer_symbol_reference(text, company) == expected


def test_insurance_persistency_cohorts_cannot_be_collapsed_into_one_metric():
    company = SimpleNamespace(id=uuid4(), legal_name='Quartz Life Limited')
    passage = Passage(id=uuid4(), document_id=uuid4(), text=(
        'Quartz Life Limited\nStandalone\n31 March 2026 | 31 March 2025\n'
        '13th month persistency (%) | 85 | 83\n61st month persistency (%) | 64 | 63'))
    batch = financial_table_batch(passage, company, Profile.LIFE_INSURER)
    assert batch and {f.metric_key for f in batch.facts} == {'persistency_13m', 'persistency_61m'}
    for candidate in batch.facts:
        result = validate_candidate(candidate, passage, company.id, Profile.LIFE_INSURER)
        assert result.fact, result.reason


def test_british_annualised_premium_label_is_source_bound():
    company = SimpleNamespace(id=uuid4(), legal_name='Quartz Life Limited')
    passage = Passage(id=uuid4(), document_id=uuid4(), text=(
        'Quartz Life Limited\nStandalone\nINR crore\nYear ended 31 March 2026 | 31 March 2025\n'
        'Annualised premium equivalent | 120 | 100'))
    batch = financial_table_batch(passage, company, Profile.LIFE_INSURER)
    assert batch and len(batch.facts) == 2
    assert all(validate_candidate(c, passage, company.id, Profile.LIFE_INSURER).fact for c in batch.facts)
