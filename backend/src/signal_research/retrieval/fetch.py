from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import sleep

import httpx

from .deduplicate import content_hash
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


class PublicFetcher:
    def __init__(self, data_dir: Path, timeout: float = 25, max_bytes: int = 25_000_000):
        self.data_dir = data_dir
        self.timeout = timeout
        self.max_bytes = max_bytes

    def fetch(self, url: str, retries: int = 2) -> FetchResult:
        try:
            validate_public_url(url)
        except UnsafeURL as exc:
            return FetchResult(url, None, None, None, None, None, str(exc))
        last_error = None
        for attempt in range(1, retries + 2):
            try:
                with httpx.Client(timeout=self.timeout, follow_redirects=False, headers={"User-Agent": "SignalResearch/0.1 public-research"}) as client:
                    response = client.get(url)
                    if response.is_redirect:
                        target = str(response.headers.get("location", ""))
                        validate_public_url(str(httpx.URL(url).join(target)))
                        response = client.get(str(httpx.URL(url).join(target)))
                    if response.status_code in {401, 403, 404, 407, 451}:
                        return FetchResult(url, str(response.url), response.status_code, response.headers.get("content-type"), None, None, f"source access returned {response.status_code}", attempt)
                    if response.status_code == 429 or response.status_code >= 500:
                        last_error = f"retryable HTTP {response.status_code}"
                        if attempt <= retries:
                            sleep(min(2 ** (attempt - 1), 4))
                            continue
                    if response.status_code >= 400:
                        return FetchResult(url, str(response.url), response.status_code, response.headers.get("content-type"), None, None, f"source access returned {response.status_code}", attempt)
                    body = response.content
                    if len(body) > self.max_bytes:
                        return FetchResult(url, str(response.url), response.status_code, response.headers.get("content-type"), None, None, "source exceeds configured size limit", attempt)
                    digest = content_hash(body)
                    suffix = ".pdf" if "pdf" in response.headers.get("content-type", "").lower() else ".html"
                    path = self.data_dir / "raw" / f"{digest}{suffix}"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if not path.exists():
                        temporary = path.with_suffix(path.suffix + ".tmp")
                        temporary.write_bytes(body)
                        temporary.replace(path)
                    return FetchResult(url, str(response.url), response.status_code, response.headers.get("content-type"), digest, str(path), None, attempt)
            except (httpx.HTTPError, OSError, UnsafeURL) as exc:
                last_error = str(exc)
                if attempt <= retries:
                    sleep(min(2 ** (attempt - 1), 4))
        return FetchResult(url, None, None, None, None, None, last_error or "source fetch failed", retries + 1)
