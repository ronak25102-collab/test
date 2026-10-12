from signal_research.api.exports import safe_csv


def test_csv_formula_injection_is_escaped():
    assert safe_csv("=cmd|'/C calc'!A0").startswith("'")
    assert safe_csv("normal") == "normal"


def test_export_keeps_typed_losses_numeric_and_escapes_untrusted_document_text(store):
    import csv
    import io
    from datetime import date
    from decimal import Decimal
    from uuid import uuid4

    from signal_research.exports.csv_facts import facts_csv
    from signal_research.research.report_builder import build_synthetic_report
    report = build_synthetic_report(uuid4(), store.search_companies('SYNTHBANK')[0], date(2026, 10, 8))
    report.facts[0].value_decimal = Decimal('-123.40')
    report.facts[0].segment = '\t=HYPERLINK("https://untrusted.example")'
    row = next(csv.DictReader(io.StringIO(facts_csv(report))))
    assert Decimal(row['value_decimal']) == Decimal('-123.40')
    assert row['segment'].startswith("'")
    assert safe_csv(' \t=1+1').startswith("'")
