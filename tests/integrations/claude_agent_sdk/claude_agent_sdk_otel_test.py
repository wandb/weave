"""Tests for the OTel variant of the Claude Agent SDK integration.

Sibling of ``claude_agent_sdk_test.py`` — same replay cassettes and flows,
but asserts on emitted OTel GenAI spans instead of Weave calls. The Claude
Agent SDK talks over a subprocess transport, so messages are replayed via
``ReplayTransport`` exactly as in the calls-based test.
"""

from __future__ import annotations

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
from weave.integrations.claude_agent_sdk.otel_integration import (
    get_claude_agent_sdk_otel_patcher,
)

_ISOLATED_ENV = "WEAVE_CLAUDE_AGENT_SDK_ISOLATED_TRACES"


@pytest.fixture
def otel_spans(monkeypatch: pytest.MonkeyPatch) -> Generator[InMemorySpanExporter]:
    """Install an in-memory OTel exporter as the global provider.

    Mirrors the session-SDK / openai_agents_otel fixture: overrides the
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


def _attrs(span: Any) -> dict[str, Any]:
    return dict(span.attributes) if span.attributes is not None else {}


def _by_op(spans: list[Any], op: str) -> list[Any]:
    return [s for s in spans if _attrs(s).get("gen_ai.operation.name") == op]


def _messages(span: Any, key: str) -> list[dict[str, Any]]:
    raw = _attrs(span).get(key)
    return json.loads(raw) if raw else []


def _all_text(messages: list[dict[str, Any]]) -> str:
    return " ".join(
        p.get("content", "")
        for m in messages
        for p in m.get("parts", [])
        if p.get("type") == "text"
    )


def _part_types(messages: list[dict[str, Any]]) -> set[str]:
    return {p.get("type") for m in messages for p in m.get("parts", [])}


async def _drain_query(cassette: str, prompt: str) -> None:
    async for _ in query(
        prompt=prompt,
        options=ClaudeAgentOptions(),
        transport=ReplayTransport(load_cassette(cassette)),
    ):
        pass


# --- query(): simple text ---------------------------------------------------


@pytest.mark.asyncio
async def test_simple_text_query_otel(otel_spans: InMemorySpanExporter) -> None:
    await _drain_query("simple_text_response", "What is 2+2?")
    spans = otel_spans.get_finished_spans()

    agent = _by_op(spans, "invoke_agent")
    chats = _by_op(spans, "chat")
    assert len(agent) == 1
    assert len(chats) == 1

    agent_span = agent[0]
    a = _attrs(agent_span)
    assert agent_span.name == "invoke_agent claude_agent_sdk"
    assert a["gen_ai.agent.name"] == "claude_agent_sdk"
    assert a["gen_ai.provider.name"] == "anthropic"
    assert a["gen_ai.conversation.id"] == "s-abc123"
    assert a["weave.claude_agent_sdk.cost.total_usd"] == 0.003
    assert a["weave.claude_agent_sdk.num_turns"] == 1
    assert "What is 2+2?" in _all_text(_messages(agent_span, "gen_ai.input.messages"))
    assert "The answer is 4." in _all_text(
        _messages(agent_span, "gen_ai.output.messages")
    )

    chat = chats[0]
    c = _attrs(chat)
    assert c["gen_ai.request.model"] == "claude-sonnet-4-6"
    assert c["gen_ai.conversation.id"] == "s-abc123"
    assert c["gen_ai.usage.input_tokens"] == 25
    assert c["gen_ai.usage.output_tokens"] == 10
    # chat nests under the invoke_agent root
    assert chat.parent.span_id == agent_span.context.span_id


# --- query(): tool use ------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_use_query_otel(otel_spans: InMemorySpanExporter) -> None:
    await _drain_query("tool_use_response", "List files in the current directory")
    spans = otel_spans.get_finished_spans()

    agent = _by_op(spans, "invoke_agent")[0]
    chats = _by_op(spans, "chat")
    tools = _by_op(spans, "execute_tool")
    assert len(chats) == 2
    assert len(tools) == 1

    tool = tools[0]
    t = _attrs(tool)
    assert tool.name == "execute_tool Bash"
    assert t["gen_ai.tool.name"] == "Bash"
    assert t["gen_ai.tool.call.id"] == "toolu_01ABC"
    assert "file1.py" in t["gen_ai.tool.call.result"]
    assert tool.parent.span_id == agent.context.span_id

    # Aggregate usage lands on exactly one (the final) chat span.
    with_usage = [c for c in chats if "gen_ai.usage.input_tokens" in _attrs(c)]
    assert len(with_usage) == 1
    assert _attrs(with_usage[0])["gen_ai.usage.input_tokens"] == 150
    assert _attrs(with_usage[0])["gen_ai.usage.output_tokens"] == 75

    # The first chat (the one requesting the tool) carries a tool_call part.
    tool_call_chat = [
        c
        for c in chats
        if "tool_call" in _part_types(_messages(c, "gen_ai.output.messages"))
    ]
    assert len(tool_call_chat) == 1
    assert _attrs(agent)["weave.claude_agent_sdk.cost.total_usd"] == 0.008


# --- query(): multiple tools in one response --------------------------------


@pytest.mark.asyncio
async def test_multi_tool_query_otel(otel_spans: InMemorySpanExporter) -> None:
    await _drain_query("multi_tool_response", "Check both files")
    spans = otel_spans.get_finished_spans()

    agent = _by_op(spans, "invoke_agent")[0]
    tools = _by_op(spans, "execute_tool")
    assert {t.name for t in tools} == {"execute_tool Read", "execute_tool Bash"}
    for t in tools:
        assert t.parent.span_id == agent.context.span_id

    results = {
        _attrs(t)["gen_ai.tool.name"]: _attrs(t)["gen_ai.tool.call.result"]
        for t in tools
    }
    assert "print('hello')" in results["Read"]
    assert "/tmp" in results["Bash"]


# --- query(): thinking folds into one chat span -----------------------------


@pytest.mark.asyncio
async def test_thinking_query_otel(otel_spans: InMemorySpanExporter) -> None:
    await _drain_query("thinking_response", "Think about it")
    spans = otel_spans.get_finished_spans()

    # Thinking-only messages are buffered into the following response, so the
    # extended-thinking turn produces a single chat span, not two.
    chats = _by_op(spans, "chat")
    assert len(chats) == 1

    out = _messages(chats[0], "gen_ai.output.messages")
    assert "reasoning" in _part_types(out)
    reasoning_text = " ".join(
        p.get("content", "")
        for m in out
        for p in m.get("parts", [])
        if p.get("type") == "reasoning"
    )
    assert "Let me think about this carefully" in reasoning_text
    assert "the answer is 42" in _all_text(out)


# --- query(): error result sets span status ---------------------------------


@pytest.mark.asyncio
async def test_error_response_otel(otel_spans: InMemorySpanExporter) -> None:
    await _drain_query("error_response", "Do something")
    spans = otel_spans.get_finished_spans()

    agent = _by_op(spans, "invoke_agent")[0]
    assert agent.status.status_code == StatusCode.ERROR


# --- trace isolation: ambient (default) vs isolated -------------------------


@pytest.mark.asyncio
async def test_ambient_trace_nesting_otel(otel_spans: InMemorySpanExporter) -> None:
    """By default a turn nests under whatever OTel span is already active."""
    tracer = otel_trace.get_tracer("test.app")
    with tracer.start_as_current_span("app.request") as outer:
        outer_ctx = outer.get_span_context()
        await _drain_query("simple_text_response", "What is 2+2?")

    spans = otel_spans.get_finished_spans()
    agent = _by_op(spans, "invoke_agent")[0]
    assert agent.parent is not None
    assert agent.parent.span_id == outer_ctx.span_id
    assert agent.context.trace_id == outer_ctx.trace_id


@pytest.mark.asyncio
async def test_isolated_trace_mode_otel(
    otel_spans: InMemorySpanExporter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the isolated-traces env set, a turn ignores the ambient span."""
    monkeypatch.setenv(_ISOLATED_ENV, "1")
    tracer = otel_trace.get_tracer("test.app")
    with tracer.start_as_current_span("app.request") as outer:
        outer_ctx = outer.get_span_context()
        await _drain_query("simple_text_response", "What is 2+2?")

    spans = otel_spans.get_finished_spans()
    agent = _by_op(spans, "invoke_agent")[0]
    assert agent.parent is None
    assert agent.context.trace_id != outer_ctx.trace_id


# --- ClaudeSDKClient: multi-turn --------------------------------------------


@pytest.mark.asyncio
async def test_multi_turn_client_otel(otel_spans: InMemorySpanExporter) -> None:
    sdk_client = ClaudeSDKClient(
        options=ClaudeAgentOptions(),
        transport=ReplayTransport(load_cassette("multi_turn_response")),
    )
    await sdk_client.connect()

    await sdk_client.query("Hello")
    _ = [m async for m in sdk_client.receive_response()]
    await sdk_client.query("What is the capital of France?")
    _ = [m async for m in sdk_client.receive_response()]

    await sdk_client.disconnect()

    spans = otel_spans.get_finished_spans()
    agents = _by_op(spans, "invoke_agent")
    assert len(agents) == 2

    # Both turns share one conversation id (the SDK session_id)...
    assert {_attrs(a)["gen_ai.conversation.id"] for a in agents} == {"s-mt001"}
    # ...but each turn is its own trace (no ambient span held across turns).
    assert len({a.context.trace_id for a in agents}) == 2

    prompts = {_all_text(_messages(a, "gen_ai.input.messages")) for a in agents}
    assert prompts == {"Hello", "What is the capital of France?"}
