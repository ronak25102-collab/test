from __future__ import annotations

import csv
import hashlib
import io
from datetime import UTC, datetime
from uuid import uuid4

import httpx

NIFTY_URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv"


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


def refresh_universe(timeout: float = 20) -> dict:
    response = httpx.get(NIFTY_URL, timeout=timeout, follow_redirects=True, headers={"User-Agent": "SignalResearch/0.1 public-research"})
    response.raise_for_status()
    rows = parse_constituents(response.content)
    return {
        "id": str(uuid4()), "source_url": NIFTY_URL,
        "fetched_at": datetime.now(UTC).isoformat(),
        "content_hash": hashlib.sha256(response.content).hexdigest(),
        "constituents": rows, "financial_constituents": financial_constituents(rows),
        "is_cached": False,
    }
