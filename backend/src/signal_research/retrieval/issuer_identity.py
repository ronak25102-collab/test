"""Accept explicit website references from trusted, issuer-bound disclosures."""
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from signal_research.research.identity import issuer_named
from signal_research.retrieval.metadata import domain_matches
from signal_research.retrieval.url_policy import UnsafeURL, validate_public_url


def exchange_issuer_domains(raw, text, source_url, company):
    host = urlparse(source_url).hostname or ""
    trusted = ("nseindia.com", "bseindia.com", *company.verified_ir_domains)
    if not any(domain_matches(host, domain) for domain in trusted):
        return []
    if not issuer_named(text, company) or (company.isin and company.isin not in text):
        return []
    candidates = []
    if not raw.startswith(b"%PDF"):
        for anchor in BeautifulSoup(raw, "html.parser").find_all("a", href=True):
            label = anchor.get_text(" ", strip=True)
            if re.fullmatch(r"(?:company\s+|corporate\s+|issuer\s+)?website(?:\s*:\s*)?", label, re.I):
                candidates.append(anchor["href"])
    candidates += re.findall(r"(?:company\s+|corporate\s+|issuer\s+)?website\s*:\s*((?:https?://|www\.)[^\s<>]+)", text, re.I)
    domains = []
    for url in candidates:
        url = url.rstrip('.,;)')
        if url.startswith('www.'):
            url = 'https://' + url
        try:
            validate_public_url(url, resolve_dns=False)
        except UnsafeURL:
            continue
        domain = (urlparse(url).hostname or "").lower().removeprefix("www.")
        if domain and not any(domain_matches(domain, exchange) for exchange in ("nseindia.com", "bseindia.com")):
            domains.append(domain)
    return list(dict.fromkeys(domains))[:2]
