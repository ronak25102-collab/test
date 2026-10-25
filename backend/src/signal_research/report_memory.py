"""One memory-heavy report operation at a time, shared by HTTP and the worker."""
import ctypes
import gc
import re
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Semaphore

import anyio

_slot = Semaphore(1)
_held = ContextVar("report_memory_held", default=False)
try:
    _malloc_trim = ctypes.CDLL(None).malloc_trim
    _malloc_trim.argtypes = [ctypes.c_size_t]
    _malloc_trim.restype = ctypes.c_int
except (AttributeError, TypeError, OSError):  # Windows and allocators other than glibc.
    _malloc_trim = None


def release_unused_memory():
    # Large report graphs can leave cyclic garbage and glibc arenas resident
    # after their last reference is gone. Return those free pages to the host.
    gc.collect()
    if _malloc_trim is not None:
        _malloc_trim(0)


@contextmanager
def report_memory():
    if _held.get():
        yield
        return
    with _slot:
        token = _held.set(True)
        try:
            yield
        finally:
            _held.reset(token)
            release_unused_memory()


class ReportMemoryMiddleware:
    """Hold admission through response delivery, without blocking the event loop.

    Status, cancellation, authentication and health requests remain responsive.
    Context propagation to sync endpoints makes nested fixture checks reentrant.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        heavy = (scope["type"] == "http" and scope.get("method") != "OPTIONS" and (
            (path == "/api/v1/runs" and scope.get("method") == "POST")
            or re.fullmatch(r"/api/v1/runs/[^/]+/report", path)
            or re.match(r"/api/v1/runs/[^/]+/exports/", path)
            or path.startswith(("/api/v1/claims/", "/api/v1/documents/", "/api/v1/calculations/"))))
        if not heavy:
            return await self.app(scope, receive, send)
        # Waiting must not occupy AnyIO thread-pool slots: otherwise many
        # waiting requests can starve the admitted sync endpoint of a thread.
        while not _slot.acquire(blocking=False):
            await anyio.sleep(.025)
        token = _held.set(True)
        try:
            await self.app(scope, receive, send)
        finally:
            _held.reset(token)
            try:
                release_unused_memory()
            finally:
                _slot.release()
