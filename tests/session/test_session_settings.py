"""Tests that the Session SDK respects weave global settings.

See spec: rgao/superpowers/specs/2026-05-13-session-sdk-respects-global-settings-design.md
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weave.session.session import (
    Message,
    Turn,
    get_current_llm,
    get_current_session,
    get_current_turn,
    log_session,
    log_turn,
    start_session,
)
from weave.trace.settings import override_settings
from weave.trace.weave_init import _setup_session_tracing


@pytest.fixture(autouse=True)
def _reset_contextvars():
    yield
    if (llm := get_current_llm()) is not None:
        llm.end()
    if (turn := get_current_turn()) is not None:
        turn.end()
    if (session := get_current_session()) is not None:
        session.end()


@pytest.fixture
def otel_spans(monkeypatch: pytest.MonkeyPatch):
    """In-memory span exporter. Mirrors test_session_otel.py pattern."""
    exporter = InMemorySpanExporter()
    provider = SDKTracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER", provider)
    yield exporter
    provider.shutdown()


# ---------------------------------------------------------------------------
# disabled
# ---------------------------------------------------------------------------


def test_disabled_streaming_emits_no_spans(otel_spans: InMemorySpanExporter):
    with override_settings(disabled=True):
        with start_session(agent_name="a", session_id="s") as s:
            with s.start_turn() as t:
                with t.llm(model="gpt-4o"):
                    pass
                with t.tool(name="search"):
                    pass
    assert otel_spans.get_finished_spans() == ()


def test_disabled_batch_log_turn_emits_no_spans(otel_spans: InMemorySpanExporter):
    with override_settings(disabled=True):
        result = log_turn(
            session_id="sess",
            agent_name="a",
            messages=[Message(role="user", content="hi")],
        )
    assert result.span_count == 0
    assert otel_spans.get_finished_spans() == ()


def test_disabled_batch_log_session_emits_no_spans(otel_spans: InMemorySpanExporter):
    turn = Turn(agent_name="a", messages=[Message(role="user", content="hi")])
    with override_settings(disabled=True):
        result = log_session(turns=[turn], session_id="sess")
    assert result.span_count == 0
    assert otel_spans.get_finished_spans() == ()


def test_disabled_at_init_skips_tracer_provider(monkeypatch: pytest.MonkeyPatch):
    """_setup_session_tracing should no-op when disabled at init time.

    Sets WF_TRACE_SERVER_URL so the function would proceed past its other
    early-return path (the trace_server_url check) and actually reach the
    TracerProvider install if the disabled short-circuit weren't there.
    """
    monkeypatch.setenv("WF_TRACE_SERVER_URL", "https://trace.wandb.ai")

    with override_settings(disabled=True):
        with patch("opentelemetry.trace.set_tracer_provider") as mock_set:
            _setup_session_tracing("entity", "project", api_key="dummy")
    mock_set.assert_not_called()
