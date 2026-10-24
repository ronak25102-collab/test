"""Pin each connection to a validated public IP while preserving Host and TLS SNI."""
import socket
import ssl

import httpcore
import httpx
import truststore

from .url_policy import UnsafeURL, _is_private


class PublicNetworkBackend(httpcore.SyncBackend):
    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        from signal_research.precomputed.guard import require_network_allowed
        require_network_allowed()
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
        if not addresses or any(_is_private(address) for address in addresses):
            raise UnsafeURL("connection DNS resolved to a private destination")
        # The HTTP origin remains the original host. Only the TCP destination
        # changes, so certificate validation and SNI still use the original name.
        return super().connect_tcp(addresses[0], port, timeout, local_address, socket_options)


class PublicTransport(httpx.HTTPTransport):
    def __init__(self):
        super().__init__(trust_env=False, retries=0)
        self._pool.close()
        self._pool = httpcore.ConnectionPool(ssl_context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT), network_backend=PublicNetworkBackend(), retries=0)
