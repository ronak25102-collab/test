from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep

import httpx

from .deduplicate import content_hash
from .transport import PublicTransport
from .url_policy import UnsafeURL, validate_public_url


@dataclass(frozen=True)
class FetchResult:
    requested_url: str
    final_url: str | None
    status: int | None
    content_type: str | None
    body_hash: str | None
    local_path: str | None
    error: str | None = None
    attempts: int = 1
    retrieved_at: str | None = None


class PublicFetcher:
    def __init__(self, data_dir: Path, timeout: float = 25, max_bytes: int = 25_000_000):
        self.data_dir = data_dir
        self.timeout = timeout
        self.max_bytes = max_bytes

    def fetch(self, url: str, retries: int = 2) -> FetchResult:
        from signal_research.precomputed.guard import require_network_allowed
        require_network_allowed()
        last_error = None
        deadline = monotonic() + self.timeout
        for attempt in range(1, retries + 2):
            try:
                current = url
                with httpx.Client(timeout=max(.1, deadline - monotonic()), follow_redirects=False, trust_env=False, transport=PublicTransport(), headers={"User-Agent": "Beyond/0.2 public-research"}) as client:
                    for redirect in range(6):
                        validate_public_url(current, resolve_dns=False)
                        if monotonic() >= deadline:
                            raise TimeoutError("source request deadline exceeded")
                        with client.stream("GET", current, timeout=max(.1, deadline - monotonic())) as response:
                            mime = response.headers.get("content-type", "").lower()
                            if response.is_redirect:
                                if redirect == 5:
                                    raise UnsafeURL("too many redirects")
                                current = str(response.url.join(response.headers.get("location", "")))
                                continue
                            if response.status_code >= 400:
                                if response.status_code in {429, 500, 502, 503, 504}:
                                    raise httpx.HTTPStatusError(f"retryable HTTP {response.status_code}", request=response.request, response=response)
                                return FetchResult(url, current, response.status_code, mime, None, None, f"source access returned {response.status_code}", attempt)
                            length = response.headers.get("content-length", "0")
                            if length.isdigit() and int(length) > self.max_bytes:
                                return FetchResult(url, current, response.status_code, mime, None, None, "source exceeds configured size limit", attempt)
                            chunks, size = [], 0
                            for chunk in response.iter_bytes(chunk_size=min(65536, self.max_bytes + 1)):
                                if monotonic() >= deadline:
                                    raise TimeoutError("source download deadline exceeded")
                                size += len(chunk)
                                if size > self.max_bytes:
                                    return FetchResult(url, current, response.status_code, mime, None, None, "source exceeds configured size limit", attempt)
                                chunks.append(chunk)
                            body = b"".join(chunks)
                            if body.startswith(b"%PDF"):
                                suffix, mime = ".pdf", "application/pdf"
                            elif "html" in mime or body.lstrip().lower().startswith((b"<!doctype html", b"<html")):
                                suffix, mime = ".html", "text/html"
                            elif "xml" in mime:
                                suffix = ".xml"
                            else:
                                return FetchResult(url, current, response.status_code, mime, None, None, "unsupported source content type", attempt)
                            digest = content_hash(body)
                            path = self.data_dir / "raw" / f"{digest}{suffix}"
                            path.parent.mkdir(parents=True, exist_ok=True)
                            if not path.exists():
                                from uuid import uuid4
                                temporary = path.with_name(f"{path.name}.{uuid4()}.tmp")
                                temporary.write_bytes(body)
                                temporary.replace(path)
                            return FetchResult(url, current, response.status_code, mime, digest, str(path), None, attempt,
                                               retrieved_at=datetime.now(UTC).isoformat())
            except UnsafeURL as exc:
                return FetchResult(url, None, None, None, None, None, str(exc), attempt)
            except (httpx.HTTPError, OSError) as exc:
                last_error = str(exc)
                if attempt <= retries and deadline - monotonic() > 1:
                    sleep(min(2 ** (attempt - 1), 2, max(0, deadline - monotonic())))
                else:
                    break
        return FetchResult(url, None, None, None, None, None, last_error or "source fetch failed", attempt)
