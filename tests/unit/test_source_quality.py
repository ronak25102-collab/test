from datetime import UTC, datetime

from signal_research.retrieval.quality import format_prose, sane_publication


def test_impossible_annual_publication_is_unknown_not_a_balance_date():
    published, warning = sane_publication(b'%PDF', 'Integrated Annual Report', 'Annual Report 2023-24', datetime(2024, 2, 28, tzinfo=UTC))
    assert published is None and warning


def test_prose_preserves_years_but_formats_raw_precision():
    assert format_prose('Borrowings were 206765.5655 crore in 2023.') == 'Borrowings were 2,06,765.57 crore in 2023.'
    assert format_prose('INR 100000 crore at 2026-03-31.') == 'INR 1,00,000.00 crore at 2026-03-31.'
    assert format_prose('INR -206765.5 crore in 2023–24.') == 'INR -2,06,765.50 crore in 2023–24.'
