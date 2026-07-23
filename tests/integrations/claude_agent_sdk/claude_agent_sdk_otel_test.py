"""Tests for the OTel variant of the Claude Agent SDK integration.

Sibling of ``claude_agent_sdk_test.py`` — same replay cassettes and flows,
but asserts on emitted OTel GenAI spans instead of Weave calls. The Claude
Agent SDK talks over a subprocess transport, so messages are replayed via
``ReplayTransport`` exactly as in the calls-based test.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Generator
from typing import Any

import pytest
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, query
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from tests.integrations.claude_agent_sdk.conftest import ReplayTransport, load_cassette
from weave.conversation import agent_name_override
from weave.integrations.claude_agent_sdk.otel_integration import (
    get_claude_agent_sdk_otel_patcher,
)


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
    import weave.integrations.claude_agent_sdk.otel_integration as mod

    mod._claude_agent_sdk_otel_patcher = None
    patcher = get_claude_agent_sdk_otel_patcher()
    patcher.attempt_patch()
    yield
    patcher.undo_patch()


# --- helpers ----------------------------------------------------------------


def get_attrs(span: Any) -> dict[str, Any]:
    return dict(span.attributes) if span.attributes is not None else {}


def check_integration_and_strip(attrs: dict[str, Any]) -> dict[str, Any]:
    """Assert + remove the flattened integration.* provenance keys.

    The agent OTel processor stamps integration provenance on every span; pop it
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


async def run_query(cassette: str, prompt: str) -> None:
    async for _ in query(
        prompt=prompt,
        options=ClaudeAgentOptions(),
        transport=ReplayTransport(load_cassette(cassette)),
    ):
        pass


# --- query(): simple text ---------------------------------------------------


@pytest.mark.asyncio
async def test_simple_text_query_otel(otel_spans: InMemorySpanExporter) -> None:
    await run_query("simple_text_response", "What is 2+2?")
    spans = otel_spans.get_finished_spans()

    agent_spans = get_spans_by_op(spans, "invoke_agent")
    chat_spans = get_spans_by_op(spans, "chat")
    assert len(agent_spans) == 1
    assert len(chat_spans) == 1

    # Assert the full attribute dicts so the emitted GenAI shape is visible at a
    # glance and any spec drift (added/removed/renamed keys) fails the test.
    agent_span = agent_spans[0]
    assert agent_span.name == "invoke_agent claude_agent_sdk"
    assert check_integration_and_strip(get_attrs(agent_span)) == {
        "gen_ai.operation.name": "invoke_agent",
        "gen_ai.agent.name": "claude_agent_sdk",
        "gen_ai.provider.name": "anthropic",
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
        "gen_ai.usage.cache_read.input_tokens": 19447,
        "gen_ai.usage.cache_creation.input_tokens": 1024,
    }


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


# --- ClaudeSDKClient: multi-turn --------------------------------------------


@pytest.mark.asyncio
async def test_multi_turn_client_otel(otel_spans: InMemorySpanExporter) -> None:
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
    # Only the agent name is overridden — the rest of the GenAI shape is intact.
    assert attrs["gen_ai.provider.name"] == "anthropic"
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
