"""Tests for the OTel variant of the Claude Agent SDK integration.

Sibling of ``claude_agent_sdk_test.py`` — same replay cassettes and flows,
but asserts on emitted OTel GenAI spans instead of Weave calls. The Claude
Agent SDK talks over a subprocess transport, so messages are replayed via
``ReplayTransport`` exactly as in the calls-based test.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterable, AsyncIterator, Generator
from typing import Any

import pytest
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, query
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode

import weave.integrations.claude_agent_sdk.otel_integration as claude_agent_sdk_otel_integration
from tests.integrations.claude_agent_sdk.conftest import ReplayTransport, load_cassette
from weave.conversation import agent_name_override
from weave.integrations.claude_agent_sdk.otel_integration import (
    get_claude_agent_sdk_otel_patcher,
)
from weave.trace.settings import override_settings
from weave.utils import pii_redaction

_PII_EMAIL = "alice@example.com"
_REDACTED_EMAIL = "<EMAIL>"


@pytest.fixture
def otel_spans(monkeypatch: pytest.MonkeyPatch) -> Generator[InMemorySpanExporter]:
    """Install an in-memory OTel exporter as the global provider.

    Mirrors the conversation-SDK / openai_agents_otel fixture: overrides the
    private ``_TRACER_PROVIDER`` so prior state is restored cleanly and the
    "set once" warning is avoided.
    """
    exporter = InMemorySpanExporter()
    provider = SDKTracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER", provider)
    yield exporter
    provider.shutdown()


@pytest.fixture(autouse=True)
def patch_claude_agent_sdk_otel() -> Generator[None]:
    claude_agent_sdk_otel_integration._claude_agent_sdk_otel_patcher = None
    patcher = get_claude_agent_sdk_otel_patcher()
    patcher.attempt_patch()
    yield
    patcher.undo_patch()


@pytest.fixture(autouse=True)
def disable_capture_info() -> Generator[None]:
    """Keep exact span payload assertions independent of host metadata."""
    with override_settings(
        capture_client_info=False,
        capture_system_info=False,
    ):
        yield


# --- helpers ----------------------------------------------------------------


def get_attrs(span: Any) -> dict[str, Any]:
    return dict(span.attributes) if span.attributes is not None else {}


def check_integration_and_strip(attrs: dict[str, Any]) -> dict[str, Any]:
    """Assert + remove the flattened integration.* provenance keys.

    Conversation attributes stamp integration provenance on every span; pop it
    here so the exact-shape assertions below stay focused on the GenAI semconv keys.
    """
    assert attrs["integration.name"] == "claude_agent_sdk"
    assert attrs["integration.version"]  # weave SDK version
    assert attrs["integration.meta.package_name"] == "claude_agent_sdk"
    return {k: v for k, v in attrs.items() if not k.startswith("integration.")}


def get_spans_by_op(spans: list[Any], op: str) -> list[Any]:
    return [
        span for span in spans if get_attrs(span).get("gen_ai.operation.name") == op
    ]


def get_messages(span: Any, key: str) -> list[dict[str, Any]]:
    raw = get_attrs(span).get(key)
    return json.loads(raw) if raw else []


def get_all_text(messages: list[dict[str, Any]]) -> str:
    return " ".join(
        part.get("content", "")
        for message in messages
        for part in message.get("parts", [])
        if part.get("type") == "text"
    )


def get_part_types(messages: list[dict[str, Any]]) -> set[str]:
    return {
        part.get("type") for message in messages for part in message.get("parts", [])
    }


def user_prompt(text: str, *, should_query: bool | None = None) -> dict[str, Any]:
    prompt: dict[str, Any] = {
        "type": "user",
        "message": {"role": "user", "content": text},
        "parent_tool_use_id": None,
    }
    if should_query is not None:
        prompt["shouldQuery"] = should_query
    return prompt


async def async_prompt_messages(
    *messages: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    for message in messages:
        yield message


def text_query_prompt(
    text: str, *, as_async_iterable: bool
) -> str | AsyncIterable[dict[str, Any]]:
    if as_async_iterable:
        return async_prompt_messages(user_prompt(text))
    return text


async def run_query(
    cassette: str,
    prompt: str | AsyncIterable[dict[str, Any]],
) -> None:
    async for _ in query(
        prompt=prompt,
        options=ClaudeAgentOptions(),
        transport=ReplayTransport(load_cassette(cassette)),
    ):
        pass


# --- query(): string and single-input async-iterable parity -----------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "as_async_iterable",
    [False, True],
    ids=["string-prompt", "async-iterable-prompt"],
)
async def test_single_text_query_otel(
    otel_spans: InMemorySpanExporter,
    as_async_iterable: bool,
) -> None:
    await run_query(
        "simple_text_response",
        text_query_prompt("What is 2+2?", as_async_iterable=as_async_iterable),
    )
    spans = otel_spans.get_finished_spans()
    assert {span.instrumentation_scope.name for span in spans} == {"weave.conversation"}

    agent_spans = get_spans_by_op(spans, "invoke_agent")
    chat_spans = get_spans_by_op(spans, "chat")
    assert len(agent_spans) == 1
    assert len(chat_spans) == 1

    # Assert the full attribute dicts so the emitted GenAI shape is visible at a
    # glance and any spec drift (added/removed/renamed keys) fails the test.
    agent_span = agent_spans[0]
    assert agent_span.name == "invoke_agent claude_agent_sdk"
    assert agent_span.kind == SpanKind.INTERNAL
    assert check_integration_and_strip(get_attrs(agent_span)) == {
        "gen_ai.operation.name": "invoke_agent",
        "gen_ai.agent.name": "claude_agent_sdk",
        "gen_ai.conversation.id": "s-abc123",
        "gen_ai.request.model": "claude-sonnet-4-6",
        "gen_ai.input.messages": (
            '[{"role": "user", "parts": [{"type": "text", "content": "What is 2+2?"}]}]'
        ),
        "gen_ai.output.messages": (
            '[{"role": "assistant", "parts": '
            '[{"type": "text", "content": "The answer is 4."}]}]'
        ),
    }

    chat_span = chat_spans[0]
    assert check_integration_and_strip(get_attrs(chat_span)) == {
        "gen_ai.operation.name": "chat",
        "gen_ai.provider.name": "anthropic",
        "gen_ai.conversation.id": "s-abc123",
        "gen_ai.request.model": "claude-sonnet-4-6",
        "gen_ai.output.messages": (
            '[{"role": "assistant", "parts": '
            '[{"type": "text", "content": "The answer is 4."}]}]'
        ),
        "gen_ai.usage.input_tokens": 25,
        "gen_ai.usage.output_tokens": 10,
    }
    # chat nests under the invoke_agent root
    assert chat_span.parent.span_id == agent_span.context.span_id


# --- query(): tool use ------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_use_query_otel(otel_spans: InMemorySpanExporter) -> None:
    await run_query("tool_use_response", "List files in the current directory")
    spans = otel_spans.get_finished_spans()

    agent_span = get_spans_by_op(spans, "invoke_agent")[0]
    chat_spans = get_spans_by_op(spans, "chat")
    tool_spans = get_spans_by_op(spans, "execute_tool")
    assert len(chat_spans) == 2
    assert len(tool_spans) == 1

    tool_span = tool_spans[0]
    tool_attrs = get_attrs(tool_span)
    assert tool_span.name == "execute_tool Bash"
    assert tool_attrs["gen_ai.tool.name"] == "Bash"
    assert tool_attrs["gen_ai.tool.call.id"] == "toolu_01ABC"
    assert "ls -la" in tool_attrs["gen_ai.tool.call.arguments"]
    assert "file1.py" in tool_attrs["gen_ai.tool.call.result"]
    assert tool_span.parent.span_id == agent_span.context.span_id

    # Aggregate usage lands on exactly one (the final) chat span.
    chats_with_usage = [
        chat_span
        for chat_span in chat_spans
        if "gen_ai.usage.input_tokens" in get_attrs(chat_span)
    ]
    assert len(chats_with_usage) == 1
    assert get_attrs(chats_with_usage[0])["gen_ai.usage.input_tokens"] == 150
    assert get_attrs(chats_with_usage[0])["gen_ai.usage.output_tokens"] == 75

    # The first chat (the one requesting the tool) carries a tool_call part.
    tool_call_chats = [
        chat_span
        for chat_span in chat_spans
        if "tool_call"
        in get_part_types(get_messages(chat_span, "gen_ai.output.messages"))
    ]
    assert len(tool_call_chats) == 1


# --- query(): subagent delegation -------------------------------------------


@pytest.mark.asyncio
async def test_subagent_query_otel(otel_spans: InMemorySpanExporter) -> None:
    await run_query("subagent_response", "Find the capital of France")
    spans = otel_spans.get_finished_spans()

    agent_spans = get_spans_by_op(spans, "invoke_agent")
    assert len(agent_spans) == 2
    root_span = next(
        span
        for span in agent_spans
        if get_attrs(span)["gen_ai.agent.name"] == "claude_agent_sdk"
    )
    subagent_span = next(
        span
        for span in agent_spans
        if get_attrs(span)["gen_ai.agent.name"] == "researcher"
    )
    assert subagent_span.name == "invoke_agent researcher"
    assert subagent_span.parent.span_id == root_span.context.span_id
    assert check_integration_and_strip(get_attrs(subagent_span)) == {
        "gen_ai.operation.name": "invoke_agent",
        "gen_ai.agent.name": "researcher",
        "gen_ai.conversation.id": "s-subagent001",
        "gen_ai.request.model": "claude-haiku-4-5",
        "gen_ai.agent.description": "Research factual questions",
        "gen_ai.tool.call.id": "toolu_agent_01",
        "gen_ai.tool.name": "Agent",
        "gen_ai.tool.call.arguments": json.dumps(
            {
                "subagent_type": "researcher",
                "description": "Research factual questions",
                "prompt": "Find the capital of France.",
            }
        ),
        "gen_ai.input.messages": json.dumps(
            [
                {
                    "role": "user",
                    "parts": [
                        {
                            "type": "text",
                            "content": "Find the capital of France.",
                        }
                    ],
                }
            ]
        ),
        "gen_ai.tool.call.result": "The capital of France is Paris.",
        "gen_ai.output.messages": json.dumps(
            [
                {
                    "role": "assistant",
                    "parts": [
                        {
                            "type": "text",
                            "content": "The capital of France is Paris.",
                        }
                    ],
                }
            ]
        ),
    }

    chat_spans = get_spans_by_op(spans, "chat")
    assert len(chat_spans) == 4
    assert [
        span.parent.span_id == subagent_span.context.span_id for span in chat_spans
    ].count(True) == 2
    assert [
        span.parent.span_id == root_span.context.span_id for span in chat_spans
    ].count(True) == 2

    tool_spans = get_spans_by_op(spans, "execute_tool")
    assert len(tool_spans) == 1
    tool_span = tool_spans[0]
    assert tool_span.name == "execute_tool Bash"
    assert tool_span.parent.span_id == subagent_span.context.span_id
    assert check_integration_and_strip(get_attrs(tool_span)) == {
        "gen_ai.operation.name": "execute_tool",
        "gen_ai.tool.name": "Bash",
        "gen_ai.tool.call.id": "toolu_bash_01",
        "gen_ai.tool.call.arguments": '{"command": "printf Paris"}',
        "gen_ai.tool.call.result": "Paris",
        "gen_ai.conversation.id": "s-subagent001",
    }


@pytest.mark.asyncio
async def test_subagent_query_content_is_pii_redacted_otel(
    otel_spans: InMemorySpanExporter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = load_cassette("subagent_response")
    messages[1]["message"]["content"][1]["input"]["prompt"] = f"Research {_PII_EMAIL}"
    messages[5]["message"]["content"][0]["content"][0]["text"] = f"Found {_PII_EMAIL}"

    def redact_messages(messages: list[Any]) -> list[Any]:
        return [
            message.model_copy(
                update={"content": message.content.replace(_PII_EMAIL, _REDACTED_EMAIL)}
            )
            for message in messages
        ]

    monkeypatch.setattr(pii_redaction, "redact_messages", redact_messages)
    monkeypatch.setattr(
        pii_redaction,
        "redact_pii_string",
        lambda value: value.replace(_PII_EMAIL, _REDACTED_EMAIL),
    )

    with override_settings(redact_pii=True):
        async for _ in query(
            prompt="Delegate sensitive research",
            options=ClaudeAgentOptions(),
            transport=ReplayTransport(messages),
        ):
            pass

    subagent_span = next(
        span
        for span in get_spans_by_op(otel_spans.get_finished_spans(), "invoke_agent")
        if get_attrs(span)["gen_ai.agent.name"] == "researcher"
    )
    assert check_integration_and_strip(get_attrs(subagent_span)) == {
        "gen_ai.operation.name": "invoke_agent",
        "gen_ai.agent.name": "researcher",
        "gen_ai.conversation.id": "s-subagent001",
        "gen_ai.request.model": "claude-haiku-4-5",
        "gen_ai.agent.description": "Research factual questions",
        "gen_ai.input.messages": json.dumps(
            [
                {
                    "role": "user",
                    "parts": [
                        {"type": "text", "content": f"Research {_REDACTED_EMAIL}"}
                    ],
                }
            ]
        ),
        "gen_ai.output.messages": json.dumps(
            [
                {
                    "role": "assistant",
                    "parts": [{"type": "text", "content": f"Found {_REDACTED_EMAIL}"}],
                }
            ]
        ),
        "gen_ai.tool.name": "Agent",
        "gen_ai.tool.call.id": "toolu_agent_01",
        "gen_ai.tool.call.arguments": json.dumps(
            {
                "subagent_type": "researcher",
                "description": "Research factual questions",
                "prompt": f"Research {_REDACTED_EMAIL}",
            }
        ),
        "gen_ai.tool.call.result": f"Found {_REDACTED_EMAIL}",
    }


@pytest.mark.parametrize(
    (
        "status",
        "summary",
        "tool_name",
        "notification_has_tool_use_id",
        "launch_has_task_id",
        "expected_status_code",
        "expected_status_description",
        "expected_error_type",
    ),
    [
        pytest.param(
            "completed",
            "The capital of France is Paris.",
            "Agent",
            False,
            True,
            StatusCode.UNSET,
            None,
            None,
            id="completed-agent-task-id-fallback",
        ),
        pytest.param(
            "failed",
            "The background researcher failed.",
            "Agent",
            True,
            True,
            StatusCode.ERROR,
            "background subagent failed",
            "claude_agent_sdk.task_failed",
            id="failed-agent-direct-tool-use-id",
        ),
        pytest.param(
            "stopped",
            "The background researcher was stopped.",
            "Task",
            False,
            False,
            StatusCode.ERROR,
            "background subagent stopped",
            "claude_agent_sdk.task_stopped",
            id="stopped-legacy-task-task-id-fallback",
        ),
    ],
)
@pytest.mark.asyncio
async def test_background_subagent_closes_on_task_notification_otel(
    status: str,
    summary: str,
    tool_name: str,
    notification_has_tool_use_id: bool,
    launch_has_task_id: bool,
    expected_status_code: StatusCode,
    expected_status_description: str | None,
    expected_error_type: str | None,
    otel_spans: InMemorySpanExporter,
) -> None:
    messages = load_cassette("background_subagent_response")
    messages[1]["message"]["content"][1]["name"] = tool_name

    launch_text = messages[2]["message"]["content"][0]["content"][0]["text"]
    launch_payload = json.loads(launch_text)
    if not launch_has_task_id:
        del launch_payload["agentId"]
    messages[2]["message"]["content"][0]["content"][0]["text"] = json.dumps(
        launch_payload
    )

    notification = messages[8]
    notification["status"] = status
    notification["summary"] = summary
    if notification_has_tool_use_id:
        notification["tool_use_id"] = "toolu_background_agent_01"

    async for _ in query(
        prompt="Research in the background",
        options=ClaudeAgentOptions(),
        transport=ReplayTransport(messages),
    ):
        pass

    spans = otel_spans.get_finished_spans()
    agent_spans = get_spans_by_op(spans, "invoke_agent")
    assert len(agent_spans) == 2
    root_span = next(
        span
        for span in agent_spans
        if get_attrs(span)["gen_ai.agent.name"] == "claude_agent_sdk"
    )
    subagent_span = next(
        span
        for span in agent_spans
        if get_attrs(span)["gen_ai.agent.name"] == "researcher"
    )

    expected_subagent_attrs = {
        "gen_ai.operation.name": "invoke_agent",
        "gen_ai.agent.name": "researcher",
        "gen_ai.conversation.id": "s-background-subagent001",
        "gen_ai.request.model": "claude-haiku-4-5",
        "gen_ai.agent.id": "task-background-01",
        "gen_ai.agent.description": "Research while the root agent continues",
        "gen_ai.input.messages": json.dumps(
            [
                {
                    "role": "user",
                    "parts": [
                        {
                            "type": "text",
                            "content": "Find the capital of France.",
                        }
                    ],
                }
            ]
        ),
        "gen_ai.output.messages": json.dumps(
            [
                {
                    "role": "assistant",
                    "parts": [{"type": "text", "content": summary}],
                }
            ]
        ),
        "gen_ai.tool.name": tool_name,
        "gen_ai.tool.call.id": "toolu_background_agent_01",
        "gen_ai.tool.call.arguments": json.dumps(
            {
                "subagent_type": "researcher",
                "description": "Research while the root agent continues",
                "prompt": "Find the capital of France.",
                "model": "claude-haiku-4-5",
                "run_in_background": True,
            }
        ),
        "gen_ai.tool.call.result": summary,
        "claude_agent_sdk.task.status": status,
    }
    if expected_error_type is not None:
        expected_subagent_attrs["error.type"] = expected_error_type
    assert check_integration_and_strip(get_attrs(subagent_span)) == (
        expected_subagent_attrs
    )
    assert subagent_span.name == "invoke_agent researcher"
    assert subagent_span.parent.span_id == root_span.context.span_id
    assert subagent_span.status.status_code == expected_status_code
    assert subagent_span.status.description == expected_status_description

    chat_spans = get_spans_by_op(spans, "chat")
    assert [
        (
            span.parent.span_id,
            get_all_text(get_messages(span, "gen_ai.output.messages")),
        )
        for span in chat_spans
    ] == [
        (root_span.context.span_id, "I will launch a background researcher."),
        (root_span.context.span_id, "While that runs, I will prepare the response."),
        (subagent_span.context.span_id, "I will verify the capital."),
        (subagent_span.context.span_id, "The delegated research is complete."),
        (root_span.context.span_id, "The background researcher confirmed Paris."),
    ]
    child_chat_spans = [
        span
        for span in chat_spans
        if span.parent.span_id == subagent_span.context.span_id
    ]
    assert [span.end_time <= subagent_span.end_time for span in child_chat_spans] == [
        True,
        True,
    ]

    tool_spans = get_spans_by_op(spans, "execute_tool")
    assert len(tool_spans) == 1
    assert tool_spans[0].parent.span_id == subagent_span.context.span_id
    assert check_integration_and_strip(get_attrs(tool_spans[0])) == {
        "gen_ai.operation.name": "execute_tool",
        "gen_ai.tool.name": "Bash",
        "gen_ai.tool.call.id": "toolu_background_bash_01",
        "gen_ai.tool.call.arguments": '{"command": "printf Paris"}',
        "gen_ai.tool.call.result": "Paris",
        "gen_ai.conversation.id": "s-background-subagent001",
    }


@pytest.mark.asyncio
async def test_background_subagent_summary_is_pii_redacted_otel(
    otel_spans: InMemorySpanExporter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = load_cassette("background_subagent_response")
    messages[1]["message"]["content"][1]["input"]["prompt"] = f"Research {_PII_EMAIL}"
    messages[8]["summary"] = f"Found {_PII_EMAIL}"

    def redact_messages(messages: list[Any]) -> list[Any]:
        return [
            message.model_copy(
                update={"content": message.content.replace(_PII_EMAIL, _REDACTED_EMAIL)}
            )
            for message in messages
        ]

    monkeypatch.setattr(pii_redaction, "redact_messages", redact_messages)
    monkeypatch.setattr(
        pii_redaction,
        "redact_pii_string",
        lambda value: value.replace(_PII_EMAIL, _REDACTED_EMAIL),
    )

    with override_settings(redact_pii=True):
        async for _ in query(
            prompt="Delegate sensitive background research",
            options=ClaudeAgentOptions(),
            transport=ReplayTransport(messages),
        ):
            pass

    subagent_span = next(
        span
        for span in get_spans_by_op(otel_spans.get_finished_spans(), "invoke_agent")
        if get_attrs(span)["gen_ai.agent.name"] == "researcher"
    )
    assert check_integration_and_strip(get_attrs(subagent_span)) == {
        "gen_ai.operation.name": "invoke_agent",
        "gen_ai.agent.name": "researcher",
        "gen_ai.conversation.id": "s-background-subagent001",
        "gen_ai.request.model": "claude-haiku-4-5",
        "gen_ai.agent.id": "task-background-01",
        "gen_ai.agent.description": "Research while the root agent continues",
        "gen_ai.input.messages": json.dumps(
            [
                {
                    "role": "user",
                    "parts": [
                        {
                            "type": "text",
                            "content": f"Research {_REDACTED_EMAIL}",
                        }
                    ],
                }
            ]
        ),
        "gen_ai.output.messages": json.dumps(
            [
                {
                    "role": "assistant",
                    "parts": [{"type": "text", "content": f"Found {_REDACTED_EMAIL}"}],
                }
            ]
        ),
        "gen_ai.tool.name": "Agent",
        "gen_ai.tool.call.id": "toolu_background_agent_01",
        "gen_ai.tool.call.arguments": json.dumps(
            {
                "subagent_type": "researcher",
                "description": "Research while the root agent continues",
                "prompt": f"Research {_REDACTED_EMAIL}",
                "model": "claude-haiku-4-5",
                "run_in_background": True,
            }
        ),
        "gen_ai.tool.call.result": f"Found {_REDACTED_EMAIL}",
        "claude_agent_sdk.task.status": "completed",
    }


@pytest.mark.asyncio
async def test_parallel_subagents_close_out_of_order_otel(
    otel_spans: InMemorySpanExporter,
) -> None:
    """Two delegations open A, B and close A, B — completion, not LIFO, order.

    Spans the integration creates itself are pinned to an explicit parent, so
    the risk is to the ambient OTel context that surrounds user code running
    between streamed messages. ``user_code`` stands in for that.
    """
    tracer = otel_trace.get_tracer("test.user_code")
    async for _ in query(
        prompt="Find the capital of France and the largest planet",
        options=ClaudeAgentOptions(),
        transport=ReplayTransport(load_cassette("parallel_subagent_response")),
    ):
        tracer.start_span("user_code").end()

    spans = otel_spans.get_finished_spans()
    agent_spans = get_spans_by_op(spans, "invoke_agent")
    assert len(agent_spans) == 3
    by_name = {get_attrs(span)["gen_ai.agent.name"]: span for span in agent_spans}
    root = by_name["claude_agent_sdk"]
    geographer = by_name["geographer"]
    astronomer = by_name["astronomer"]

    assert geographer.parent.span_id == root.context.span_id
    assert astronomer.parent.span_id == root.context.span_id
    assert get_attrs(geographer)["gen_ai.tool.call.result"] == (
        "The capital of France is Paris."
    )
    assert get_attrs(astronomer)["gen_ai.tool.call.result"] == (
        "The largest planet is Jupiter."
    )

    # Each delegation's own chat nests under it, not under its sibling.
    chats_by_parent: dict[int, list[Any]] = {}
    for chat in get_spans_by_op(spans, "chat"):
        chats_by_parent.setdefault(chat.parent.span_id, []).append(chat)
    assert (
        get_all_text(
            get_messages(
                chats_by_parent[geographer.context.span_id][0], "gen_ai.output.messages"
            )
        )
        == "The capital of France is Paris."
    )
    assert (
        get_all_text(
            get_messages(
                chats_by_parent[astronomer.context.span_id][0], "gen_ai.output.messages"
            )
        )
        == "The largest planet is Jupiter."
    )

    # The ambient context must never hand user code an ended span as its
    # parent: detaching out of LIFO order restores whichever span was current
    # when the later token was attached, and that sibling has already ended.
    ended_subagents = {geographer.context.span_id, astronomer.context.span_id}
    orphaned = [
        span
        for span in spans
        if span.name == "user_code"
        and span.parent is not None
        and span.parent.span_id in ended_subagents
    ]
    assert orphaned == []


# --- query(): prompt caching ------------------------------------------------


@pytest.mark.asyncio
async def test_cached_usage_is_normalized_in_otel_span(
    otel_spans: InMemorySpanExporter,
) -> None:
    await run_query("cache_usage_response", "Use the cache")

    chat_spans = get_spans_by_op(otel_spans.get_finished_spans(), "chat")
    assert len(chat_spans) == 1
    usage_attrs = {
        key: value
        for key, value in get_attrs(chat_spans[0]).items()
        if key.startswith("gen_ai.usage.")
    }
    assert usage_attrs == {
        "gen_ai.usage.input_tokens": 20481,
        "gen_ai.usage.output_tokens": 75,
        "gen_ai.usage.cache_creation.input_tokens": 1024,
        "gen_ai.usage.cache_read.input_tokens": 19447,
    }


# --- query(): multiple tools in one response --------------------------------


@pytest.mark.asyncio
async def test_multi_tool_query_otel(otel_spans: InMemorySpanExporter) -> None:
    await run_query("multi_tool_response", "Check both files")
    spans = otel_spans.get_finished_spans()

    agent_span = get_spans_by_op(spans, "invoke_agent")[0]
    tool_spans = get_spans_by_op(spans, "execute_tool")
    assert {tool_span.name for tool_span in tool_spans} == {
        "execute_tool Read",
        "execute_tool Bash",
    }
    for tool_span in tool_spans:
        assert tool_span.parent.span_id == agent_span.context.span_id

    results = {
        get_attrs(tool_span)["gen_ai.tool.name"]: get_attrs(tool_span)[
            "gen_ai.tool.call.result"
        ]
        for tool_span in tool_spans
    }
    assert "print('hello')" in results["Read"]
    assert "/tmp" in results["Bash"]


# --- query(): thinking folds into one chat span -----------------------------


@pytest.mark.asyncio
async def test_thinking_query_otel(otel_spans: InMemorySpanExporter) -> None:
    await run_query("thinking_response", "Think about it")
    spans = otel_spans.get_finished_spans()

    # Thinking-only messages are buffered into the following response, so the
    # extended-thinking turn produces a single chat span, not two.
    chat_spans = get_spans_by_op(spans, "chat")
    assert len(chat_spans) == 1

    output_messages = get_messages(chat_spans[0], "gen_ai.output.messages")
    assert "reasoning" in get_part_types(output_messages)
    reasoning_text = " ".join(
        part.get("content", "")
        for message in output_messages
        for part in message.get("parts", [])
        if part.get("type") == "reasoning"
    )
    assert "Let me think about this carefully" in reasoning_text
    assert "the answer is 42" in get_all_text(output_messages)


# --- query(): error result sets span status ---------------------------------


@pytest.mark.asyncio
async def test_error_response_otel(otel_spans: InMemorySpanExporter) -> None:
    await run_query("error_response", "Do something")
    spans = otel_spans.get_finished_spans()

    agent_span = get_spans_by_op(spans, "invoke_agent")[0]
    assert agent_span.status.status_code == StatusCode.ERROR


# --- trace nesting: turns nest under the ambient OTel context ---------------


@pytest.mark.asyncio
async def test_ambient_trace_nesting_otel(otel_spans: InMemorySpanExporter) -> None:
    """A turn nests under whatever OTel span is already active."""
    tracer = otel_trace.get_tracer("test.app")
    with tracer.start_as_current_span("app.request") as outer_span:
        outer_context = outer_span.get_span_context()
        await run_query("simple_text_response", "What is 2+2?")

    spans = otel_spans.get_finished_spans()
    agent_span = get_spans_by_op(spans, "invoke_agent")[0]
    assert agent_span.parent is not None
    assert agent_span.parent.span_id == outer_context.span_id
    assert agent_span.context.trace_id == outer_context.trace_id


# --- ClaudeSDKClient: one turn per receive_response() ------------------------


@pytest.mark.asyncio
async def test_string_client_queries_use_one_turn_per_response_otel(
    otel_spans: InMemorySpanExporter,
) -> None:
    sdk_client = ClaudeSDKClient(
        options=ClaudeAgentOptions(),
        transport=ReplayTransport(load_cassette("multi_turn_response")),
    )
    await sdk_client.connect()

    await sdk_client.query("Hello")
    _ = [message async for message in sdk_client.receive_response()]
    await sdk_client.query("What is the capital of France?")
    _ = [message async for message in sdk_client.receive_response()]

    await sdk_client.disconnect()

    spans = otel_spans.get_finished_spans()
    agent_spans = get_spans_by_op(spans, "invoke_agent")
    assert len(agent_spans) == 2

    # Both turns share one conversation id (the SDK session_id)...
    conversation_ids = {
        get_attrs(agent_span)["gen_ai.conversation.id"] for agent_span in agent_spans
    }
    assert conversation_ids == {"s-mt001"}
    # ...but each turn is its own trace (no ambient span held across turns).
    trace_ids = {agent_span.context.trace_id for agent_span in agent_spans}
    assert len(trace_ids) == 2

    prompts = {
        get_all_text(get_messages(agent_span, "gen_ai.input.messages"))
        for agent_span in agent_spans
    }
    assert prompts == {"Hello", "What is the capital of France?"}


@pytest.mark.asyncio
async def test_async_iterable_client_query_uses_one_turn_per_response_otel(
    otel_spans: InMemorySpanExporter,
) -> None:
    """Each receive_response() remains a single turn for async client input."""
    sdk_client = ClaudeSDKClient(
        options=ClaudeAgentOptions(),
        transport=ReplayTransport(load_cassette("multi_turn_response")),
    )
    await sdk_client.connect()
    await sdk_client.query(
        async_prompt_messages(
            user_prompt("Hello"),
            user_prompt("What is the capital of France?"),
        )
    )

    responses = [
        [type(message).__name__ async for message in sdk_client.receive_response()],
        [type(message).__name__ async for message in sdk_client.receive_response()],
    ]
    await sdk_client.disconnect()

    assert responses == [
        ["SystemMessage", "AssistantMessage", "ResultMessage"],
        ["AssistantMessage", "ResultMessage"],
    ]
    agent_spans = sorted(
        get_spans_by_op(otel_spans.get_finished_spans(), "invoke_agent"),
        key=lambda span: span.start_time,
    )
    assert [
        get_all_text(get_messages(agent_span, "gen_ai.input.messages"))
        for agent_span in agent_spans
    ] == [
        "Hello",
        "What is the capital of France?",
    ]


# --- query(): async-iterable image prompt -----------------------------------


@pytest.mark.asyncio
async def test_async_iterable_image_prompt_otel(
    otel_spans: InMemorySpanExporter,
) -> None:
    image_base64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    image_message = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_base64,
                    },
                },
                {"type": "text", "text": "Describe this image."},
            ],
        },
        "parent_tool_use_id": None,
    }

    async def image_prompt() -> AsyncIterator[dict[str, Any]]:
        yield image_message

    transport = ReplayTransport(load_cassette("simple_text_response"))
    messages = [
        message
        async for message in query(
            prompt=image_prompt(),
            options=ClaudeAgentOptions(),
            transport=transport,
        )
    ]

    assert [type(message).__name__ for message in messages] == [
        "SystemMessage",
        "AssistantMessage",
        "ResultMessage",
    ]
    assert transport.user_messages == [image_message]
    agent_spans = get_spans_by_op(otel_spans.get_finished_spans(), "invoke_agent")
    assert len(agent_spans) == 1
    assert get_messages(agent_spans[0], "gen_ai.input.messages") == [
        {
            "role": "user",
            "parts": [
                {
                    "type": "blob",
                    "mime_type": "image/png",
                    "modality": "image",
                    "content": image_base64,
                },
                {"type": "text", "content": "Describe this image."},
            ],
        }
    ]


# --- query(): async-iterable multi-turn prompts ------------------------------


@pytest.mark.asyncio
async def test_async_iterable_query_multi_turn_otel(
    otel_spans: InMemorySpanExporter,
) -> None:
    messages = [
        message
        async for message in query(
            prompt=async_prompt_messages(
                user_prompt("Hello"),
                user_prompt("What is the capital of France?"),
            ),
            options=ClaudeAgentOptions(),
            transport=ReplayTransport(load_cassette("multi_turn_response")),
        )
    ]

    assert [type(message).__name__ for message in messages] == [
        "SystemMessage",
        "AssistantMessage",
        "ResultMessage",
        "AssistantMessage",
        "ResultMessage",
    ]
    agent_spans = sorted(
        get_spans_by_op(otel_spans.get_finished_spans(), "invoke_agent"),
        key=lambda span: span.start_time,
    )
    assert len(agent_spans) == 2
    assert [
        get_messages(agent_span, "gen_ai.input.messages") for agent_span in agent_spans
    ] == [
        [{"role": "user", "parts": [{"type": "text", "content": "Hello"}]}],
        [
            {
                "role": "user",
                "parts": [
                    {
                        "type": "text",
                        "content": "What is the capital of France?",
                    }
                ],
            }
        ],
    ]
    assert [
        get_messages(agent_span, "gen_ai.output.messages") for agent_span in agent_spans
    ] == [
        [
            {
                "role": "assistant",
                "parts": [{"type": "text", "content": "Hello! How can I help you?"}],
            }
        ],
        [
            {
                "role": "assistant",
                "parts": [
                    {
                        "type": "text",
                        "content": "The capital of France is Paris.",
                    }
                ],
            }
        ],
    ]
    assert {
        get_attrs(agent_span)["gen_ai.conversation.id"] for agent_span in agent_spans
    } == {"s-mt001"}
    assert len({agent_span.context.trace_id for agent_span in agent_spans}) == 2


@pytest.mark.asyncio
async def test_async_iterable_query_buffers_non_query_inputs_otel(
    otel_spans: InMemorySpanExporter,
) -> None:
    messages = [
        message
        async for message in query(
            prompt=async_prompt_messages(
                user_prompt("Background context", should_query=False),
                user_prompt("Answer using that context"),
            ),
            options=ClaudeAgentOptions(),
            transport=ReplayTransport(load_cassette("simple_text_response")),
        )
    ]

    assert [type(message).__name__ for message in messages] == [
        "SystemMessage",
        "AssistantMessage",
        "ResultMessage",
    ]
    agent_spans = get_spans_by_op(otel_spans.get_finished_spans(), "invoke_agent")
    assert len(agent_spans) == 1
    assert get_messages(agent_spans[0], "gen_ai.input.messages") == [
        {
            "role": "user",
            "parts": [{"type": "text", "content": "Background context"}],
        },
        {
            "role": "user",
            "parts": [{"type": "text", "content": "Answer using that context"}],
        },
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "as_async_iterable",
    [False, True],
    ids=["string-prompt", "async-iterable-prompt"],
)
async def test_query_failure_before_first_response_records_error_turn_otel(
    otel_spans: InMemorySpanExporter,
    as_async_iterable: bool,
) -> None:
    transport = ReplayTransport(
        load_cassette("simple_text_response"),
        fail_after_messages=0,
    )

    with pytest.raises(Exception, match="replay transport failed"):
        _ = [
            message
            async for message in query(
                prompt=text_query_prompt("Hello", as_async_iterable=as_async_iterable),
                options=ClaudeAgentOptions(),
                transport=transport,
            )
        ]

    agent_spans = get_spans_by_op(otel_spans.get_finished_spans(), "invoke_agent")
    assert len(agent_spans) == 1
    assert agent_spans[0].status.status_code == StatusCode.ERROR
    assert get_messages(agent_spans[0], "gen_ai.input.messages") == [
        {"role": "user", "parts": [{"type": "text", "content": "Hello"}]}
    ]
    assert get_messages(agent_spans[0], "gen_ai.output.messages") == []


@pytest.mark.asyncio
async def test_async_iterable_query_failure_between_turns_records_error_turn_otel(
    otel_spans: InMemorySpanExporter,
) -> None:
    transport = ReplayTransport(
        load_cassette("multi_turn_response"),
        fail_after_messages=3,
    )
    seen_messages: list[str] = []

    async def consume_query() -> None:
        async for message in query(
            prompt=async_prompt_messages(
                user_prompt("Hello"),
                user_prompt("Second prompt"),
            ),
            options=ClaudeAgentOptions(),
            transport=transport,
        ):
            seen_messages.append(type(message).__name__)

    with pytest.raises(Exception, match="replay transport failed"):
        await consume_query()

    assert seen_messages == ["SystemMessage", "AssistantMessage", "ResultMessage"]
    agent_spans = sorted(
        get_spans_by_op(otel_spans.get_finished_spans(), "invoke_agent"),
        key=lambda span: span.start_time,
    )
    assert len(agent_spans) == 2
    assert [span.status.status_code for span in agent_spans] == [
        StatusCode.UNSET,
        StatusCode.ERROR,
    ]
    assert [
        get_messages(agent_span, "gen_ai.input.messages") for agent_span in agent_spans
    ] == [
        [{"role": "user", "parts": [{"type": "text", "content": "Hello"}]}],
        [
            {
                "role": "user",
                "parts": [{"type": "text", "content": "Second prompt"}],
            }
        ],
    ]
    assert [
        get_messages(agent_span, "gen_ai.output.messages") for agent_span in agent_spans
    ] == [
        [
            {
                "role": "assistant",
                "parts": [{"type": "text", "content": "Hello! How can I help you?"}],
            }
        ],
        [],
    ]
    assert {
        get_attrs(agent_span)["gen_ai.conversation.id"] for agent_span in agent_spans
    } == {"s-mt001"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "as_async_iterable",
    [False, True],
    ids=["string-prompt", "async-iterable-prompt"],
)
async def test_query_failure_after_final_result_does_not_add_turn_otel(
    otel_spans: InMemorySpanExporter,
    as_async_iterable: bool,
) -> None:
    transport = ReplayTransport(
        load_cassette("simple_text_response"),
        fail_after_messages=3,
    )
    seen_messages: list[str] = []

    async def consume_query() -> None:
        async for message in query(
            prompt=text_query_prompt("Hello", as_async_iterable=as_async_iterable),
            options=ClaudeAgentOptions(),
            transport=transport,
        ):
            seen_messages.append(type(message).__name__)

    with pytest.raises(Exception, match="replay transport failed"):
        await consume_query()

    assert seen_messages == ["SystemMessage", "AssistantMessage", "ResultMessage"]
    agent_spans = get_spans_by_op(otel_spans.get_finished_spans(), "invoke_agent")
    assert len(agent_spans) == 1
    assert agent_spans[0].status.status_code == StatusCode.UNSET
    assert get_messages(agent_spans[0], "gen_ai.input.messages") == [
        {"role": "user", "parts": [{"type": "text", "content": "Hello"}]}
    ]
    assert get_messages(agent_spans[0], "gen_ai.output.messages") == [
        {
            "role": "assistant",
            "parts": [{"type": "text", "content": "The answer is 4."}],
        }
    ]


# --- agent name override ----------------------------------------------------


@pytest.mark.asyncio
async def test_custom_agent_name_query_otel(otel_spans: InMemorySpanExporter) -> None:
    """A custom name lands on both the span name and gen_ai.agent.name."""
    with agent_name_override("research_agent"):
        await run_query("simple_text_response", "What is 2+2?")

    agent_span = get_spans_by_op(otel_spans.get_finished_spans(), "invoke_agent")[0]
    assert agent_span.name == "invoke_agent research_agent"
    attrs = check_integration_and_strip(get_attrs(agent_span))
    assert attrs["gen_ai.agent.name"] == "research_agent"
    # Only the agent name is overridden — the model remains intact.
    assert attrs["gen_ai.request.model"] == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_agent_name_restored_after_context_otel(
    otel_spans: InMemorySpanExporter,
) -> None:
    """Inside the block the custom name applies; outside it reverts to default."""
    with agent_name_override("scoped_agent"):
        await run_query("simple_text_response", "What is 2+2?")
    await run_query("simple_text_response", "What is 2+2?")

    agent_spans = get_spans_by_op(otel_spans.get_finished_spans(), "invoke_agent")
    names = sorted(get_attrs(span)["gen_ai.agent.name"] for span in agent_spans)
    assert names == ["claude_agent_sdk", "scoped_agent"]
    span_names = sorted(span.name for span in agent_spans)
    assert span_names == [
        "invoke_agent claude_agent_sdk",
        "invoke_agent scoped_agent",
    ]


@pytest.mark.asyncio
async def test_custom_agent_name_multi_turn_otel(
    otel_spans: InMemorySpanExporter,
) -> None:
    """The override applies to every turn of a ClaudeSDKClient session."""
    with agent_name_override("support_agent"):
        sdk_client = ClaudeSDKClient(
            options=ClaudeAgentOptions(),
            transport=ReplayTransport(load_cassette("multi_turn_response")),
        )
        await sdk_client.connect()
        await sdk_client.query("Hello")
        _ = [message async for message in sdk_client.receive_response()]
        await sdk_client.query("What is the capital of France?")
        _ = [message async for message in sdk_client.receive_response()]
        await sdk_client.disconnect()

    agent_spans = get_spans_by_op(otel_spans.get_finished_spans(), "invoke_agent")
    assert len(agent_spans) == 2
    assert {span.name for span in agent_spans} == {"invoke_agent support_agent"}
    assert {get_attrs(span)["gen_ai.agent.name"] for span in agent_spans} == {
        "support_agent"
    }


@pytest.mark.asyncio
async def test_concurrent_queries_distinct_agent_names_otel(
    otel_spans: InMemorySpanExporter,
) -> None:
    """Concurrent queries each keep their own name (ContextVar isolation)."""

    async def named_query(agent_name: str, prompt: str) -> None:
        with agent_name_override(agent_name):
            await run_query("simple_text_response", prompt)

    await asyncio.gather(
        named_query("agent_a", "What is 2+2?"),
        named_query("agent_b", "What is 3+3?"),
    )

    agent_spans = get_spans_by_op(otel_spans.get_finished_spans(), "invoke_agent")
    assert {get_attrs(span)["gen_ai.agent.name"] for span in agent_spans} == {
        "agent_a",
        "agent_b",
    }


@pytest.mark.parametrize("bad_name", ["", "   ", "\n\t"])
def test_agent_name_rejects_empty(bad_name: str) -> None:
    """An empty/whitespace name fails loudly rather than mislabeling spans."""
    with pytest.raises(ValueError, match="non-empty"):
        with agent_name_override(bad_name):
            pass
