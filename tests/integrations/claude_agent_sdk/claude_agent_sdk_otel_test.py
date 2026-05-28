"""Tests for the OTel variant of the Claude Agent SDK integration.

Sibling of ``claude_agent_sdk_test.py`` — reuses the same cassette-driven
``ReplayTransport`` flows, but installs the OTel patcher and asserts on
emitted OpenTelemetry spans (via an ``InMemorySpanExporter``) rather
than Weave calls.
"""

from __future__ import annotations

import json
from collections.abc import Generator

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    query,
)
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from tests.integrations.claude_agent_sdk.conftest import ReplayTransport, load_cassette
from weave.integrations.claude_agent_sdk.patcher import (
    get_claude_agent_sdk_otel_patcher,
)


@pytest.fixture
def otel_spans(monkeypatch: pytest.MonkeyPatch):
    """Install an in-memory OTel exporter and return it for assertions.

    Mirrors the fixture in ``openai_agents_otel_test.py`` — overrides the
    global tracer provider so prior state is restored cleanly between
    tests.
    """
    exporter = InMemorySpanExporter()
    provider = SDKTracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER", provider)
    yield exporter
    provider.shutdown()


@pytest.fixture(autouse=True)
def patch_claude_agent_sdk_otel() -> Generator[None, None, None]:
    import weave.integrations.claude_agent_sdk.patcher as mod

    mod._claude_agent_sdk_otel_patcher = None
    patcher = get_claude_agent_sdk_otel_patcher()
    patcher.attempt_patch()
    yield
    patcher.undo_patch()


def _invoke_agent_span(exporter: InMemorySpanExporter):
    """Pick the single invoke_agent span from the exporter.

    The ``query()`` flow wraps the invoke_agent in an outer
    "Conversation" span, so the invoke_agent is no longer the trace
    root. Filter by operation name instead of by ``parent is None``.
    """
    spans = [
        s
        for s in exporter.get_finished_spans()
        if s.attributes.get("gen_ai.operation.name") == "invoke_agent"
    ]
    assert len(spans) == 1, f"expected 1 invoke_agent span, found {len(spans)}"
    return spans[0]


def _conversation_span(exporter: InMemorySpanExporter):
    """Pick the outer conversation span (the only trace root for query())."""
    spans = [s for s in exporter.get_finished_spans() if s.parent is None]
    assert len(spans) == 1, f"expected 1 root span, found {len(spans)}"
    return spans[0]


def _tool_spans(exporter: InMemorySpanExporter) -> list:
    return [
        s
        for s in exporter.get_finished_spans()
        if s.attributes.get("gen_ai.operation.name") == "execute_tool"
    ]


# =====================================================================
# query() — simple text response
# =====================================================================


@pytest.mark.asyncio
async def test_simple_text_query(otel_spans: InMemorySpanExporter) -> None:
    cassette = load_cassette("simple_text_response")
    transport = ReplayTransport(cassette)

    messages = []
    async for msg in query(
        prompt="What is 2+2?",
        options=ClaudeAgentOptions(),
        transport=transport,
    ):
        messages.append(msg)

    assert any(isinstance(m, AssistantMessage) for m in messages)
    assert any(isinstance(m, ResultMessage) for m in messages)

    invoke_agent = _invoke_agent_span(otel_spans)
    assert invoke_agent.name == "invoke_agent ClaudeAgentSDK.query"

    attrs = invoke_agent.attributes
    assert attrs["gen_ai.operation.name"] == "invoke_agent"
    assert attrs["gen_ai.provider.name"] == "anthropic"
    assert attrs["gen_ai.agent.name"] == "ClaudeAgentSDK"
    assert attrs["gen_ai.request.model"] == "claude-sonnet-4-6"
    assert attrs["gen_ai.usage.input_tokens"] == 25
    assert attrs["gen_ai.usage.output_tokens"] == 10
    assert attrs["gen_ai.conversation.id"] == "s-abc123"
    assert attrs["gen_ai.response.id"] == "s-abc123"
    assert attrs["weave.claude_agent_sdk.total_cost_usd"] == pytest.approx(0.003)
    assert attrs["weave.claude_agent_sdk.result"] == "The answer is 4."

    input_msgs = json.loads(attrs["gen_ai.input.messages"])
    assert input_msgs == [
        {"role": "user", "parts": [{"type": "text", "content": "What is 2+2?"}]}
    ]

    output_msgs = json.loads(attrs["gen_ai.output.messages"])
    assert len(output_msgs) == 1
    assert output_msgs[0]["role"] == "assistant"
    text_parts = [p for p in output_msgs[0]["parts"] if p.get("type") == "text"]
    assert text_parts == [{"type": "text", "content": "The answer is 4."}]

    # No tool spans for the plain-text path.
    assert _tool_spans(otel_spans) == []

    # The outer conversation span is the trace root; the invoke_agent
    # nests under it and conversation_id propagates to both.
    conv = _conversation_span(otel_spans)
    assert conv.name == "ClaudeAgentSDK Conversation"
    assert conv.attributes["gen_ai.conversation.id"] == "s-abc123"
    assert invoke_agent.parent.span_id == conv.context.span_id


# =====================================================================
# query() — tool use produces an execute_tool child span
# =====================================================================


@pytest.mark.asyncio
async def test_tool_use_query(otel_spans: InMemorySpanExporter) -> None:
    cassette = load_cassette("tool_use_response")
    transport = ReplayTransport(cassette)

    async for _ in query(
        prompt="List files in the current directory",
        options=ClaudeAgentOptions(),
        transport=transport,
    ):
        pass

    invoke_agent = _invoke_agent_span(otel_spans)
    tools = _tool_spans(otel_spans)
    assert len(tools) == 1

    tool = tools[0]
    assert tool.name == "execute_tool Bash"
    assert tool.parent.span_id == invoke_agent.context.span_id

    attrs = tool.attributes
    assert attrs["gen_ai.operation.name"] == "execute_tool"
    assert attrs["gen_ai.tool.name"] == "Bash"
    assert attrs["gen_ai.tool.call.id"] == "toolu_01ABC"
    # arguments are JSON-encoded per semconv
    args = json.loads(attrs["gen_ai.tool.call.arguments"])
    assert args == {"command": "ls -la"}
    assert attrs["gen_ai.tool.call.result"] == "file1.py\nfile2.py\nREADME.md"

    # Output messages on the invoke_agent include the tool_use block.
    output_msgs = json.loads(invoke_agent.attributes["gen_ai.output.messages"])
    tool_call_parts = [
        p
        for msg in output_msgs
        for p in msg["parts"]
        if p.get("type") == "tool_call"
    ]
    assert len(tool_call_parts) == 1
    assert tool_call_parts[0]["name"] == "Bash"
    assert tool_call_parts[0]["id"] == "toolu_01ABC"


# =====================================================================
# query() — multiple tool uses in one message
# =====================================================================


@pytest.mark.asyncio
async def test_multi_tool_query(otel_spans: InMemorySpanExporter) -> None:
    cassette = load_cassette("multi_tool_response")
    transport = ReplayTransport(cassette)

    async for _ in query(
        prompt="Check files and directory",
        options=ClaudeAgentOptions(),
        transport=transport,
    ):
        pass

    invoke_agent = _invoke_agent_span(otel_spans)
    tools = _tool_spans(otel_spans)
    assert len(tools) == 2

    names = {t.name for t in tools}
    assert names == {"execute_tool Read", "execute_tool Bash"}

    for tool in tools:
        assert tool.parent.span_id == invoke_agent.context.span_id


# =====================================================================
# query() — error response
# =====================================================================


@pytest.mark.asyncio
async def test_error_query(otel_spans: InMemorySpanExporter) -> None:
    cassette = load_cassette("error_response")
    transport = ReplayTransport(cassette)

    messages = []
    async for msg in query(
        prompt="This will fail",
        options=ClaudeAgentOptions(),
        transport=transport,
    ):
        messages.append(msg)

    result_msg = next(m for m in messages if isinstance(m, ResultMessage))
    assert result_msg.is_error is True

    # The cassette flags is_error on the result message; we still
    # successfully iterate without raising. The span ends OK because
    # no python exception bubbled up — error semantics are carried
    # through ``is_error`` in the cassette, not via raising.
    # (Status enrichment for is_error result messages is a future task.)
    invoke_agent = _invoke_agent_span(otel_spans)
    assert invoke_agent.attributes["gen_ai.usage.input_tokens"] == 20


# =====================================================================
# ClaudeSDKClient — multi-turn conversation
# =====================================================================


@pytest.mark.asyncio
async def test_multi_turn_client(otel_spans: InMemorySpanExporter) -> None:
    cassette = load_cassette("multi_turn_response")
    transport = ReplayTransport(cassette)

    sdk_client = ClaudeSDKClient(
        options=ClaudeAgentOptions(),
        transport=transport,
    )

    await sdk_client.connect()

    # Turn 1
    await sdk_client.query(prompt="Hello")
    turn1: list = []
    async for msg in sdk_client.receive_response():
        turn1.append(msg)
        if isinstance(msg, ResultMessage):
            break

    # Turn 2
    await sdk_client.query(prompt="What is the capital of France?")
    turn2: list = []
    async for msg in sdk_client.receive_response():
        turn2.append(msg)
        if isinstance(msg, ResultMessage):
            break

    await sdk_client.disconnect()

    # Two roots — one per receive_response() invocation.
    roots = [
        s
        for s in otel_spans.get_finished_spans()
        if s.attributes.get("gen_ai.operation.name") == "invoke_agent"
        and s.parent is None
    ]
    assert len(roots) == 2

    # Each turn carries its own prompt in input.messages.
    in1 = json.loads(roots[0].attributes["gen_ai.input.messages"])
    in2 = json.loads(roots[1].attributes["gen_ai.input.messages"])
    assert in1[0]["parts"][0]["content"] == "Hello"
    assert in2[0]["parts"][0]["content"] == "What is the capital of France?"
