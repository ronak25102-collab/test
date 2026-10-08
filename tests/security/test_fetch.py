import socket

import httpcore
import httpx
import pytest
from signal_research.retrieval import fetch
from signal_research.retrieval.transport import PublicNetworkBackend
from signal_research.retrieval.url_policy import UnsafeURL


def test_redirect_chain_cannot_reach_private_url(tmp_path, monkeypatch):
    visited = []
    def handler(request):
        visited.append(str(request.url))
        destination = "/next" if len(visited) == 1 else "http://127.0.0.1/private"
        return httpx.Response(302, headers={"location": destination})
    monkeypatch.setattr(fetch, "PublicTransport", lambda: httpx.MockTransport(handler))
    result = fetch.PublicFetcher(tmp_path).fetch("https://public.example/start")
    assert "private" in result.error and len(visited) == 2
    assert not result.local_path


def test_download_stops_at_decompressed_size_cap(tmp_path, monkeypatch):
    read = []
    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(10):
                read.append(1)
                yield b"x" * 100
    monkeypatch.setattr(fetch, "PublicTransport", lambda: httpx.MockTransport(lambda request: httpx.Response(200, headers={"content-type": "text/html"}, stream=Stream())))
    result = fetch.PublicFetcher(tmp_path, max_bytes=200).fetch("https://public.example/report")
    assert result.error == "source exceeds configured size limit"
    assert len(read) < 10 and not result.local_path


def test_connection_is_pinned_to_validated_public_address(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 443))])
    connected = []
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", lambda self, host, *a: connected.append(host))
    PublicNetworkBackend().connect_tcp("public.example", 443, timeout=1)
    assert connected == ["93.184.216.34"]


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.2", "169.254.169.254", "100.64.0.1", "::1"])
def test_connection_rejects_private_and_non_global_dns(monkeypatch, address):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (address, 443))])
    with pytest.raises(UnsafeURL):
        PublicNetworkBackend().connect_tcp("rebinding.example", 443)
