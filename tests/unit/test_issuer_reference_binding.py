from uuid import uuid4

from signal_research.domain.enums import Profile
from signal_research.domain.schemas import Company
from signal_research.retrieval.issuer_identity import exchange_issuer_domains


def company():
    return Company(id=uuid4(), legal_name='Quartz Financial Bank', symbols=['QFB'],
                   isin='INE000000001', business_profiles=[Profile.BANK], verified_ir_domains=['quartz.example'])


def test_a_directory_website_is_bound_to_its_own_issuer_row():
    raw = b'''<table><tr><td>Quartz Financial Bank INE000000001</td>
    <td><a href="https://new-quartz.example">Company website</a></td></tr>
    <tr><td>Different Issuer INE000000002</td>
    <td><a href="https://different.example">Company website</a></td></tr></table>'''
    text = 'Quartz Financial Bank INE000000001 Different Issuer INE000000002'
    assert exchange_issuer_domains(raw, text, 'https://nseindia.com/directory', company()) == ['new-quartz.example']


def test_global_issuer_mentions_do_not_authorize_another_company_website():
    text = ('Quartz Financial Bank INE000000001 is mentioned in an investment schedule.\n' +
            'Unrelated disclosures. ' * 30 + '\nDifferent Issuer Limited\nWebsite: https://different.example')
    assert not exchange_issuer_domains(b'%PDF', text, 'https://bseindia.com/filing.pdf', company())
    short = 'Quartz Financial Bank INE000000001 holds shares in Another Issuer Limited. Website: https://different.example'
    assert not exchange_issuer_domains(b'%PDF', short, 'https://bseindia.com/filing.pdf', company())


def test_trustee_registrar_and_depository_references_are_not_issuer_websites():
    text = ('Quartz Financial Bank INE000000001\nRegistrar and share transfer agent\n'
            'Website: https://registrar.example\nDebenture trustee\nWebsite: https://trustee.example')
    assert not exchange_issuer_domains(b'%PDF', text, 'https://quartz.example/report.pdf', company())


def test_a_bare_www_fragment_cannot_become_a_verified_domain():
    text = 'Quartz Financial Bank INE000000001\nCompany Website: www.'
    assert not exchange_issuer_domains(b'%PDF', text, 'https://bseindia.com/filing.pdf', company())


def test_an_issuer_bound_letterhead_website_remains_usable():
    text = 'Quartz Financial Bank INE000000001\nRegistered office\nWebsite: https://new-quartz.example'
    assert exchange_issuer_domains(b'%PDF', text, 'https://bseindia.com/filing.pdf', company()) == ['new-quartz.example']
