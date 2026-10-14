"""Accept explicit website references from trusted, issuer-bound disclosures."""
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from signal_research.research.identity import issuer_named, normalize_name
from signal_research.retrieval.metadata import domain_matches
from signal_research.retrieval.url_policy import UnsafeURL, validate_public_url

ISSUER_REFERENCE_POLICY = 'issuer-reference-v2'
THIRD_PARTY_ROLE = re.compile(r'\btrustee|registrar|share\s+transfer\s+agent|depositor(?:y|ies)|auditors?|stock\s+exchanges?\b', re.I)


def reference_owner_bound(context, company):
    """Bind this reference to a nearby issuer identity, never a global mention."""
    if THIRD_PARTY_ROLE.search(context):
        return False
    prefix = re.split(r'(?:company\s+|corporate\s+|issuer\s+)?website\s*:?', context, flags=re.I)[0]
    names = [company.legal_name, *getattr(company, 'aliases', [])]
    targets = {normalize_name(name) for name in names if name == company.legal_name or len(normalize_name(name).split()) >= 2}
    for line in reversed(prefix.splitlines()[-8:]):
        line = line.replace(company.isin or '\0', '')
        line = re.sub(r'^\s*(?:company\s+name|name\s+of\s+(?:the\s+)?issuer|issuer|company)\s*:\s*', '', line, flags=re.I)
        if normalize_name(line) in targets:
            return True
        if re.search(r'\b(?:Limited|Ltd|Bank|Insurance|Exchange|Company)\b', line, re.I):
            return False  # A different nearby owner supersedes a distant mention.
    return False


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
                row = anchor.find_parent('tr')
                if row is not None:
                    context = row.get_text(' ', strip=True)
                    if reference_owner_bound(context, company) and (not company.isin or company.isin in context):
                        candidates.append(anchor['href'])
                    continue
                bound = False
                for parent in anchor.parents:
                    context = parent.get_text(' ', strip=True)
                    if len(context) > 1000:
                        break
                    if reference_owner_bound(context, company) and (not company.isin or company.isin in context):
                        bound = True
                        break
                if bound or (len(text) <= 800 and reference_owner_bound(text, company)):
                    candidates.append(anchor['href'])
    for match in re.finditer(r"(?:company\s+|corporate\s+|issuer\s+)?website\s*:\s*((?:https?://|www\.)[^\s<>]+)", text, re.I):
        context = text[max(0, match.start() - 500):match.end()]
        if reference_owner_bound(context, company):
            candidates.append(match[1])
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
        if re.fullmatch(r'(?:[a-z0-9][a-z0-9-]*\.)+[a-z]{2,63}', domain) and not any(domain_matches(domain, exchange) for exchange in ("nseindia.com", "bseindia.com")):
            domains.append(domain)
    return list(dict.fromkeys(domains))[:2]
