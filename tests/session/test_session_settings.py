"""Tests that the Session SDK respects weave global settings.

See spec: rgao/superpowers/specs/2026-05-13-session-sdk-respects-global-settings-design.md
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weave.session import _redaction
from weave.session.session import (
    Message,
    TextPart,
    ToolCallPart,
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


# ---------------------------------------------------------------------------
# _redaction.py helpers
# ---------------------------------------------------------------------------


def test_redact_string_empty_skips_presidio():
    with patch("weave.session._redaction.redact_pii") as mock:
        assert _redaction.redact_string("") == ""
    mock.assert_not_called()


def test_redact_string_routes_through_redact_pii():
    with patch("weave.session._redaction.redact_pii", return_value="REDACTED") as mock:
        result = _redaction.redact_string("alice@example.com")
    assert result == "REDACTED"
    mock.assert_called_once_with("alice@example.com")


def test_redact_messages_none_passthrough():
    assert _redaction.redact_messages(None) is None
    assert _redaction.redact_messages([]) == []


def test_redact_messages_dump_redact_revalidate():
    """The dump → redact → revalidate round-trip should preserve typed parts."""
    msgs = [
        Message(role="user", content="email me at alice@example.com"),
        Message(
            role="assistant",
            parts=[
                TextPart(content="ok"),
                ToolCallPart(id="c1", name="search", arguments='{"q":"alice"}'),
            ],
        ),
    ]

    def fake_redact(data: Any) -> Any:
        """Echo input but uppercase string values for assertion ease."""
        if isinstance(data, str):
            return data.upper()
        if isinstance(data, dict):
            return {k: fake_redact(v) for k, v in data.items()}
        if isinstance(data, list):
            return [fake_redact(x) for x in data]
        return data

    with patch("weave.session._redaction.redact_pii", side_effect=fake_redact):
        out = _redaction.redact_messages(msgs)

    assert out is not None
    assert len(out) == 2
    assert out[0].content == "EMAIL ME AT ALICE@EXAMPLE.COM"
    assert out[0].role == "user"  # role is a Literal — preserved by validation
    assert out[1].parts[0].content == "OK"
    # ToolCallPart.arguments goes through JSONString coercion
    assert "ALICE" in out[1].parts[1].arguments


def test_redact_system_instructions():
    with patch(
        "weave.session._redaction.redact_pii",
        side_effect=lambda s: "<REDACTED>" if s else s,
    ):
        out = _redaction.redact_system_instructions(["secret instruction"])
    assert out == ["<REDACTED>"]


def test_redact_system_instructions_none_passthrough():
    assert _redaction.redact_system_instructions(None) is None
    assert _redaction.redact_system_instructions([]) == []
