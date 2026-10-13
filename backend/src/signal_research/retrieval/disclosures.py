"""Bounded financial-document leads from verified issuer index pages."""
from __future__ import annotations

import re
from urllib.parse import unquote, urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

from signal_research.providers.search.base import SearchHit

from .metadata import domain_matches
from .url_policy import UnsafeURL, validate_public_url


def verified_disclosure_indexes(company) -> list[SearchHit]:
    """Company-neutral entry points; search and page links locate actual reports."""
    hits = []
    for domain in company.verified_ir_domains[:1]:
        url = f"https://{domain}/"
        try:
            validate_public_url(url, resolve_dns=False)
        except UnsafeURL:
            continue
        hits.append(SearchHit(url, "Official issuer website", "Navigation lead; not financial evidence", 1, "issuer_index"))
    return hits


def issuer_navigation(raw: bytes, page_url: str, domains: list[str], limit: int = 3) -> list[SearchHit]:
    """Bounded same-issuer navigation; labels are leads, never evidence."""
    if not any(domain_matches(urlparse(page_url).hostname or "", domain) for domain in domains):
        return []
    hits, seen = [], set()
    for anchor in BeautifulSoup(raw, "html.parser").find_all("a", href=True):
        label = anchor.get_text(" ", strip=True) or anchor.get("aria-label", "")
        try:
            url = urldefrag(urljoin(page_url, anchor["href"]))[0]
            validate_public_url(url, resolve_dns=False)
        except ValueError:
            continue
        if not re.search(r"investor\s*relations|financials?|financial\s*results|annual\s*reports?|shareholders", label, re.I):
            continue
        if url == page_url or url in seen or ".pdf" in urlparse(url).path.lower():
            continue
        if not any(domain_matches(urlparse(url).hostname or "", domain) for domain in domains):
            continue
        try:
            validate_public_url(url, resolve_dns=False)
        except UnsafeURL:
            continue
        seen.add(url)
        hits.append(SearchHit(url, label, "Issuer navigation lead", len(hits) + 1, "issuer_navigation"))
        if len(hits) == limit:
            break
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
        try:
            url = urldefrag(urljoin(page_url, anchor["href"]))[0]
            validate_public_url(url, resolve_dns=False)
        except ValueError:
            continue
        host = urlparse(url).hostname or ""
        label = anchor.get_text(" ", strip=True) or anchor.get("aria-label") or anchor.get("title") or ""
        pdf_lead = (".pdf" in urlparse(url).path.lower() or
                    bool(re.search(r"(?:^|&)fmt=pdf(?:&|$)", urlparse(url).query, re.I)) or
                    anchor.get('type') == 'application/pdf')
        if not pdf_lead or not any(domain_matches(host, domain) for domain in domains):
            continue
        # Many bank result pages use icon-only download links. Their filename
        # is a lead label, never evidence of a value or publication date.
        filename = re.sub(r"[-_]", " ", unquote(urlparse(url).path.rsplit("/", 1)[-1]))
        description = label + " " + filename
        path_label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", unquote(urlparse(url).path))
        path_label = re.sub(r"[-_/]", " ", path_label)
        financial_path = bool(re.search(r"financial\s+results?|\bfinancials\b|investor\s+presentations?", path_label, re.I))
        financial_file = bool(re.search(r"press\s+(?:table|release)|financial\s+statements?", filename, re.I))
        if not (re.search(r"annual\s+report|(?:annual|quarterly|financial)\s+results|(?:analyst|investor)\s+presentation|earnings\s+(?:conference\s+)?call|call\s+transcript", description, re.I)
                or (financial_path and (financial_file or re.search(r"\bQ[1-4]\s*FY\s*\d{2,4}\b", description, re.I)))):
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
