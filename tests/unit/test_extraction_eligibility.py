from types import SimpleNamespace

from signal_research.domain.enums import Profile
from signal_research.extraction.eligibility import minimum_source_bindings


def test_model_calls_cannot_supply_an_absent_currency_scope_or_reporting_date():
    valid = 'Standalone deposits INR 100 crore as at 31 March 2026.'
    def eligible(text):
        return minimum_source_bindings(SimpleNamespace(text=text), Profile.BANK)
    assert eligible(valid)
    assert not eligible(valid.replace('INR ', ''))
    assert not eligible(valid.replace('Standalone ', ''))
    assert not eligible(valid.replace('31 March 2026', 'FY2026'))
    assert eligible('Consolidated GNPA 1.5% as at 31 March 2026.')
    assert not eligible('Cash flows and related-party borrowings are discussed elsewhere.')
