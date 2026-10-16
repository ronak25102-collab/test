"""Bounded financial-document leads from verified issuer index pages."""
from __future__ import annotations

import json
import re
from urllib.parse import unquote, urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

from signal_research.providers.search.base import SearchHit

from .metadata import domain_matches
from .url_policy import UnsafeURL, validate_public_url


def exchange_results_query(company):
    """Disambiguate the issuer from names appearing as filing recipients."""
    if company.isin:
        return f'"{company.isin}" "financial results"'
    symbol = company.symbols[0]
    return f'"{company.legal_name}" "NSE Symbol" "{symbol}" "Name of company" "financial results"'


def verified_disclosure_indexes(company) -> list[SearchHit]:
    """Company-neutral entry points; search and page links locate actual reports."""
    hits = []
    for domain in company.verified_ir_domains[:2]:
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
        # A business name containing 'Financial' is not a report-navigation
        # label. Quote pages and peer stock links otherwise consume this cap.
        if not re.search(r"\binvestor\s*relations\b|\bfinancial\s+(?:results?|statements?|reports?|performance)\b|\bannual\s*reports?\b|\binvestor\s*presentations?\b|\bshareholders?\b|^investors?$|^financials?$", label, re.I):
            continue
        if re.search(r'(?:share|stock)[-/]?(?:price|quote)|(?:price|quote)[-/]?(?:share|stock)', urlparse(url).path, re.I):
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
        priority = (0 if re.search(r'financial\s+(?:results?|statements?)', label, re.I) else
                    1 if re.search(r'annual\s*reports?', label, re.I) else
                    2 if re.search(r'investor\s*presentations?', label, re.I) else
                    3 if re.search(r'investor\s*relations', label, re.I) else 4)
        hits.append((priority, SearchHit(url, label, "Issuer navigation lead", len(hits) + 1, "issuer_navigation")))
    hits.sort(key=lambda item: item[0])
    return [hit for _, hit in hits[:limit]]


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


def embedded_disclosures(raw: bytes, page_url: str, domains: list[str], limit: int = 4) -> list[SearchHit]:
    """Read literal public document links from portal data without executing scripts.

    Same-issuer URLs, JSON metadata and onclick literals are retrieval leads only.
    They never establish document identity, dates or claim support.
    """
    if not any(domain_matches(urlparse(page_url).hostname or '', domain) for domain in domains):
        return []
    soup = BeautifulSoup(raw, 'html.parser')
    candidates = []
    financial = re.compile(r'annual|integrated|financial|quarterly|results|investor|presentation|earnings', re.I)
    literal = re.compile(r'''["']([^"'\n]{1,2048}\.pdf(?:\?[^"'\n]{0,512})?)["']''', re.I)
    for anchor in soup.find_all(['a', 'button']):
        label = anchor.get_text(' ', strip=True) or anchor.get('aria-label', '')
        if not financial.search(label):
            continue
        for attribute in ('onclick', 'data-url', 'data-href', 'data-download'):
            value = anchor.get(attribute, '')
            if attribute == 'onclick':
                candidates.extend((match[1], label) for match in literal.finditer(value))
            elif '.pdf' in value.lower():
                candidates.append((value, label))
    def walk(value, depth=0):
        if depth > 8 or len(candidates) >= 100:
            return
        if isinstance(value, dict):
            label = ' '.join(str(v) for k, v in value.items()
                             if k.lower() in {'title', 'name', 'description', 'label', 'category', 'documenttype'} and isinstance(v, str))[:500]
            for child in value.values():
                if isinstance(child, str) and '.pdf' in child.lower():
                    candidates.append((child, label))
                elif isinstance(child, (dict, list)):
                    walk(child, depth + 1)
        elif isinstance(value, list):
            for child in value[:100]:
                walk(child, depth + 1)
    for script in soup.find_all('script'):
        data = script.string or script.get_text()
        if not data or len(data) > 512000:
            continue
        try:
            walk(json.loads(data))
        except (ValueError, TypeError):
            pass
        candidates.extend((match[1], '') for match in literal.finditer(data))
    hits, seen = [], set()
    for value, label in candidates:
        value = value.replace('\\/', '/')
        try:
            url = urldefrag(urljoin(page_url, value))[0]
            validate_public_url(url, resolve_dns=False)
            path = unquote(urlparse(url).path)
            if not path.lower().endswith('.pdf') or not any(domain_matches(urlparse(url).hostname or '', domain) for domain in domains):
                continue
        except ValueError:
            continue
        description = label + ' ' + re.sub(r'[-_/]', ' ', path)
        if url in seen or not financial.search(description):
            continue
        seen.add(url)
        hits.append(SearchHit(url, label or path.rsplit('/', 1)[-1],
                              'Literal issuer-portal document lead; verify the original document', len(hits) + 1, 'issuer_embedded_link'))
        if len(hits) == limit:
            break
    return hits
