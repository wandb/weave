"""Shared fixtures for Conversation SDK tests."""

from __future__ import annotations

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weave.conversation.conversation import (
    _current_container,
    _current_conversation,
    _current_llm,
    _current_turn,
    get_current_conversation,
    get_current_llm,
    get_current_subagent,
    get_current_turn,
)


@pytest.fixture(autouse=True)
def _reset_contextvars():
    """Reset contextvar state after each test to prevent leakage."""
    yield
    if (llm := get_current_llm()) is not None:
        llm.end()
    if (subagent := get_current_subagent()) is not None:
        subagent.end()
    if (turn := get_current_turn()) is not None:
        turn.end()
    if (conversation := get_current_conversation()) is not None:
        conversation.end()
    # Hard-reset the ambient contextvars regardless of the end() calls above.
    # end() on an already-ended span no-ops and skips its own contextvar reset,
    # so an imperative start_turn()/start_*() with no matching end() can strand a
    # stale value that leaks into the next test. This makes teardown
    # order-independent (test-only).
    _current_llm.set(None)
    _current_container.set(None)
    _current_turn.set(None)
    _current_conversation.set(None)


@pytest.fixture
def otel_spans(monkeypatch: pytest.MonkeyPatch):
    """Provide an in-memory span exporter for capturing OTel spans.

    Overrides the global OTel tracer provider for the duration of the test.
    Uses ``monkeypatch.setattr`` on the private ``_TRACER_PROVIDER`` symbol
    rather than ``set_tracer_provider`` to avoid the "set once" warning
    and to guarantee restoration of the prior value.
    """
    exporter = InMemorySpanExporter()
    provider = SDKTracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER", provider)
    yield exporter
    provider.shutdown()
