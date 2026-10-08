from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", query, ""))


def normalized_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def origin_family(publisher: str, title: str, text: str) -> str:
    # Issuer copies can be recognized by the issuer/title and stable text hash;
    # callers may override this with a known originating-author family.
    seed = f"{publisher.lower().strip()}|{title.lower().strip()}|{normalized_text(text)[:1200]}"
    return hashlib.sha256(seed.encode()).hexdigest()[:24]
