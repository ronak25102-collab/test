import json
import re
from datetime import UTC, datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup


def publication_day(timestamp):
    return timestamp.astimezone(ZoneInfo("Asia/Kolkata")).date()


def domain_matches(host, domain):
    host, domain = host.lower().rstrip("."), domain.lower().rstrip(".")
    return host == domain or host.endswith("." + domain)


def source_publication(raw, text):
    """Only source-owned explicit publication dates; never search dates or balance dates."""
    is_xml = raw.lstrip().startswith(b"<?xml") or b"<xbrli:xbrl" in raw[:1000]
    soup = BeautifulSoup(raw, "html.parser") if not raw.startswith(b"%PDF") and not is_xml else None
    dates = []
    if is_xml:
        from defusedxml import ElementTree
        try:
            root = ElementTree.fromstring(raw)
            dates.extend(element.text for element in root.iter() if element.tag.rsplit("}", 1)[-1].lower() in {"datepublished", "publicationdate", "filingdate"})
        except ElementTree.ParseError:
            pass
    if soup:
        for tag in soup.select('meta[property="article:published_time"], meta[name="date"], meta[name="DC.date.issued"], meta[itemprop="datePublished"], time[itemprop="datePublished"]'):
            dates.append(tag.get("content") or tag.get("datetime") or tag.get_text())
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.get_text())
                nodes = data if isinstance(data, list) else [data]
                for node in nodes:
                    if isinstance(node, dict):
                        dates.append(node.get("datePublished", ""))
                        for child in node.get("@graph", []):
                            dates.append(child.get("datePublished", ""))
            except (ValueError, TypeError):
                continue
    dates += re.findall(r"(?:published(?:\s+on)?|publication\s+date|dated)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]+\s+\d{4})", text, flags=re.I)
    for value in dates:
        if not isinstance(value, str):
            continue
        for fmt in (None, "%d %B %Y", "%d %b %Y"):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if fmt is None else datetime.strptime(value, fmt)
                return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
            except ValueError:
                pass
    return None


def source_origin(url, company, title, text):
    host = (urlparse(url).hostname or "").lower()
    issuer = any(domain_matches(host, d) for d in company.verified_ir_domains)
    exchange = any(domain_matches(host, d) for d in ("nseindia.com", "bseindia.com"))
    # Exchange copies of issuer announcements share the issuer origin.
    name = re.sub(r"\b(limited|ltd)\b\.?", "", company.legal_name.lower()).strip()
    identity = name in text.lower() or (company.isin and company.isin in text)
    issuer_copy = exchange and identity and any(word in title.lower() for word in ("results", "annual report", "presentation", "disclosure"))
    if issuer or issuer_copy:
        return company.legal_name, f"issuer:{company.id}", "issuer_disclosure"
    wire = re.search(r"(?:source|by|copyright|©)\s*[:\-]?\s*(Reuters|PTI|Bloomberg|Associated Press)\b", text[:3000], flags=re.I)
    if wire:
        return wire.group(1), "wire:" + wire.group(1).lower(), "public_context"
    # Different subdomains of the same publisher are a single origin.
    parts = host.split(".")
    suffix_len = 3 if host.endswith((".co.in", ".org.in", ".gov.in", ".co.uk")) else 2
    family = ".".join(parts[-suffix_len:])
    return host, family, "public_context"
