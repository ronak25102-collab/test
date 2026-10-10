"""Bounded financial-document leads from verified issuer index pages."""
from __future__ import annotations

import re
from urllib.parse import unquote, urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

from signal_research.providers.search.base import SearchHit

from .metadata import domain_matches
from .url_policy import UnsafeURL, validate_public_url

BANK_DISCLOSURE_INDEXES = {
    "AXISBANK": "https://www.axis.bank.in/shareholders-corner/financial-results-and-other-presentation",
    "HDFCBANK": "https://www.hdfc.bank.in/about-us/investor-relations/financial-results",
    "ICICIBANK": "https://www.icici.bank.in/about-us/invest-relations",
    "KOTAKBANK": "https://www.kotak.bank.in/en/investor-relations/financial-results.html",
    "SBIN": "https://sbi.bank.in/web/investor-relations/analyst-presentation",
}


def verified_disclosure_indexes(company) -> list[SearchHit]:
    """Stable issuer indexes provide leads even when search indexing is incomplete."""
    hits = []
    for symbol in company.symbols:
        url = BANK_DISCLOSURE_INDEXES.get(symbol.upper())
        if url and any(domain_matches(urlparse(url).hostname or "", d) for d in company.verified_ir_domains):
            hits.append(SearchHit(url, "Official financial results index", "Index lead; underlying document dates require verification", 1, "issuer_index"))
    return hits


def linked_disclosures(raw: bytes, page_url: str, domains: list[str], limit: int = 4, *, issuer_name: str | None = None) -> list[SearchHit]:
    if not any(domain_matches(urlparse(page_url).hostname or "", domain) for domain in domains):
        return []
    soup = BeautifulSoup(raw, "html.parser")
    for element in soup(["nav", "header", "footer", "script", "style"]):
        element.decompose()
    leads = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        url = urldefrag(urljoin(page_url, anchor["href"]))[0]
        host = urlparse(url).hostname or ""
        label = anchor.get_text(" ", strip=True) or anchor.get("aria-label") or anchor.get("title") or ""
        if ".pdf" not in urlparse(url).path.lower() or not any(domain_matches(host, domain) for domain in domains):
            continue
        # Many bank result pages use icon-only download links. Their filename
        # is a lead label, never evidence of a value or publication date.
        filename = re.sub(r"[-_]", " ", unquote(urlparse(url).path.rsplit("/", 1)[-1]))
        description = label + " " + filename
        path_label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", unquote(urlparse(url).path))
        path_label = re.sub(r"[-_/]", " ", path_label)
        financial_path = bool(re.search(r"financial\s+results?", path_label, re.I))
        financial_file = bool(re.search(r"press\s+(?:table|release)|financial\s+statements?", filename, re.I))
        if not (re.search(r"annual\s+report|(?:annual|quarterly|financial)\s+results|(?:analyst|investor)\s+presentation", description, re.I)
                or (financial_path and financial_file)):
            continue
        # Issuer portals can also list subsidiary presentations. Explicit company
        # prefixes distinguish these leads without trusting shared branding.
        if issuer_name and ":" in label:
            prefix = label.split(":", 1)[0].strip().lower()
            if prefix.startswith(issuer_name.split()[0].lower()) and prefix != issuer_name.lower():
                continue
        try:
            validate_public_url(url, resolve_dns=False)
        except UnsafeURL:
            continue
        if url in seen:
            continue
        seen.add(url)
        # Labels rank leads only; they never authorize cutoff eligibility.
        full_years = re.findall(r"(?<!\d)20\d{2}(?!\d)", description)
        fiscal_years = re.findall(r"FY\s*(\d{2})(?!\d)", description, re.I)
        year = max([int(value) for value in full_years] + [2000 + int(value) for value in fiscal_years], default=0)
        # Short dated results are usually more useful than a large annual report
        # for retrieving comparable balance figures within the parsing budget.
        financial = int(bool(re.search(r"financial\s+results", description, re.I)) or (financial_path and financial_file))
        leads.append((year, financial, SearchHit(url, label or filename, "Linked issuer document; publication date requires source verification", len(leads) + 1, "issuer_link")))
    leads.sort(key=lambda item: item[:2], reverse=True)
    return [hit for _, _, hit in leads[:limit]]
