from __future__ import annotations

import csv
import hashlib
import io
from datetime import UTC, datetime
from uuid import uuid4

import httpx

from signal_research.retrieval.transport import PublicTransport

NIFTY_URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv"
LISTED_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"


def parse_constituents(raw: bytes) -> list[dict[str, str]]:
    text = raw.decode("utf-8-sig", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    return [{str(k).strip(): str(v).strip() for k, v in row.items() if k is not None} for row in rows]


def financial_constituents(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    result = []
    for row in rows:
        industry = " ".join(str(row.get(k, "")) for k in ("Industry", "Sector", "ISIN Code")).lower()
        if any(term in industry for term in ("financial", "bank", "insurance", "exchange", "finance", "nbfc")):
            result.append(row)
    return result


def refresh_universe(timeout: float = 20, listed: bool = False) -> dict:
    url = LISTED_URL if listed else NIFTY_URL
    with httpx.Client(transport=PublicTransport(), trust_env=False, timeout=timeout, follow_redirects=False) as client:
        with client.stream("GET", url, headers={"User-Agent": "Beyond public-research"}) as response:
            response.raise_for_status()
            raw = bytearray()
            for chunk in response.iter_bytes():
                raw.extend(chunk)
                if len(raw) > 2_000_000:
                    raise ValueError("exchange directory exceeds size cap")
    rows = parse_constituents(bytes(raw))
    if not rows or not any("Symbol" in row or "SYMBOL" in row for row in rows):
        raise ValueError("exchange directory is not a valid constituent CSV")
    return {
        "id": str(uuid4()), "source_url": url,
        "fetched_at": datetime.now(UTC).isoformat(),
        "content_hash": hashlib.sha256(raw).hexdigest(),
        "constituents": rows, "financial_constituents": financial_constituents(rows),
        "is_cached": False,
    }
