"""Tests that the Session SDK respects weave global settings.

See spec: rgao/superpowers/specs/2026-05-13-session-sdk-respects-global-settings-design.md
"""

from __future__ import annotations

import platform
import sys
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weave import version
from weave.session import _redaction
from weave.session.session import (
    LLM,
    Message,
    Reasoning,
    TextPart,
    Tool,
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


def _make_redact_substitutor(substitutions: dict[str, str]) -> Callable[[Any], Any]:
    """Build a recursive redaction mock that substitutes substrings in strings.

    Walks dicts, lists, and dataclasses (matches the real ``redact_pii``
    shape) and applies each ``old → new`` substitution to every string
    encountered. Used as ``side_effect`` for patching
    ``weave.session._redaction.redact_pii`` in tests.
    """

    def _walk(value: Any) -> Any:
        if isinstance(value, str):
            for old, new in substitutions.items():
                value = value.replace(old, new)
            return value
        if isinstance(value, dict):
            return {k: _walk(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_walk(x) for x in value]
        return value

    return _walk


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


# ---------------------------------------------------------------------------
# redact_pii — Tool
# ---------------------------------------------------------------------------


def test_tool_redacts_arguments_and_result(otel_spans: InMemorySpanExporter):
    """With redact_pii=True, Tool.arguments and Tool.result are redacted on emit."""
    with override_settings(redact_pii=True):
        with patch(
            "weave.session._redaction.redact_pii",
            side_effect=lambda s: s.replace("alice@example.com", "<EMAIL>"),
        ):
            with start_session(session_id="s") as sess, sess.start_turn() as t:
                with t.tool(name="lookup") as tool:
                    tool.arguments = '{"email":"alice@example.com"}'
                    tool.result = "found alice@example.com"

    tool_spans = [
        s for s in otel_spans.get_finished_spans() if s.name.startswith("execute_tool")
    ]
    assert len(tool_spans) == 1
    attrs = tool_spans[0].attributes
    assert "<EMAIL>" in attrs["gen_ai.tool.call.arguments"]
    assert "alice@example.com" not in attrs["gen_ai.tool.call.arguments"]
    assert "<EMAIL>" in attrs["gen_ai.tool.call.result"]


def test_tool_no_redaction_when_setting_off(otel_spans: InMemorySpanExporter):
    """Default: redact_pii=False → content passes through unchanged."""
    with start_session(session_id="s") as sess, sess.start_turn() as t:
        with t.tool(name="lookup") as tool:
            tool.arguments = '{"email":"alice@example.com"}'

    tool_spans = [
        s for s in otel_spans.get_finished_spans() if s.name.startswith("execute_tool")
    ]
    assert "alice@example.com" in tool_spans[0].attributes["gen_ai.tool.call.arguments"]


def test_tool_skip_presidio_when_include_content_false(
    otel_spans: InMemorySpanExporter,
):
    """include_content=False drops content at source; Presidio is never called."""
    with override_settings(redact_pii=True):
        with patch("weave.session._redaction.redact_pii") as mock_redact:
            with start_session(session_id="s", include_content=False) as sess:
                with sess.start_turn() as t:
                    with t.tool(name="lookup") as tool:
                        tool.arguments = '{"email":"alice@example.com"}'

    mock_redact.assert_not_called()
    tool_spans = [
        s for s in otel_spans.get_finished_spans() if s.name.startswith("execute_tool")
    ]
    assert "gen_ai.tool.call.arguments" not in tool_spans[0].attributes


# ---------------------------------------------------------------------------
# redact_pii — LLM
# ---------------------------------------------------------------------------


def _get_llm_attrs(otel_spans: InMemorySpanExporter) -> dict[str, Any]:
    llm_spans = [
        s for s in otel_spans.get_finished_spans() if s.name.startswith("chat")
    ]
    assert len(llm_spans) == 1, f"expected 1 chat span, got {len(llm_spans)}"
    return dict(llm_spans[0].attributes)


def test_llm_redacts_input_and_output_messages(otel_spans: InMemorySpanExporter):
    with override_settings(redact_pii=True):
        with patch(
            "weave.session._redaction.redact_pii",
            side_effect=_make_redact_substitutor({"alice@example.com": "<EMAIL>"}),
        ):
            with start_session(session_id="s") as sess, sess.start_turn() as t:
                with t.llm(model="gpt-4o") as llm:
                    llm.input_messages = [
                        Message(role="user", content="alice@example.com")
                    ]
                    llm.output_messages = [
                        Message(role="assistant", content="hi alice@example.com")
                    ]

    attrs = _get_llm_attrs(otel_spans)
    assert "alice@example.com" not in attrs["gen_ai.input.messages"]
    assert "<EMAIL>" in attrs["gen_ai.input.messages"]
    assert "alice@example.com" not in attrs["gen_ai.output.messages"]


def test_llm_redacts_system_instructions(otel_spans: InMemorySpanExporter):
    with override_settings(redact_pii=True):
        with patch(
            "weave.session._redaction.redact_pii",
            side_effect=lambda s: (
                s.replace("alice@example.com", "<EMAIL>") if isinstance(s, str) else s
            ),
        ):
            with start_session(session_id="s") as sess, sess.start_turn() as t:
                with t.llm(
                    model="gpt-4o",
                    system_instructions=["contact alice@example.com"],
                ):
                    pass

    attrs = _get_llm_attrs(otel_spans)
    assert "alice@example.com" not in attrs["gen_ai.system_instructions"]
    assert "<EMAIL>" in attrs["gen_ai.system_instructions"]


def test_llm_redacts_reasoning(otel_spans: InMemorySpanExporter):
    with override_settings(redact_pii=True):
        with patch(
            "weave.session._redaction.redact_pii",
            side_effect=lambda s: (
                s.replace("alice@example.com", "<EMAIL>") if isinstance(s, str) else s
            ),
        ):
            with start_session(session_id="s") as sess, sess.start_turn() as t:
                with t.llm(model="gpt-4o") as llm:
                    llm.reasoning = Reasoning(content="think about alice@example.com")
                    llm.output_messages = [Message(role="assistant", content="ok")]

    attrs = _get_llm_attrs(otel_spans)
    assert "alice@example.com" not in attrs["gen_ai.output.messages"]


def test_llm_include_content_false_drops_reasoning(otel_spans: InMemorySpanExporter):
    """Regression test for pre-existing leak: reasoning bypassed include_content."""
    with start_session(session_id="s", include_content=False) as sess:
        with sess.start_turn() as t:
            with t.llm(model="gpt-4o") as llm:
                llm.reasoning = Reasoning(content="sensitive reasoning")

    attrs = _get_llm_attrs(otel_spans)
    # gen_ai.output.messages should be absent (no messages, no reasoning carries through)
    assert "gen_ai.output.messages" not in attrs


def test_llm_skip_presidio_when_include_content_false(otel_spans: InMemorySpanExporter):
    with override_settings(redact_pii=True):
        with patch("weave.session._redaction.redact_pii") as mock_redact:
            with start_session(session_id="s", include_content=False) as sess:
                with sess.start_turn() as t:
                    with t.llm(model="gpt-4o") as llm:
                        llm.input_messages = [
                            Message(role="user", content="alice@example.com")
                        ]
                        llm.reasoning = Reasoning(content="think")
    mock_redact.assert_not_called()


# ---------------------------------------------------------------------------
# redact_pii — Turn
# ---------------------------------------------------------------------------


def test_turn_redacts_messages(otel_spans: InMemorySpanExporter):
    with override_settings(redact_pii=True):
        with patch(
            "weave.session._redaction.redact_pii",
            side_effect=_make_redact_substitutor({"alice@example.com": "<EMAIL>"}),
        ):
            with start_session(session_id="s") as sess:
                with sess.start_turn(user_message="alice@example.com"):
                    pass

    turn_spans = [
        s for s in otel_spans.get_finished_spans() if s.name.startswith("invoke_agent")
    ]
    assert len(turn_spans) == 1
    attrs = dict(turn_spans[0].attributes)
    assert "alice@example.com" not in attrs.get("gen_ai.input.messages", "")
    assert "<EMAIL>" in attrs["gen_ai.input.messages"]


def test_turn_skip_presidio_when_include_content_false(
    otel_spans: InMemorySpanExporter,
):
    with override_settings(redact_pii=True):
        with patch("weave.session._redaction.redact_pii") as mock_redact:
            with start_session(session_id="s", include_content=False) as sess:
                with sess.start_turn(user_message="alice@example.com"):
                    pass
    mock_redact.assert_not_called()


# ---------------------------------------------------------------------------
# redact_pii — batch (log_turn / log_session / _attrs_for_span)
# ---------------------------------------------------------------------------


def test_log_turn_redacts_turn_messages(otel_spans: InMemorySpanExporter):
    with override_settings(redact_pii=True):
        with patch(
            "weave.session._redaction.redact_pii",
            side_effect=_make_redact_substitutor({"alice@example.com": "<EMAIL>"}),
        ):
            log_turn(
                session_id="s",
                agent_name="a",
                messages=[Message(role="user", content="alice@example.com")],
            )

    turn_spans = [
        s for s in otel_spans.get_finished_spans() if s.name.startswith("invoke_agent")
    ]
    assert len(turn_spans) == 1
    assert "alice@example.com" not in turn_spans[0].attributes["gen_ai.input.messages"]
    assert "<EMAIL>" in turn_spans[0].attributes["gen_ai.input.messages"]


def test_log_turn_redacts_child_llm(otel_spans: InMemorySpanExporter):
    with override_settings(redact_pii=True):
        with patch(
            "weave.session._redaction.redact_pii",
            side_effect=_make_redact_substitutor({"alice@example.com": "<EMAIL>"}),
        ):
            log_turn(
                session_id="s",
                agent_name="a",
                spans=[
                    LLM(
                        model="gpt-4o",
                        input_messages=[
                            Message(role="user", content="alice@example.com")
                        ],
                    ),
                ],
            )

    chat_spans = [
        s for s in otel_spans.get_finished_spans() if s.name.startswith("chat")
    ]
    assert len(chat_spans) == 1
    assert "alice@example.com" not in chat_spans[0].attributes["gen_ai.input.messages"]


def test_log_turn_redacts_child_tool(otel_spans: InMemorySpanExporter):
    with override_settings(redact_pii=True):
        with patch(
            "weave.session._redaction.redact_pii",
            side_effect=_make_redact_substitutor({"alice@example.com": "<EMAIL>"}),
        ):
            log_turn(
                session_id="s",
                agent_name="a",
                spans=[
                    Tool(name="lookup", arguments='{"email":"alice@example.com"}'),
                ],
            )

    tool_spans = [
        s for s in otel_spans.get_finished_spans() if s.name.startswith("execute_tool")
    ]
    assert "<EMAIL>" in tool_spans[0].attributes["gen_ai.tool.call.arguments"]


def test_log_turn_include_content_false_drops_reasoning(
    otel_spans: InMemorySpanExporter,
):
    """Regression test: batch path reasoning gating fix."""
    log_turn(
        session_id="s",
        agent_name="a",
        include_content=False,
        spans=[
            LLM(model="gpt-4o", reasoning=Reasoning(content="sensitive")),
        ],
    )
    chat_spans = [
        s for s in otel_spans.get_finished_spans() if s.name.startswith("chat")
    ]
    attrs = dict(chat_spans[0].attributes)
    assert "gen_ai.output.messages" not in attrs


def test_log_turn_skip_presidio_when_include_content_false(
    otel_spans: InMemorySpanExporter,
):
    with override_settings(redact_pii=True):
        with patch("weave.session._redaction.redact_pii") as mock_redact:
            log_turn(
                session_id="s",
                agent_name="a",
                include_content=False,
                messages=[Message(role="user", content="alice@example.com")],
                spans=[Tool(name="lookup", arguments='{"email":"alice@example.com"}')],
            )
    mock_redact.assert_not_called()


# ---------------------------------------------------------------------------
# capture_client_info / capture_system_info
# ---------------------------------------------------------------------------


def test_capture_client_info_on(otel_spans: InMemorySpanExporter):
    with override_settings(capture_client_info=True, capture_system_info=False):
        with start_session(session_id="s") as sess:
            with sess.start_turn() as t:
                with t.tool(name="x"):
                    pass

    spans = otel_spans.get_finished_spans()
    assert len(spans) >= 2  # turn + tool
    for span in spans:
        attrs = dict(span.attributes)
        assert attrs.get("weave.client_version") == version.VERSION
        assert attrs.get("weave.source") == "python-sdk"
        assert attrs.get("weave.sys_version") == sys.version
        assert "weave.os_name" not in attrs


def test_capture_system_info_on(otel_spans: InMemorySpanExporter):
    with override_settings(capture_system_info=True, capture_client_info=False):
        with start_session(session_id="s") as sess:
            with sess.start_turn():
                pass

    turn_spans = [
        s for s in otel_spans.get_finished_spans() if s.name.startswith("invoke_agent")
    ]
    attrs = dict(turn_spans[0].attributes)
    assert attrs["weave.os_name"] == platform.system()
    assert "weave.os_release" in attrs
    assert "weave.client_version" not in attrs


def test_capture_info_on_batch_path(otel_spans: InMemorySpanExporter):
    with override_settings(capture_client_info=True):
        log_turn(
            session_id="s",
            agent_name="a",
            spans=[LLM(model="gpt-4o")],
        )

    spans = otel_spans.get_finished_spans()
    assert len(spans) == 2  # turn + child llm
    for s in spans:
        assert s.attributes.get("weave.client_version") == version.VERSION


def test_capture_info_off(otel_spans: InMemorySpanExporter):
    """When both settings are explicitly off, weave.* attrs are absent."""
    with override_settings(capture_client_info=False, capture_system_info=False):
        with start_session(session_id="s") as sess:
            with sess.start_turn():
                pass

    turn_spans = [
        s for s in otel_spans.get_finished_spans() if s.name.startswith("invoke_agent")
    ]
    attrs = dict(turn_spans[0].attributes)
    assert "weave.client_version" not in attrs
    assert "weave.os_name" not in attrs
