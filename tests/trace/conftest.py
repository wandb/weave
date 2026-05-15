"""Shared fixtures for trace tests."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any

import pytest

from tests.trace.test_utils import FailingSaveType, failing_load, failing_save
from weave.trace.serialization import serializer
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


@pytest.fixture
def failing_serializer():
    """Register a serializer that always fails, and clean up after the test."""
    serializer.register_serializer(FailingSaveType, failing_save, failing_load)
    yield FailingSaveType
    serializer.SERIALIZERS[:] = [
        s for s in serializer.SERIALIZERS if s.target_class is not FailingSaveType
    ]


class BlockingTraceServer(tsi.TraceServerInterface):
    """Server proxy that holds a lock; while paused, all proxied calls block."""

    def __init__(self, inner: tsi.TraceServerInterface):
        self._inner = inner
        self._lock = threading.Lock()

    def pause(self) -> None:
        self._lock.acquire()

    def resume(self) -> None:
        self._lock.release()

    def __getattribute__(self, item: str) -> Any:
        if item in {"_inner", "_lock", "pause", "resume"}:
            return super().__getattribute__(item)
        inner = super().__getattribute__("_inner")
        if item in {"attribute_access_log", "remote_request_bytes_limit"}:
            return getattr(inner, item)

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with self._lock:
                return getattr(inner, item)(*args, **kwargs)

        return wrapper


@contextmanager
def paused(client: WeaveClient):
    """Pause the client's server proxy, yield, then resume and flush."""
    original = client.server
    client.set_autoflush(False)
    blocker = BlockingTraceServer(original)
    client.server = blocker
    blocker.pause()
    try:
        yield client
    finally:
        blocker.resume()
        client.server = original
        client._flush()
        client.set_autoflush(True)
