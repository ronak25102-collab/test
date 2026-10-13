from types import SimpleNamespace
from uuid import uuid4

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
