"""Tests that the Session SDK respects weave global settings."""

from __future__ import annotations

import platform
import sys
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weave import version
from weave.session.session import (
    LLM,
    Message,
    Reasoning,
    TextPart,
    Tool,
    ToolCallPart,
    Turn,
    log_session,
    log_turn,
    start_session,
)
from weave.trace.settings import override_settings
from weave.trace.weave_init import init_weave_disabled
from weave.utils import pii_redaction


def _make_redact_substitutor(substitutions: dict[str, str]) -> Callable[[Any], Any]:
    """Build a recursive redaction mock that substitutes substrings in strings.

    Walks dicts, lists, and dataclasses (matches the real ``redact_pii``
    shape) and applies each ``old → new`` substitution to every string
    encountered. Used as ``side_effect`` for patching
    ``weave.utils.pii_redaction.redact_pii`` in tests.
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


def _email_substitutor() -> Callable[[Any], Any]:
    """Standard substitutor: alice@example.com → <EMAIL>. Used by most redact tests."""
    return _make_redact_substitutor({"alice@example.com": "<EMAIL>"})


def _spans_with_prefix(otel_spans: InMemorySpanExporter, prefix: str) -> list[Any]:
    return [s for s in otel_spans.get_finished_spans() if s.name.startswith(prefix)]


def _exercise_tool() -> None:
    """Streaming Tool span path with PII-bearing content."""
    with start_session(session_id="s", include_content=False) as sess:
        with sess.start_turn() as t:
            with t.tool(name="lookup") as tool:
                tool.arguments = '{"email":"alice@example.com"}'


def _exercise_llm() -> None:
    """Streaming LLM span path with PII-bearing content."""
    with start_session(session_id="s", include_content=False) as sess:
        with sess.start_turn() as t:
            with t.llm(model="gpt-4o") as llm:
                llm.input_messages = [Message(role="user", content="alice@example.com")]
                llm.reasoning = Reasoning(content="think")


def _exercise_turn() -> None:
    """Streaming Turn span path with PII-bearing user_message."""
    with start_session(session_id="s", include_content=False) as sess:
        with sess.start_turn(user_message="alice@example.com"):
            pass


def _exercise_log_turn() -> None:
    """Batch log_turn path with PII-bearing content."""
    log_turn(
        session_id="s",
        agent_name="a",
        include_content=False,
        messages=[Message(role="user", content="alice@example.com")],
        spans=[Tool(name="lookup", arguments='{"email":"alice@example.com"}')],
    )


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


@pytest.mark.parametrize(
    "batch_call",
    [
        pytest.param(
            lambda: log_turn(
                session_id="sess",
                agent_name="a",
                messages=[Message(role="user", content="hi")],
            ),
            id="log_turn",
        ),
        pytest.param(
            lambda: log_session(
                turns=[
                    Turn(agent_name="a", messages=[Message(role="user", content="hi")])
                ],
                session_id="sess",
            ),
            id="log_session",
        ),
    ],
)
def test_disabled_batch_emits_no_spans(
    batch_call: Callable[[], Any], otel_spans: InMemorySpanExporter
):
    with override_settings(disabled=True):
        result = batch_call()
    assert result.span_count == 0
    assert otel_spans.get_finished_spans() == ()


def test_disabled_init_skips_session_tracing():
    """``init_weave_disabled`` is the path ``weave.init()`` takes under
    ``WEAVE_DISABLED=true`` (short-circuited in ``api.py`` before
    ``init_weave``). It must not invoke ``_setup_session_tracing`` —
    otherwise a global OTel TracerProvider would be installed against
    the disabled stub server.
    """
    with (
        patch("weave.trace.weave_init.init_weave_get_server"),
        patch("weave.trace.weave_init.weave_client.WeaveClient"),
        patch("weave.trace.weave_init._setup_session_tracing") as mock_setup,
    ):
        init_weave_disabled()
    mock_setup.assert_not_called()


# ---------------------------------------------------------------------------
# pii_redaction.py session helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("input_str", "expected_output", "expects_call"),
    [
        pytest.param("", "", False, id="empty_skips_presidio"),
        pytest.param(
            "alice@example.com", "REDACTED", True, id="routes_through_redact_pii"
        ),
    ],
)
def test_redact_string(input_str: str, expected_output: str, expects_call: bool):
    with patch("weave.utils.pii_redaction.redact_pii", return_value="REDACTED") as mock:
        result = pii_redaction.redact_string(input_str)
    assert result == expected_output
    assert mock.called is expects_call


@pytest.mark.parametrize(
    ("fn", "empty"),
    [
        pytest.param(pii_redaction.redact_messages, [], id="messages"),
        pytest.param(
            pii_redaction.redact_system_instructions, [], id="system_instructions"
        ),
    ],
)
def test_redact_collection_helpers_passthrough_none_and_empty(fn, empty):
    """Collection helpers passthrough None → None and empty → empty."""
    assert fn(None) is None
    assert fn(empty) == empty


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

    with patch("weave.utils.pii_redaction.redact_pii", side_effect=fake_redact):
        out = pii_redaction.redact_messages(msgs)

    assert out is not None
    assert len(out) == 2
    assert out[0].content == "EMAIL ME AT ALICE@EXAMPLE.COM"
    assert out[0].role == "user"  # role is a Literal — preserved by validation
    assert out[1].parts[0].content == "OK"
    # ToolCallPart.arguments goes through JSONString coercion
    assert "ALICE" in out[1].parts[1].arguments


def test_redact_system_instructions():
    with patch(
        "weave.utils.pii_redaction.redact_pii",
        side_effect=lambda s: "<REDACTED>" if s else s,
    ):
        out = pii_redaction.redact_system_instructions(["secret instruction"])
    assert out == ["<REDACTED>"]


# ---------------------------------------------------------------------------
# redact_pii — applied across streaming + batch paths
# ---------------------------------------------------------------------------


def _redact_streaming_tool() -> None:
    with start_session(session_id="s") as sess, sess.start_turn() as t:
        with t.tool(name="lookup") as tool:
            tool.arguments = '{"email":"alice@example.com"}'
            tool.result = "found alice@example.com"


def _redact_streaming_llm_messages() -> None:
    with start_session(session_id="s") as sess, sess.start_turn() as t:
        with t.llm(
            model="gpt-4o", system_instructions=["contact alice@example.com"]
        ) as llm:
            llm.input_messages = [Message(role="user", content="alice@example.com")]
            llm.output_messages = [
                Message(role="assistant", content="hi alice@example.com")
            ]


def _redact_streaming_llm_reasoning() -> None:
    """Regression case for the pre-existing leak: reasoning bypassing redact_pii."""
    with start_session(session_id="s") as sess, sess.start_turn() as t:
        with t.llm(model="gpt-4o") as llm:
            llm.reasoning = Reasoning(content="think about alice@example.com")
            llm.output_messages = [Message(role="assistant", content="ok")]


def _redact_streaming_turn() -> None:
    with start_session(session_id="s") as sess:
        with sess.start_turn(user_message="alice@example.com"):
            pass


def _redact_batch_turn_messages() -> None:
    log_turn(
        session_id="s",
        agent_name="a",
        messages=[Message(role="user", content="alice@example.com")],
    )


def _redact_batch_child_llm() -> None:
    log_turn(
        session_id="s",
        agent_name="a",
        spans=[
            LLM(
                model="gpt-4o",
                input_messages=[Message(role="user", content="alice@example.com")],
            ),
        ],
    )


def _redact_batch_child_tool() -> None:
    log_turn(
        session_id="s",
        agent_name="a",
        spans=[Tool(name="lookup", arguments='{"email":"alice@example.com"}')],
    )


@pytest.mark.parametrize(
    ("exercise", "span_prefix", "checked_keys"),
    [
        pytest.param(
            _redact_streaming_tool,
            "execute_tool",
            ("gen_ai.tool.call.arguments", "gen_ai.tool.call.result"),
            id="streaming_tool",
        ),
        pytest.param(
            _redact_streaming_llm_messages,
            "chat",
            (
                "gen_ai.input.messages",
                "gen_ai.output.messages",
                "gen_ai.system_instructions",
            ),
            id="streaming_llm_messages",
        ),
        pytest.param(
            _redact_streaming_llm_reasoning,
            "chat",
            ("gen_ai.output.messages",),
            id="streaming_llm_reasoning",
        ),
        pytest.param(
            _redact_streaming_turn,
            "invoke_agent",
            ("gen_ai.input.messages",),
            id="streaming_turn",
        ),
        pytest.param(
            _redact_batch_turn_messages,
            "invoke_agent",
            ("gen_ai.input.messages",),
            id="batch_turn_messages",
        ),
        pytest.param(
            _redact_batch_child_llm,
            "chat",
            ("gen_ai.input.messages",),
            id="batch_child_llm",
        ),
        pytest.param(
            _redact_batch_child_tool,
            "execute_tool",
            ("gen_ai.tool.call.arguments",),
            id="batch_child_tool",
        ),
    ],
)
def test_redact_pii_applied(
    exercise: Callable[[], None],
    span_prefix: str,
    checked_keys: tuple[str, ...],
    otel_spans: InMemorySpanExporter,
):
    """redact_pii=True applies redaction across streaming + batch paths."""
    with override_settings(redact_pii=True):
        with patch(
            "weave.utils.pii_redaction.redact_pii", side_effect=_email_substitutor()
        ):
            exercise()

    spans = _spans_with_prefix(otel_spans, span_prefix)
    assert len(spans) == 1, f"expected 1 {span_prefix} span, got {len(spans)}"
    attrs = dict(spans[0].attributes)
    for key in checked_keys:
        assert "alice@example.com" not in attrs[key], key
        assert "<EMAIL>" in attrs[key], key


# ---------------------------------------------------------------------------
# include_content=False — cross-path invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exercise_path",
    [
        pytest.param(_exercise_tool, id="tool"),
        pytest.param(_exercise_llm, id="llm"),
        pytest.param(_exercise_turn, id="turn"),
        pytest.param(_exercise_log_turn, id="log_turn"),
    ],
)
def test_skip_presidio_when_include_content_false(
    exercise_path: Callable[[], None],
    otel_spans: InMemorySpanExporter,
):
    """include_content=False drops content at source; Presidio is never called."""
    with override_settings(redact_pii=True):
        with patch("weave.utils.pii_redaction.redact_pii") as mock_redact:
            exercise_path()
    mock_redact.assert_not_called()


def _exercise_streaming_reasoning() -> None:
    with start_session(session_id="s", include_content=False) as sess:
        with sess.start_turn() as t:
            with t.llm(model="gpt-4o") as llm:
                llm.reasoning = Reasoning(content="sensitive reasoning")


def _exercise_batch_reasoning() -> None:
    log_turn(
        session_id="s",
        agent_name="a",
        include_content=False,
        spans=[LLM(model="gpt-4o", reasoning=Reasoning(content="sensitive"))],
    )


@pytest.mark.parametrize(
    "exercise_path",
    [
        pytest.param(_exercise_streaming_reasoning, id="streaming"),
        pytest.param(_exercise_batch_reasoning, id="batch"),
    ],
)
def test_include_content_false_drops_reasoning(
    exercise_path: Callable[[], None],
    otel_spans: InMemorySpanExporter,
):
    """Regression test for the pre-existing leak: LLM.reasoning bypassed include_content."""
    exercise_path()
    chat_spans = _spans_with_prefix(otel_spans, "chat")
    attrs = dict(chat_spans[0].attributes)
    assert "gen_ai.output.messages" not in attrs


# ---------------------------------------------------------------------------
# capture_client_info / capture_system_info
# ---------------------------------------------------------------------------


# Sentinel for presence-only checks (value exists, content not asserted).
_PRESENT = object()


@pytest.mark.parametrize(
    ("client_info", "system_info", "expected_present", "expected_absent"),
    [
        pytest.param(
            True,
            False,
            {
                "weave.client_version": version.VERSION,
                "weave.source": "python-sdk",
                "weave.sys_version": sys.version,
            },
            ("weave.os_name",),
            id="client_only",
        ),
        pytest.param(
            False,
            True,
            {"weave.os_name": platform.system(), "weave.os_release": _PRESENT},
            ("weave.client_version",),
            id="system_only",
        ),
        pytest.param(
            False,
            False,
            {},
            ("weave.client_version", "weave.os_name"),
            id="both_off",
        ),
    ],
)
def test_capture_info_settings(
    client_info: bool,
    system_info: bool,
    expected_present: dict[str, Any],
    expected_absent: tuple[str, ...],
    otel_spans: InMemorySpanExporter,
):
    with override_settings(
        capture_client_info=client_info, capture_system_info=system_info
    ):
        with start_session(session_id="s") as sess:
            with sess.start_turn() as t:
                with t.tool(name="x"):
                    pass

    spans = otel_spans.get_finished_spans()
    assert len(spans) >= 2  # turn + tool
    for span in spans:
        attrs = dict(span.attributes)
        for key, expected in expected_present.items():
            if expected is _PRESENT:
                assert key in attrs, f"{key} missing on span {span.name}"
            else:
                assert attrs.get(key) == expected, f"{key} mismatch on {span.name}"
        for key in expected_absent:
            assert key not in attrs, f"{key} unexpectedly present on {span.name}"


def test_capture_info_on_batch_path(otel_spans: InMemorySpanExporter):
    """Same invariant on the batch (log_turn) path, which uses a separate emit path."""
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


# ---------------------------------------------------------------------------
# Independence + defaults
# ---------------------------------------------------------------------------


def test_settings_independence(otel_spans: InMemorySpanExporter):
    """redact_pii=True, capture_client_info=False produces redacted content
    without weave.client_version. Confirms settings don't bleed into each other.
    """
    with override_settings(
        redact_pii=True, capture_client_info=False, capture_system_info=False
    ):
        with patch(
            "weave.utils.pii_redaction.redact_pii",
            side_effect=_email_substitutor(),
        ):
            with start_session(session_id="s") as sess, sess.start_turn() as t:
                with t.tool(name="lookup") as tool:
                    tool.arguments = "alice@example.com"

    tool_spans = _spans_with_prefix(otel_spans, "execute_tool")
    attrs = dict(tool_spans[0].attributes)
    assert "<EMAIL>" in attrs["gen_ai.tool.call.arguments"]
    assert "weave.client_version" not in attrs


def test_all_settings_default_off_redaction(otel_spans: InMemorySpanExporter):
    """With defaults, redaction does not run. Sanity check."""
    with patch("weave.utils.pii_redaction.redact_pii") as mock_redact:
        with start_session(session_id="s") as sess, sess.start_turn() as t:
            with t.tool(name="x") as tool:
                tool.arguments = "alice@example.com"
    mock_redact.assert_not_called()
