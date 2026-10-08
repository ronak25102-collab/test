from signal_research.api.exports import safe_csv


def test_csv_formula_injection_is_escaped():
    assert safe_csv("=cmd|'/C calc'!A0").startswith("'")
    assert safe_csv("normal") == "normal"
