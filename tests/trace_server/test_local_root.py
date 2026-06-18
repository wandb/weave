"""Tests for `weave.trace_server.local_root`."""

from __future__ import annotations

import asyncio

from opentelemetry.sdk.trace import TracerProvider

from weave.trace_server.local_root import (
    get_local_root,
    local_root_scope,
)


def _make_span():
    """Create a real recording span via the SDK."""
    return TracerProvider().get_tracer("test").start_span("entry")


def test_get_local_root_none_outside_scope() -> None:
    assert get_local_root() is None


def test_local_root_scope_sets_and_resets() -> None:
    span = _make_span()
    assert get_local_root() is None
    with local_root_scope(span):
        assert get_local_root() is span
    assert get_local_root() is None
    span.end()


def test_local_root_scope_resets_on_exception() -> None:
    span = _make_span()
    try:
        with local_root_scope(span):
            assert get_local_root() is span
            raise ValueError("boom")
    except ValueError:
        pass
    assert get_local_root() is None
    span.end()


def test_local_root_scope_nests() -> None:
    outer = _make_span()
    inner = _make_span()
    with local_root_scope(outer):
        assert get_local_root() is outer
        with local_root_scope(inner):
            assert get_local_root() is inner
        assert get_local_root() is outer
    assert get_local_root() is None
    outer.end()
    inner.end()


def test_local_root_visible_across_await() -> None:
    """Contextvars propagate to awaited coroutines."""
    span = _make_span()

    async def deep_helper() -> object:
        return get_local_root()

    async def runner() -> object:
        with local_root_scope(span):
            return await deep_helper()

    result = asyncio.run(runner())
    assert result is span
    span.end()


def test_get_local_root_returns_none_for_non_recording_span() -> None:
    """Per the contract, non-recording spans are treated as 'no local root'."""
    from opentelemetry import trace as _otel_trace

    invalid_span = _otel_trace.INVALID_SPAN
    with local_root_scope(invalid_span):
        # INVALID_SPAN.is_recording() returns False — helper should hide it.
        assert get_local_root() is None
