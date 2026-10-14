"""Shared issuer identity matching; never infer an identity from a fuzzy match."""
import re


def normalize_name(value: str) -> str:
    value = re.sub(r"\b(?:limited|ltd|inc|plc)\b\.?", "", value, flags=re.I)
    normalized = " ".join(re.findall(r"[a-z0-9]+", value.lower()))
    return re.sub(r"^the\s+", "", normalized)


def identity_aliases(name: str) -> list[str]:
    normalized = normalize_name(name)
    words = [word for word in normalized.split() if word not in {"of", "and", "the"}]
    aliases = [name, normalized]
    if len(words) >= 3:
        aliases.append("".join(word[0] for word in words).upper())
    return list(dict.fromkeys(aliases))


def issuer_named(text: str, company) -> bool:
    """Full legal names/aliases authorize issuer binding; acronyms alone do not."""
    normalized = " " + normalize_name(text) + " "
    names = [company.legal_name, *getattr(company, "aliases", [])]
    return any(len(normalize_name(name).split()) >= 2 and
               " " + normalize_name(name) + " " in normalized for name in names) or (
        " " + normalize_name(company.legal_name) + " " in normalized)


def issuer_cover_identity(text: str, company) -> bool:
    """Bind a document only to a full issuer heading, not a passing mention."""
    target = normalize_name(company.legal_name)
    compact_target = re.sub(r'[^a-z0-9]', '', target)
    for line in text.splitlines():
        if normalize_name(line) == target:
            return True
        # Font letter spacing and concatenated legal suffixes can affect headings.
        # Match the complete heading only, never a substring/passing mention.
        compact = re.sub(r'[^a-z0-9]', '', line.lower())
        compact = re.sub(r'(?:limited|ltd)$', '', compact)
        if compact == compact_target:
            return True
    return False


def issuer_symbol_reference(text: str, company) -> bool:
    """Explicit own NSE symbol on a filing cover, never a bare ticker mention."""
    return any(re.search(r'\bNSE\s+(?:(?:Scrip|Security)\s+)?(?:Symbol|Code)\s*[:\-]?\s*' +
        re.escape(symbol) + r'(?![A-Za-z0-9_-])', text[:3000], re.I)
        for symbol in getattr(company, 'symbols', []))


def foreign_cover_identity(text: str, company) -> bool:
    """An explicitly named different issuer on a cover defeats passing mentions.

    Exchange addressees and generic signature headings are not company subjects.
    This is a rejection rule; absence of a foreign heading proves nothing.
    """
    target = normalize_name(company.legal_name)
    addressees = {'bse', 'national stock exchange', 'national stock exchange of india'}
    for line in text[:1500].splitlines():
        # PDF extraction can place both listing recipients on the same line.
        # Removing only these exact exchange names must leave no other owner.
        recipients = re.sub(r'\b(?:National\s+Stock\s+Exchange(?:\s+of\s+India)?|BSE)\s+(?:Limited|Ltd\.?)\b',
                            '', line, flags=re.I)
        if recipients != line and not recipients.strip(' ,;|\t'):
            continue
        match = re.fullmatch(r'\s*(?:For\s+)?([A-Za-z0-9&.,() /-]{2,120}\b(?:Limited|Ltd\.?))\s*', line, re.I)
        if not match:
            continue
        name = normalize_name(match[1])
        if name == target:
            return False
        if name in addressees or len(name.split()) < 2:
            continue
        return True
    return False
