import pytest
from signal_research.retrieval.deduplicate import normalize_url, origin_family
from signal_research.retrieval.url_policy import UnsafeURL, validate_public_url


def test_url_policy_blocks_private_destinations():
    with pytest.raises(UnsafeURL):
        validate_public_url("http://127.0.0.1:8000/health", resolve_dns=False)
    with pytest.raises(UnsafeURL):
        validate_public_url("http://user:password@example.com/a", resolve_dns=False)


def test_url_normalization_preserves_filing_query_identity():
    assert normalize_url("HTTPS://Example.com/file?b=2&a=1#page") == "https://example.com/file?a=1&b=2"
    assert origin_family("Issuer", "Results", "same text") == origin_family("Issuer", "Results", "same text")
