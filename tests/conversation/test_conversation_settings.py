"""Tests that the Conversation SDK respects weave global settings.

Covers four settings + one bug fix:

- ``WEAVE_DISABLED`` — silences span emission in streaming + batch paths.
- ``WEAVE_REDACT_PII`` — routes content fields through ``redact_pii`` /
  ``redact_pii_string`` so Conversation SDK redaction matches ``@op``.
- ``WEAVE_CAPTURE_CLIENT_INFO`` / ``WEAVE_CAPTURE_SYSTEM_INFO`` — emits
  ``weave.*`` metadata attrs on every span (matches ``@op`` defaults).
- Reasoning leak fix — ``LLM.reasoning`` is now gated by ``include_content``
  in both streaming (``LLM.end``) and batch (``_attrs_for_span``) paths.

Mocking strategy: tests that need redaction patch ``_get_engines`` with
stub Presidio engines (see ``fake_presidio`` fixture). The real
``redact_pii`` / ``redact_pii_string`` code paths run — only the external
NLP dependency is stubbed. Tests that need to assert "no redaction
happens" patch ``_get_engines`` and assert it isn't called.
"""

from __future__ import annotations

import platform
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weave import version
from weave.conversation.conversation import (
    LLM,
    Message,
    Reasoning,
    Tool,
    Turn,
    log_conversation,
    log_turn,
    start_conversation,
)
from weave.trace.settings import override_settings

_PII_EMAIL = "alice@example.com"
_REDACTED_EMAIL = "<EMAIL>"


@dataclass
class _FakeEntity:
    start: int
    end: int


@dataclass
class _FakeResult:
    text: str


class _FakeAnalyzer:
    def analyze(self, *, text: str, **_: Any) -> list[_FakeEntity]:
        i = text.find(_PII_EMAIL)
        return [_FakeEntity(i, i + len(_PII_EMAIL))] if i >= 0 else []


class _FakeAnonymizer:
    def anonymize(self, *, text: str, analyzer_results: Any) -> _FakeResult:
        return _FakeResult(text.replace(_PII_EMAIL, _REDACTED_EMAIL))


@pytest.fixture
def fake_presidio(monkeypatch: pytest.MonkeyPatch):
    """Replace Presidio engines with stubs that substitute ``_PII_EMAIL`` → ``_REDACTED_EMAIL``.

    Patches ``_get_engines`` (the single dependency on Presidio) so the
    real ``redact_pii`` / ``redact_pii_string`` code paths run end-to-end
    against deterministic engines. Lets tests assert on resulting span
    attrs without installing the NLP stack.
    """
    monkeypatch.setattr(
        "weave.utils.pii_redaction._get_engines",
        lambda: (_FakeAnalyzer(), _FakeAnonymizer()),
    )


def _spans_with_prefix(otel_spans: InMemorySpanExporter, prefix: str) -> list[Any]:
    return [s for s in otel_spans.get_finished_spans() if s.name.startswith(prefix)]


# ---------------------------------------------------------------------------
# WEAVE_DISABLED — runtime span emission suppressed in streaming + batch
# ---------------------------------------------------------------------------


def test_disabled_streaming_emits_no_spans(otel_spans: InMemorySpanExporter):
    with override_settings(disabled=True):
        with start_conversation(agent_name="a", conversation_id="s") as s:
            with s.start_turn() as t:
                with t.llm(model="gpt-4o"):
                    pass
                with t.tool(name="search"):
                    pass
    assert otel_spans.get_finished_spans() == ()


def _user_func_log_turn() -> Any:
    return log_turn(
        conversation_id="s",
        agent_name="a",
        messages=[Message(role="user", content="hi")],
    )


def _user_func_log_conversation() -> Any:
    return log_conversation(
        turns=[Turn(agent_name="a", messages=[Message(role="user", content="hi")])],
        conversation_id="s",
    )


@pytest.mark.parametrize(
    "user_func",
    [
        pytest.param(_user_func_log_turn, id="log_turn"),
        pytest.param(_user_func_log_conversation, id="log_conversation"),
    ],
)
def test_disabled_batch_emits_no_spans(
    user_func: Callable[[], Any], otel_spans: InMemorySpanExporter
):
    with override_settings(disabled=True):
        result = user_func()
    assert result.span_count == 0
    assert otel_spans.get_finished_spans() == ()


# ---------------------------------------------------------------------------
# WEAVE_REDACT_PII — applied across streaming + batch paths
#
# Each helper below sets up a conversation that emits PII through one code path.
# The test runs the helper under ``redact_pii=True`` and asserts that the
# resulting span's content attrs are redacted (no raw email, ``<EMAIL>``
# present).
# ---------------------------------------------------------------------------


def _streaming_tool_with_pii() -> None:
    with start_conversation(conversation_id="s") as sess, sess.start_turn() as t:
        with t.tool(name="lookup") as tool:
            tool.arguments = f'{{"email":"{_PII_EMAIL}"}}'
            tool.result = f"found {_PII_EMAIL}"


def _streaming_llm_messages_with_pii() -> None:
    with start_conversation(conversation_id="s") as sess, sess.start_turn() as t:
        with t.llm(
            model="gpt-4o", system_instructions=[f"contact {_PII_EMAIL}"]
        ) as llm:
            llm.input_messages = [Message(role="user", content=_PII_EMAIL)]
            llm.output_messages = [
                Message(role="assistant", content=f"hi {_PII_EMAIL}")
            ]


def _streaming_llm_reasoning_with_pii() -> None:
    """Regression case for the pre-existing leak: reasoning bypassing redaction."""
    with start_conversation(conversation_id="s") as sess, sess.start_turn() as t:
        with t.llm(model="gpt-4o") as llm:
            llm.reasoning = Reasoning(content=f"think about {_PII_EMAIL}")
            llm.output_messages = [Message(role="assistant", content="ok")]


def _streaming_turn_with_pii() -> None:
    with start_conversation(conversation_id="s") as sess:
        with sess.start_turn(user_message=_PII_EMAIL):
            pass


def _batch_turn_messages_with_pii() -> None:
    log_turn(
        conversation_id="s",
        agent_name="a",
        messages=[Message(role="user", content=_PII_EMAIL)],
    )


def _batch_child_llm_with_pii() -> None:
    log_turn(
        conversation_id="s",
        agent_name="a",
        spans=[
            LLM(
                model="gpt-4o",
                input_messages=[Message(role="user", content=_PII_EMAIL)],
            ),
        ],
    )


def _batch_child_tool_with_pii() -> None:
    log_turn(
        conversation_id="s",
        agent_name="a",
        spans=[Tool(name="lookup", arguments=f'{{"email":"{_PII_EMAIL}"}}')],
    )


@pytest.mark.parametrize(
    ("user_func", "span_prefix", "checked_keys"),
    [
        pytest.param(
            _streaming_tool_with_pii,
            "execute_tool",
            ("gen_ai.tool.call.arguments", "gen_ai.tool.call.result"),
            id="streaming_tool",
        ),
        pytest.param(
            _streaming_llm_messages_with_pii,
            "chat",
            (
                "gen_ai.input.messages",
                "gen_ai.output.messages",
                "gen_ai.system_instructions",
            ),
            id="streaming_llm_messages",
        ),
        pytest.param(
            _streaming_llm_reasoning_with_pii,
            "chat",
            ("gen_ai.output.messages",),
            id="streaming_llm_reasoning",
        ),
        pytest.param(
            _streaming_turn_with_pii,
            "invoke_agent",
            ("gen_ai.input.messages",),
            id="streaming_turn",
        ),
        pytest.param(
            _batch_turn_messages_with_pii,
            "invoke_agent",
            ("gen_ai.input.messages",),
            id="batch_turn_messages",
        ),
        pytest.param(
            _batch_child_llm_with_pii,
            "chat",
            ("gen_ai.input.messages",),
            id="batch_child_llm",
        ),
        pytest.param(
            _batch_child_tool_with_pii,
            "execute_tool",
            ("gen_ai.tool.call.arguments",),
            id="batch_child_tool",
        ),
    ],
)
def test_redact_pii_applied(
    user_func: Callable[[], None],
    span_prefix: str,
    checked_keys: tuple[str, ...],
    otel_spans: InMemorySpanExporter,
    fake_presidio: None,
):
    """redact_pii=True routes content through real redact_pii / redact_pii_string."""
    with override_settings(redact_pii=True):
        user_func()

    spans = _spans_with_prefix(otel_spans, span_prefix)
    assert len(spans) == 1, f"expected 1 {span_prefix} span, got {len(spans)}"
    attrs = dict(spans[0].attributes)
    for key in checked_keys:
        assert _PII_EMAIL not in attrs[key], key
        assert _REDACTED_EMAIL in attrs[key], key


# ---------------------------------------------------------------------------
# include_content=False — content dropped at source, Presidio never loaded
# ---------------------------------------------------------------------------


def _content_off_tool() -> None:
    with start_conversation(conversation_id="s", include_content=False) as sess:
        with sess.start_turn() as t:
            with t.tool(name="lookup") as tool:
                tool.arguments = f'{{"email":"{_PII_EMAIL}"}}'


def _content_off_llm() -> None:
    with start_conversation(conversation_id="s", include_content=False) as sess:
        with sess.start_turn() as t:
            with t.llm(model="gpt-4o") as llm:
                llm.input_messages = [Message(role="user", content=_PII_EMAIL)]
                llm.reasoning = Reasoning(content="think")


def _content_off_turn() -> None:
    with start_conversation(conversation_id="s", include_content=False) as sess:
        with sess.start_turn(user_message=_PII_EMAIL):
            pass


def _content_off_log_turn() -> None:
    log_turn(
        conversation_id="s",
        agent_name="a",
        include_content=False,
        messages=[Message(role="user", content=_PII_EMAIL)],
        spans=[Tool(name="lookup", arguments=f'{{"email":"{_PII_EMAIL}"}}')],
    )


@pytest.mark.parametrize(
    "user_func",
    [
        pytest.param(_content_off_tool, id="tool"),
        pytest.param(_content_off_llm, id="llm"),
        pytest.param(_content_off_turn, id="turn"),
        pytest.param(_content_off_log_turn, id="log_turn"),
    ],
)
def test_include_content_false_skips_presidio(
    user_func: Callable[[], None],
    otel_spans: InMemorySpanExporter,
):
    """Content dropped upstream → Presidio engines must never load.

    Patching ``_get_engines`` and asserting it isn't called is the meaningful
    invariant: no NLP cost paid on content that's already gone.
    """
    with override_settings(redact_pii=True):
        with patch("weave.utils.pii_redaction._get_engines") as mock_get_engines:
            user_func()
    mock_get_engines.assert_not_called()


def _reasoning_content_off_streaming() -> None:
    with start_conversation(conversation_id="s", include_content=False) as sess:
        with sess.start_turn() as t:
            with t.llm(model="gpt-4o") as llm:
                llm.reasoning = Reasoning(content="sensitive reasoning")


def _reasoning_content_off_batch() -> None:
    log_turn(
        conversation_id="s",
        agent_name="a",
        include_content=False,
        spans=[LLM(model="gpt-4o", reasoning=Reasoning(content="sensitive"))],
    )


@pytest.mark.parametrize(
    "user_func",
    [
        pytest.param(_reasoning_content_off_streaming, id="streaming"),
        pytest.param(_reasoning_content_off_batch, id="batch"),
    ],
)
def test_include_content_false_drops_reasoning(
    user_func: Callable[[], None], otel_spans: InMemorySpanExporter
):
    """Regression: LLM.reasoning used to bypass include_content and leak into output.messages."""
    user_func()
    chat_spans = _spans_with_prefix(otel_spans, "chat")
    attrs = dict(chat_spans[0].attributes)
    assert "gen_ai.output.messages" not in attrs


# ---------------------------------------------------------------------------
# WEAVE_CAPTURE_CLIENT_INFO / WEAVE_CAPTURE_SYSTEM_INFO
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
        with start_conversation(conversation_id="s") as sess:
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
            conversation_id="s",
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


def test_settings_independent(otel_spans: InMemorySpanExporter, fake_presidio: None):
    """redact_pii=True + capture_*=False produces redacted content without weave.* attrs."""
    with override_settings(
        redact_pii=True, capture_client_info=False, capture_system_info=False
    ):
        with start_conversation(conversation_id="s") as sess, sess.start_turn() as t:
            with t.tool(name="lookup") as tool:
                tool.arguments = _PII_EMAIL

    tool_spans = _spans_with_prefix(otel_spans, "execute_tool")
    attrs = dict(tool_spans[0].attributes)
    assert _REDACTED_EMAIL in attrs["gen_ai.tool.call.arguments"]
    assert "weave.client_version" not in attrs


def test_defaults_skip_redaction(otel_spans: InMemorySpanExporter):
    """With defaults (redact_pii=False), Presidio engines are never loaded."""
    with patch("weave.utils.pii_redaction._get_engines") as mock_get_engines:
        with start_conversation(conversation_id="s") as sess, sess.start_turn() as t:
            with t.tool(name="x") as tool:
                tool.arguments = _PII_EMAIL
    mock_get_engines.assert_not_called()
