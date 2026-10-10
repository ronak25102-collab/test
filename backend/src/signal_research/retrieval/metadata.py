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
    # Source dates commonly use ordinals and a comma after the month. Normalize
    # punctuation only; financial period labels must still never date a source.
    text = re.sub(r"(?<=\d)(?:st|nd|rd|th)\b", "", text, flags=re.I)
    text = re.sub(r"\b([A-Za-z]+),\s*(?=\d{4}\b)", r"\1 ", text)
    date_pattern = r"\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+,?\s+\d{1,2},?\s+\d{4}|\d{2}[./-]\d{2}[./-]\d{4}"
    dates += re.findall(r"(?:published(?:\s+on)?|publication\s+date)\s*[:\-]?\s*(" + date_pattern + r")", text, flags=re.I)
    if raw.startswith(b"%PDF"):
        # A dated exchange filing cover or a formal document date identifies the
        # disclosure itself. A cited regulation/report merely described as 'dated'
        # must never supply this document's publication timing.
        filing_cover = text[:3000]
        # Rating-agency reports put their issuance date above the company and
        # rating action. This explicit cover date is not a balance-sheet date.
        rating_cover = re.match(r"^\s*(" + date_pattern + r")\s*\n([^\n]{1,300})", filing_cover)
        if rating_cover and re.search(r"ratings?\s+(?:reaffirmed|assigned|withdrawn|upgraded|downgraded)|rating\s+rationale", rating_cover[2], re.I):
            dates.append(rating_cover[1])
        if re.search(r"Ref\.?\s*(?:No\.?|:)|\b[A-Z]+/[A-Z/]+/\d", filing_cover, re.I) and re.search(r"BSE Limited|National Stock Exchange", filing_cover, re.I):
            dates += re.findall(r"^\s*(" + date_pattern + r")\s*$", filing_cover, re.I | re.M)
        dates += re.findall(r"^\s*Date\s*:\s*(" + date_pattern + r")", text, re.I | re.M)
        # Some banks sign results with a city/date dateline instead of 'Date:'.
        # Require a financial-results document and a board/issuer signature block
        # with an executive role, so reporting dates and meeting references cannot
        # become publication evidence.
        if re.search(r"\bfinancial\s+results\b", text[:3000], re.I):
            signatures = re.finditer(r"\bFor\s+(?:and\s+on\s+behalf\s+of\s+(?:the\s+)?Board(?:\s+of\s+Directors)?|[^\n]{1,100}\bBank(?:\s+Limited)?)\b([^\n]*\n[\s\S]{0,600})", text, re.I)
            for signature in signatures:
                block = signature[1]
                if re.search(r"(?:Managing|Executive)\s+Director|Chief\s+Executive\s+Officer|Chairman", block, re.I):
                    dates += re.findall(r"^\s*(?:[A-Za-z][A-Za-z ]{1,40},\s*)?(" + date_pattern + r")(?=\s|$)", block, re.I | re.M)
        # Presentation covers state the event date separately from reporting periods.
        # PDF letter spacing must not hide that explicit source-owned date.
        cover = text[:1200]
        cover = re.sub(r"\b(?:[A-Za-z]\s+){3,}[A-Za-z]\b", lambda m: re.sub(r"\s", "", m[0]), cover)
        cover = re.sub(r"(?<=\d)\s+(?=[\d.])|(?<=\.)\s+(?=\d)", "", cover)
        dates += re.findall(r"(?:analyst|investor)\s*presentation\s*[|:\-]?\s*(" + date_pattern + r")\b", cover, flags=re.I)
    for value in dates:
        if not isinstance(value, str):
            continue
        for fmt in (None, "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if fmt is None else datetime.strptime(value.replace(",", ""), fmt)
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
