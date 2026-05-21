"""Tests that the Session SDK respects weave global settings.

Covers four settings + one bug fix:

- ``WEAVE_DISABLED`` — silences span emission in streaming + batch paths.
- ``WEAVE_REDACT_PII`` — routes content fields through ``redact_pii`` /
  ``redact_pii_string`` so Session SDK redaction matches ``@op``.
- ``WEAVE_CAPTURE_CLIENT_INFO`` / ``WEAVE_CAPTURE_SYSTEM_INFO`` — emits
  ``weave.*`` metadata attrs on every span (matches ``@op`` defaults).
- Reasoning leak fix — ``LLM.reasoning`` is now gated by ``include_content``
  in both streaming (``LLM.end``) and batch (``_attrs_for_span``) paths.
"""

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
    Tool,
    Turn,
    log_session,
    log_turn,
    start_session,
)
from weave.trace.settings import override_settings


def _email_substitutor() -> Callable[[Any], Any]:
    """Recursive ``alice@example.com → <EMAIL>`` substitutor.

    Stand-in for the real ``redact_pii``: walks dicts and lists like
    Presidio does, but does plain string substitution so tests don't
    need the NLP stack installed.
    """

    def _walk(value: Any) -> Any:
        if isinstance(value, str):
            return value.replace("alice@example.com", "<EMAIL>")
        if isinstance(value, dict):
            return {k: _walk(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_walk(x) for x in value]
        return value

    return _walk


def _spans_with_prefix(otel_spans: InMemorySpanExporter, prefix: str) -> list[Any]:
    return [s for s in otel_spans.get_finished_spans() if s.name.startswith(prefix)]


# ---------------------------------------------------------------------------
# disabled — runtime span emission
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


def _exercise_log_turn() -> Any:
    return log_turn(
        session_id="s",
        agent_name="a",
        messages=[Message(role="user", content="hi")],
    )


def _exercise_log_session() -> Any:
    return log_session(
        turns=[Turn(agent_name="a", messages=[Message(role="user", content="hi")])],
        session_id="s",
    )


@pytest.mark.parametrize(
    "exercise",
    [
        pytest.param(_exercise_log_turn, id="log_turn"),
        pytest.param(_exercise_log_session, id="log_session"),
    ],
)
def test_disabled_batch_emits_no_spans(
    exercise: Callable[[], Any], otel_spans: InMemorySpanExporter
):
    with override_settings(disabled=True):
        result = exercise()
    assert result.span_count == 0
    assert otel_spans.get_finished_spans() == ()


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
    """Regression case for the pre-existing leak: reasoning bypassing redaction."""
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
    substitutor = _email_substitutor()
    with override_settings(redact_pii=True):
        with (
            patch("weave.utils.pii_redaction.redact_pii", side_effect=substitutor),
            patch(
                "weave.utils.pii_redaction.redact_pii_string", side_effect=substitutor
            ),
        ):
            exercise()

    spans = _spans_with_prefix(otel_spans, span_prefix)
    assert len(spans) == 1, f"expected 1 {span_prefix} span, got {len(spans)}"
    attrs = dict(spans[0].attributes)
    for key in checked_keys:
        assert "alice@example.com" not in attrs[key], key
        assert "<EMAIL>" in attrs[key], key


# ---------------------------------------------------------------------------
# include_content=False — Presidio skipped, content dropped
# ---------------------------------------------------------------------------


def _ic_off_tool() -> None:
    with start_session(session_id="s", include_content=False) as sess:
        with sess.start_turn() as t:
            with t.tool(name="lookup") as tool:
                tool.arguments = '{"email":"alice@example.com"}'


def _ic_off_llm() -> None:
    with start_session(session_id="s", include_content=False) as sess:
        with sess.start_turn() as t:
            with t.llm(model="gpt-4o") as llm:
                llm.input_messages = [Message(role="user", content="alice@example.com")]
                llm.reasoning = Reasoning(content="think")


def _ic_off_turn() -> None:
    with start_session(session_id="s", include_content=False) as sess:
        with sess.start_turn(user_message="alice@example.com"):
            pass


def _ic_off_log_turn() -> None:
    log_turn(
        session_id="s",
        agent_name="a",
        include_content=False,
        messages=[Message(role="user", content="alice@example.com")],
        spans=[Tool(name="lookup", arguments='{"email":"alice@example.com"}')],
    )


@pytest.mark.parametrize(
    "exercise",
    [
        pytest.param(_ic_off_tool, id="tool"),
        pytest.param(_ic_off_llm, id="llm"),
        pytest.param(_ic_off_turn, id="turn"),
        pytest.param(_ic_off_log_turn, id="log_turn"),
    ],
)
def test_include_content_false_skips_presidio(
    exercise: Callable[[], None],
    otel_spans: InMemorySpanExporter,
):
    """include_content=False drops content at source; Presidio is never called."""
    with override_settings(redact_pii=True):
        with (
            patch("weave.utils.pii_redaction.redact_pii") as mock_redact,
            patch("weave.utils.pii_redaction.redact_pii_string") as mock_redact_str,
        ):
            exercise()
    mock_redact.assert_not_called()
    mock_redact_str.assert_not_called()


def _reasoning_streaming() -> None:
    with start_session(session_id="s", include_content=False) as sess:
        with sess.start_turn() as t:
            with t.llm(model="gpt-4o") as llm:
                llm.reasoning = Reasoning(content="sensitive reasoning")


def _reasoning_batch() -> None:
    log_turn(
        session_id="s",
        agent_name="a",
        include_content=False,
        spans=[LLM(model="gpt-4o", reasoning=Reasoning(content="sensitive"))],
    )


@pytest.mark.parametrize(
    "exercise",
    [
        pytest.param(_reasoning_streaming, id="streaming"),
        pytest.param(_reasoning_batch, id="batch"),
    ],
)
def test_include_content_false_drops_reasoning(
    exercise: Callable[[], None], otel_spans: InMemorySpanExporter
):
    """Regression: LLM.reasoning used to bypass include_content and leak into output.messages."""
    exercise()
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
    """Batch (log_turn) path uses a separate emit path — same invariant."""
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


def test_settings_independent(otel_spans: InMemorySpanExporter):
    """redact_pii=True + capture_*=False produces redacted content without weave.* attrs."""
    substitutor = _email_substitutor()
    with override_settings(
        redact_pii=True, capture_client_info=False, capture_system_info=False
    ):
        with (
            patch("weave.utils.pii_redaction.redact_pii", side_effect=substitutor),
            patch(
                "weave.utils.pii_redaction.redact_pii_string", side_effect=substitutor
            ),
        ):
            with start_session(session_id="s") as sess, sess.start_turn() as t:
                with t.tool(name="lookup") as tool:
                    tool.arguments = "alice@example.com"

    tool_spans = _spans_with_prefix(otel_spans, "execute_tool")
    attrs = dict(tool_spans[0].attributes)
    assert "<EMAIL>" in attrs["gen_ai.tool.call.arguments"]
    assert "weave.client_version" not in attrs


def test_defaults_skip_redaction(otel_spans: InMemorySpanExporter):
    """With defaults (redact_pii=False), redaction primitives are never called."""
    with (
        patch("weave.utils.pii_redaction.redact_pii") as mock_redact,
        patch("weave.utils.pii_redaction.redact_pii_string") as mock_redact_str,
    ):
        with start_session(session_id="s") as sess, sess.start_turn() as t:
            with t.tool(name="x") as tool:
                tool.arguments = "alice@example.com"
    mock_redact.assert_not_called()
    mock_redact_str.assert_not_called()
