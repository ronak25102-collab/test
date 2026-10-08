from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeURL(ValueError):
    pass


def _is_private(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
        return address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_unspecified or address.is_multicast
    except ValueError:
        return False


def validate_public_url(url: str, resolve_dns: bool = True) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeURL("only HTTP and HTTPS sources are allowed")
    if parsed.username or parsed.password:
        raise UnsafeURL("embedded credentials are not allowed")
    if not parsed.hostname:
        raise UnsafeURL("source URL has no hostname")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "metadata.google.internal"} or _is_private(host):
        raise UnsafeURL("private or metadata destinations are blocked")
    if resolve_dns:
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
        except OSError as exc:
            raise UnsafeURL(f"DNS resolution failed: {exc}") from exc
        if any(_is_private(address) for address in addresses):
            raise UnsafeURL("hostname resolves to a private destination")
    return parsed.geturl()
