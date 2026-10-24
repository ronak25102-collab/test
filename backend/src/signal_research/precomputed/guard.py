"""Explicit provider boundary for offline playback; build-time retrieval is allowed."""
from contextlib import contextmanager
from contextvars import ContextVar

_offline = ContextVar("precomputed_offline", default=False)


class PrecomputedNetworkForbidden(RuntimeError):
    code = "PRECOMPUTED_NETWORK_FORBIDDEN"


def require_network_allowed():
    if _offline.get():
        raise PrecomputedNetworkForbidden("Provider and fetch calls are forbidden during precomputed playback")


@contextmanager
def offline_playback():
    token = _offline.set(True)
    try:
        yield
    finally:
        _offline.reset(token)
