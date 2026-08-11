"""Tests for the OTel variant of the OpenAI Agents tracing processor.

Sibling of ``openai_agents_test.py`` — same trigger flows (Agent runs via
recorded cassettes, mock-driven processor unit checks), but asserts on
emitted OTel spans instead of Weave calls.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Generator
from typing import Any
from unittest.mock import Mock

import httpx
import pytest
from agents import Agent, Runner
from agents.models.openai_responses import OpenAIResponsesModel
from agents.tracing import (
    AgentSpanData,
    CustomSpanData,
    FunctionSpanData,
    GenerationSpanData,
    GuardrailSpanData,
    HandoffSpanData,
    ResponseSpanData,
    Span,
    TaskSpanData,
    Trace,
    TurnSpanData,
    generation_span,
    get_trace_provider,
    response_span,
    set_trace_processors,
    set_trace_provider,
    trace,
)
from agents.tracing.provider import DefaultTraceProvider
from openai import AsyncOpenAI
from opentelemetry import context as otel_context
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import Decision, StaticSampler

from weave.conversation import agent_name_override
from weave.integrations.integration_utilities import op_name_from_ref
from weave.integrations.openai.openai_sdk import get_openai_patcher
from weave.integrations.openai_agents.otel_processor import (
    WeaveOtelTracingProcessor,
    _iso_to_ns,
)
from weave.trace.weave_client import WeaveClient


@pytest.fixture
def otel_spans(monkeypatch: pytest.MonkeyPatch):
    """Install an in-memory OTel exporter and return it for assertions.

    Mirrors the fixture in ``tests/conversation/test_conversation_otel.py`` — overrides
    the global tracer provider via ``monkeypatch.setattr`` so prior state is
    restored cleanly between tests.
    """
    exporter = InMemorySpanExporter()
    provider = SDKTracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER", provider)
    yield exporter
    provider.shutdown()


@pytest.fixture
def setup_tests() -> Generator[WeaveOtelTracingProcessor, None, None]:
    """Install exactly one OTel processor and restore the Agents provider."""
    original_provider = get_trace_provider()
    set_trace_provider(DefaultTraceProvider())
    processor = WeaveOtelTracingProcessor()
    set_trace_processors([processor])
    try:
        yield processor
    finally:
        processor.shutdown()
        set_trace_provider(original_provider)


@pytest.fixture
def patched_openai() -> Generator[None, None, None]:
    patcher = get_openai_patcher()
    patcher.attempt_patch()
    yield
    # MultiPatcher stops undoing after its first unsuccessful child.
    for symbol_patcher in patcher.patchers:
        symbol_patcher.undo_patch()


# 5 spans gives ~0.8% chance (1/120) of a random set-iteration happening to
# match reverse-insertion by accident — low enough to make the LIFO regression
# checks reliable across PYTHONHASHSEED runs. count=3 would let the bug slip
# through ~17% of the time (1/6).
_LIFO_TEST_SPAN_COUNT = 5


def _record_detach_calls(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Wrap ``otel_context.detach`` so the test can assert call order; returns the list."""
    calls: list[Any] = []
    original = otel_context.detach

    def recording_detach(token: Any) -> None:
        calls.append(token)
        return original(token)

    monkeypatch.setattr(
        "weave.integrations.openai_agents.otel_processor.otel_context.detach",
        recording_detach,
    )
    return calls


def _make_processor_with_open_span_chain() -> tuple[WeaveOtelTracingProcessor, Any]:
    """Build a processor + trace with N open spans already attached.

    Each ``on_span_start`` attaches a fresh OTel context token; the resulting
    stack is ``_LIFO_TEST_SPAN_COUNT`` levels deep with the last span current —
    the precondition for LIFO-detach assertions. ``on_span_end`` is NOT called,
    so the spans remain "leftover" for whichever cleanup path the test drives.
    """
    processor = WeaveOtelTracingProcessor()
    trace = Mock(spec=Trace)
    trace.trace_id = "trace_lifo"
    trace.name = "wf"
    trace.group_id = None
    processor.on_trace_start(trace)

    last_span_id: str | None = None
    for i in range(_LIFO_TEST_SPAN_COUNT):
        s = Mock(spec=Span)
        s.trace_id = "trace_lifo"
        s.span_id = f"span_{i:02d}"
        s.parent_id = last_span_id
        s.span_data = AgentSpanData(name=f"Agent{i}")
        s.started_at = None
        s.ended_at = None
        s.error = None
        processor.on_span_start(s)
        last_span_id = s.span_id

    return processor, trace


def _attrs(span: Any) -> dict[str, Any]:
    """Return span attributes as a plain dict."""
    return dict(span.attributes) if span.attributes is not None else {}


def _by_name(spans: list[Any], prefix: str) -> list[Any]:
    return [s for s in spans if s.name.startswith(prefix)]


def _response_payload(response_id: str, text: str) -> dict[str, Any]:
    return {
        "id": response_id,
        "object": "response",
        "created_at": 1,
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "instructions": "You are a helpful assistant",
        "max_output_tokens": None,
        "model": "gpt-4o-2024-08-06",
        "output": [
            {
                "type": "message",
                "id": f"msg_{response_id}",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
        "parallel_tool_calls": True,
        "previous_response_id": None,
        "reasoning": {"effort": None, "generate_summary": None},
        "store": True,
        "temperature": 1.0,
        "text": {"format": {"type": "text"}},
        "tool_choice": "auto",
        "tools": [],
        "top_p": 1.0,
        "truncation": "disabled",
        "usage": {
            "input_tokens": 4,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 2,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 6,
        },
        "user": None,
        "metadata": {},
    }


def _chat_completion_payload(response_id: str) -> dict[str, Any]:
    return {
        "id": response_id,
        "object": "chat.completion",
        "created": 1,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hi"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 2,
            "completion_tokens": 1,
            "total_tokens": 3,
        },
    }


def _mock_transport(
    *payloads: dict[str, Any],
) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    remaining = iter(payloads)
    requests: list[httpx.Request] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=next(remaining))

    return httpx.MockTransport(handle), requests


def _calls_named(client: WeaveClient, name: str) -> list[Any]:
    return [
        call for call in client.get_calls() if op_name_from_ref(call.op_name) == name
    ]


@pytest.mark.vcr(
    filter_headers=["authorization"],
)
def test_openai_agents_quickstart_otel(
    client: WeaveClient, setup_tests, otel_spans: InMemorySpanExporter
) -> None:
    agent = Agent(name="Assistant", instructions="You are a helpful assistant")

    Runner.run_sync(agent, "Write a haiku about recursion in programming.")

    spans = otel_spans.get_finished_spans()
    # Integration-tracking metadata is stamped (flattened) on every emitted span.
    stamped = [_attrs(s) for s in spans if "integration.name" in _attrs(s)]
    assert stamped, "expected >=1 span to carry integration metadata"
    assert all(a["integration.name"] == "openai_agents" for a in stamped)
    assert all(a["integration.meta.package_name"] == "openai-agents" for a in stamped)
    by_name = {s.name: s for s in spans}

    # No synthetic trace root: TaskSpan is the OTel root, named "workflow ..."
    # so the Agents-tab events panel doesn't treat it as a sub-agent.
    workflow = by_name["workflow Agent workflow"]
    workflow_attrs = _attrs(workflow)
    assert workflow.parent is None
    assert "gen_ai.operation.name" not in workflow_attrs
    assert workflow_attrs["weave.openai_agents.task.workflow_name"] == "Agent workflow"
    assert workflow_attrs["gen_ai.conversation.id"].startswith("trace_")

    # AgentSpan is the only invoke_agent — TaskSpan and TurnSpan are structural,
    # so handoff/multi-agent flows show one agent_start event per agent only.
    invoke_agent_spans = [
        s for s in spans if _attrs(s).get("gen_ai.operation.name") == "invoke_agent"
    ]
    assert len(invoke_agent_spans) == 1
    agent_span = invoke_agent_spans[0]
    assert agent_span.name == "invoke_agent Assistant"
    assert _attrs(agent_span)["gen_ai.agent.name"] == "Assistant"
    assert agent_span.parent.span_id == workflow.context.span_id

    # TurnSpan is structural — name has no invoke_agent prefix, no semconv op.
    turn_spans = [s for s in spans if "turn " in s.name and s.name != agent_span.name]
    assert turn_spans
    for turn in turn_spans:
        turn_attrs = _attrs(turn)
        assert "gen_ai.operation.name" not in turn_attrs
        assert turn_attrs["weave.openai_agents.turn.agent_name"] == "Assistant"
        assert turn.parent.span_id == agent_span.context.span_id

    # At least one chat span lifted from ResponseSpanData, nested under a turn.
    chat_spans = _by_name(spans, "chat ")
    assert chat_spans, "expected at least one chat span"
    chat = chat_spans[0]
    assert chat.parent.span_id == turn_spans[0].context.span_id
    chat_attrs = _attrs(chat)
    assert chat_attrs["gen_ai.operation.name"] == "chat"
    assert chat_attrs["gen_ai.provider.name"] == "openai"


def test_agent_span_carries_provider_name(
    client: WeaveClient, otel_spans: InMemorySpanExporter
) -> None:
    """AgentSpan sets ``gen_ai.provider.name`` so the Agents tab can filter by provider."""
    processor = WeaveOtelTracingProcessor()
    trace = Mock(spec=Trace)
    trace.trace_id = "trace_p"
    trace.name = "wf"
    trace.group_id = None
    processor.on_trace_start(trace)

    agent_span = Mock(spec=Span)
    agent_span.trace_id = "trace_p"
    agent_span.span_id = "span_p"
    agent_span.parent_id = None
    agent_span.span_data = AgentSpanData(name="Bot")
    agent_span.started_at = None
    agent_span.ended_at = None
    agent_span.error = None
    processor.on_span_start(agent_span)
    processor.on_span_end(agent_span)
    processor.on_trace_end(trace)

    spans = otel_spans.get_finished_spans()
    agent = next(s for s in spans if s.name == "invoke_agent Bot")
    assert _attrs(agent)["gen_ai.provider.name"] == "openai"


def test_agent_name_override_wins_over_native(
    client: WeaveClient, otel_spans: InMemorySpanExporter
) -> None:
    """An explicit override replaces the SDK-native agent name on the span."""
    processor = WeaveOtelTracingProcessor()
    trace = Mock(spec=Trace)
    trace.trace_id = "trace_o"
    trace.name = "wf"
    trace.group_id = None

    agent_span = Mock(spec=Span)
    agent_span.trace_id = "trace_o"
    agent_span.span_id = "span_o"
    agent_span.parent_id = None
    agent_span.span_data = AgentSpanData(name="Bot")
    agent_span.started_at = None
    agent_span.ended_at = None
    agent_span.error = None

    # The name is resolved at span start/end, so the override must be active then.
    with agent_name_override("research_agent"):
        processor.on_trace_start(trace)
        processor.on_span_start(agent_span)
        processor.on_span_end(agent_span)
        processor.on_trace_end(trace)

    spans = otel_spans.get_finished_spans()
    agent = next(
        s for s in spans if _attrs(s).get("gen_ai.operation.name") == "invoke_agent"
    )
    assert agent.name == "invoke_agent research_agent"
    assert _attrs(agent)["gen_ai.agent.name"] == "research_agent"


def test_response_span_emits_chat_with_messages(
    client: WeaveClient, otel_spans: InMemorySpanExporter
) -> None:
    """ResponseSpan is lifted into a ``chat`` semconv span.

    Pulls model, response id, input/output messages, usage, finish_reasons,
    and output_type directly off ``ResponseSpanData`` — the Agents SDK already
    serializes the openai Response on the span.
    """
    processor = WeaveOtelTracingProcessor()

    trace = Mock(spec=Trace)
    trace.trace_id = "trace_r"
    trace.name = "wf"
    trace.group_id = None
    processor.on_trace_start(trace)

    output_item = Mock()
    output_item.model_dump.return_value = {
        "role": "assistant",
        "content": [{"type": "output_text", "text": "Hi!"}],
        "finish_reason": "stop",
    }
    response = Mock()
    response.id = "resp_42"
    response.model = "gpt-4o"
    response.output = [output_item]
    usage = Mock()
    usage.input_tokens = 5
    usage.output_tokens = 7
    usage.output_tokens_details = None
    usage.input_tokens_details = None
    response.usage = usage

    response_data = Mock(spec=ResponseSpanData)
    response_data.__class__ = ResponseSpanData
    response_data.input = "Say hi"
    response_data.response = response
    response_data.usage = None

    response_span = Mock(spec=Span)
    response_span.trace_id = "trace_r"
    response_span.span_id = "span_resp"
    response_span.parent_id = None
    response_span.span_data = response_data
    response_span.started_at = None
    response_span.ended_at = None
    response_span.error = None
    processor.on_span_start(response_span)
    processor.on_span_end(response_span)
    processor.on_trace_end(trace)

    spans = otel_spans.get_finished_spans()
    chat = next(s for s in spans if s.name == "chat gpt-4o")
    attrs = _attrs(chat)
    assert attrs["gen_ai.operation.name"] == "chat"
    assert attrs["gen_ai.request.model"] == "gpt-4o"
    assert attrs["gen_ai.response.id"] == "resp_42"
    assert attrs["gen_ai.response.model"] == "gpt-4o"
    assert attrs["gen_ai.usage.input_tokens"] == 5
    assert attrs["gen_ai.usage.output_tokens"] == 7
    assert attrs["gen_ai.response.finish_reasons"] == ("stop",)
    assert attrs["gen_ai.output.type"] == "text"

    input_messages = json.loads(attrs["gen_ai.input.messages"])
    assert input_messages == [
        {"role": "user", "parts": [{"type": "text", "content": "Say hi"}]}
    ]
    output_messages = json.loads(attrs["gen_ai.output.messages"])
    assert output_messages == [
        {
            "role": "assistant",
            "parts": [{"type": "text", "content": "Hi!"}],
            "finish_reason": "stop",
        }
    ]


def test_generation_span_emits_chat_with_messages(
    client: WeaveClient, otel_spans: InMemorySpanExporter
) -> None:
    """GenerationSpan is lifted into a ``chat`` semconv span.

    The legacy chat-completions shape uses flat ``[{role, content}]`` messages,
    plain string content, and a ``prompt_tokens``/``completion_tokens`` usage
    dict.
    """
    processor = WeaveOtelTracingProcessor()

    trace = Mock(spec=Trace)
    trace.trace_id = "trace_g"
    trace.name = "wf"
    trace.group_id = None
    processor.on_trace_start(trace)

    gen_span = Mock(spec=Span)
    gen_span.trace_id = "trace_g"
    gen_span.span_id = "span_gen"
    gen_span.parent_id = None
    gen_span.span_data = GenerationSpanData(
        input=[{"role": "user", "content": "Say hi"}],
        output=[{"role": "assistant", "content": "Hi!"}],
        model="gpt-4o",
        usage={"input_tokens": 5, "output_tokens": 7},
    )
    gen_span.started_at = None
    gen_span.ended_at = None
    gen_span.error = None
    processor.on_span_start(gen_span)
    processor.on_span_end(gen_span)
    processor.on_trace_end(trace)

    spans = otel_spans.get_finished_spans()
    chat = next(s for s in spans if s.name == "chat gpt-4o")
    attrs = _attrs(chat)
    assert attrs["gen_ai.operation.name"] == "chat"
    assert attrs["gen_ai.request.model"] == "gpt-4o"
    assert attrs["gen_ai.usage.input_tokens"] == 5
    assert attrs["gen_ai.usage.output_tokens"] == 7

    input_messages = json.loads(attrs["gen_ai.input.messages"])
    assert input_messages == [
        {"role": "user", "parts": [{"type": "text", "content": "Say hi"}]}
    ]
    output_messages = json.loads(attrs["gen_ai.output.messages"])
    assert output_messages == [
        {"role": "assistant", "parts": [{"type": "text", "content": "Hi!"}]}
    ]


def test_handoff_emits_custom_attrs(
    client: WeaveClient, otel_spans: InMemorySpanExporter
) -> None:
    processor = WeaveOtelTracingProcessor()

    trace = Mock(spec=Trace)
    trace.trace_id = "trace_handoff"
    trace.name = "wf"
    trace.group_id = None
    processor.on_trace_start(trace)

    handoff_data = HandoffSpanData(from_agent="Triage", to_agent="History")
    handoff_span = Mock(spec=Span)
    handoff_span.trace_id = "trace_handoff"
    handoff_span.span_id = "span_handoff"
    handoff_span.parent_id = None
    handoff_span.span_data = handoff_data
    handoff_span.started_at = None
    handoff_span.ended_at = None
    handoff_span.error = None
    processor.on_span_start(handoff_span)
    processor.on_span_end(handoff_span)

    processor.on_trace_end(trace)

    spans = otel_spans.get_finished_spans()
    handoff = next(s for s in spans if s.name == "handoff Triage -> History")
    attrs = _attrs(handoff)
    assert attrs["weave.openai_agents.handoff.from_agent"] == "Triage"
    assert attrs["weave.openai_agents.handoff.to_agent"] == "History"
    # No gen_ai.operation.name — handoff has no semconv mapping.
    assert "gen_ai.operation.name" not in attrs


def test_guardrail_emits_custom_attrs(
    client: WeaveClient, otel_spans: InMemorySpanExporter
) -> None:
    processor = WeaveOtelTracingProcessor()

    trace = Mock(spec=Trace)
    trace.trace_id = "trace_guard"
    trace.name = "wf"
    trace.group_id = None
    processor.on_trace_start(trace)

    guardrail_data = GuardrailSpanData(name="homework", triggered=True)
    guardrail_span = Mock(spec=Span)
    guardrail_span.trace_id = "trace_guard"
    guardrail_span.span_id = "span_guard"
    guardrail_span.parent_id = None
    guardrail_span.span_data = guardrail_data
    guardrail_span.started_at = None
    guardrail_span.ended_at = None
    guardrail_span.error = None
    processor.on_span_start(guardrail_span)
    processor.on_span_end(guardrail_span)

    processor.on_trace_end(trace)

    spans = otel_spans.get_finished_spans()
    guardrail = next(s for s in spans if s.name == "guardrail homework")
    attrs = _attrs(guardrail)
    assert attrs["weave.openai_agents.guardrail.name"] == "homework"
    assert attrs["weave.openai_agents.guardrail.triggered"] is True


def test_function_emits_execute_tool(
    client: WeaveClient, otel_spans: InMemorySpanExporter
) -> None:
    processor = WeaveOtelTracingProcessor()

    trace = Mock(spec=Trace)
    trace.trace_id = "trace_fn"
    trace.name = "wf"
    trace.group_id = None
    processor.on_trace_start(trace)

    fn_data = FunctionSpanData(
        name="get_weather", input='{"city": "Paris"}', output='{"temp": 17}'
    )
    fn_span = Mock(spec=Span)
    fn_span.trace_id = "trace_fn"
    fn_span.span_id = "span_fn"
    fn_span.parent_id = None
    fn_span.span_data = fn_data
    fn_span.started_at = None
    fn_span.ended_at = None
    fn_span.error = None
    processor.on_span_start(fn_span)
    processor.on_span_end(fn_span)

    processor.on_trace_end(trace)

    spans = otel_spans.get_finished_spans()
    tool_span = next(s for s in spans if s.name == "execute_tool get_weather")
    attrs = _attrs(tool_span)
    assert attrs["gen_ai.operation.name"] == "execute_tool"
    assert attrs["gen_ai.tool.name"] == "get_weather"
    assert attrs["gen_ai.tool.call.arguments"] == '{"city": "Paris"}'
    assert attrs["gen_ai.tool.call.result"] == '{"temp": 17}'


def test_conversation_id_uses_group_id_when_set(
    client: WeaveClient, otel_spans: InMemorySpanExporter
) -> None:
    """``group_id`` (when set) becomes ``gen_ai.conversation.id``; otherwise trace_id.

    The conversation_id is propagated onto every emitted child span (the trace
    object itself emits no span — TaskSpan is the natural root).
    """
    processor = WeaveOtelTracingProcessor()

    def _emit_task(trace_id: str, group_id: str | None) -> None:
        trace = Mock(spec=Trace)
        trace.trace_id = trace_id
        trace.name = "wf"
        trace.group_id = group_id
        processor.on_trace_start(trace)

        task_span = Mock(spec=Span)
        task_span.trace_id = trace_id
        task_span.span_id = f"task_{trace_id}"
        task_span.parent_id = None
        task_span.span_data = TaskSpanData(name="wf")
        task_span.started_at = None
        task_span.ended_at = None
        task_span.error = None
        processor.on_span_start(task_span)
        processor.on_span_end(task_span)
        processor.on_trace_end(trace)

    _emit_task("trace_1", "chat_456")
    _emit_task("trace_2", None)

    by_trace_attr = {
        _attrs(s)["weave.openai_agents.trace_id"]: _attrs(s)
        for s in otel_spans.get_finished_spans()
    }
    assert by_trace_attr["trace_1"]["gen_ai.conversation.id"] == "chat_456"
    assert by_trace_attr["trace_2"]["gen_ai.conversation.id"] == "trace_2"
    # TaskSpan is structural — no invoke_agent semconv on it.
    assert "gen_ai.operation.name" not in by_trace_attr["trace_1"]
    assert "gen_ai.operation.name" not in by_trace_attr["trace_2"]


def test_task_and_turn_emit_structural_spans(
    client: WeaveClient, otel_spans: InMemorySpanExporter
) -> None:
    """Task/Turn spans are structural — no invoke_agent semconv on them.

    TaskSpan wraps a workflow (not an agent invocation) and TurnSpan is one
    loop iteration within an agent (not a separate agent), so emitting
    ``gen_ai.operation.name=invoke_agent`` on either would surface them as
    redundant "sub-agent" events in the Agents tab Events panel. They still
    emit OTel spans (queryable, parent-child trace tree, metadata preserved
    under ``weave.openai_agents.*``) — just not as semconv agent invocations.
    """
    processor = WeaveOtelTracingProcessor()

    trace = Mock(spec=Trace)
    trace.trace_id = "trace_tt"
    trace.name = "Agent workflow"
    trace.group_id = None
    processor.on_trace_start(trace)

    task_span = Mock(spec=Span)
    task_span.trace_id = trace.trace_id
    task_span.span_id = "task_1"
    task_span.parent_id = None
    task_span.span_data = TaskSpanData(
        name="Runner task",
        usage={"input_tokens": 0, "output_tokens": 5, "total_tokens": 5},
        metadata={"session_id": "session-1"},
    )
    task_span.started_at = None
    task_span.ended_at = None
    task_span.error = None
    processor.on_span_start(task_span)

    turn_span = Mock(spec=Span)
    turn_span.trace_id = trace.trace_id
    turn_span.span_id = "turn_1"
    turn_span.parent_id = task_span.span_id
    turn_span.span_data = TurnSpanData(
        turn=2,
        agent_name="Assistant",
        usage={"input_tokens": 7, "output_tokens": 11},
        metadata={"callback": "session_input"},
    )
    turn_span.started_at = None
    turn_span.ended_at = None
    turn_span.error = None
    processor.on_span_start(turn_span)

    processor.on_span_end(turn_span)
    processor.on_span_end(task_span)
    processor.on_trace_end(trace)

    spans = otel_spans.get_finished_spans()
    task = next(s for s in spans if s.name == "workflow Runner task")
    task_attrs = _attrs(task)
    assert "gen_ai.operation.name" not in task_attrs
    assert task_attrs["weave.openai_agents.task.workflow_name"] == "Runner task"
    assert task_attrs["weave.openai_agents.task.metadata.session_id"] == "session-1"

    turn = next(s for s in spans if s.name == "Assistant turn 2")
    turn_attrs = _attrs(turn)
    assert "gen_ai.operation.name" not in turn_attrs
    assert turn_attrs["weave.openai_agents.turn.agent_name"] == "Assistant"
    assert turn_attrs["weave.openai_agents.turn.number"] == 2
    assert turn_attrs["weave.openai_agents.turn.metadata.callback"] == "session_input"


def test_custom_span_data_passes_through(
    client: WeaveClient, otel_spans: InMemorySpanExporter
) -> None:
    processor = WeaveOtelTracingProcessor()

    trace = Mock(spec=Trace)
    trace.trace_id = "trace_cust"
    trace.name = "wf"
    trace.group_id = None
    processor.on_trace_start(trace)

    custom_data = CustomSpanData(
        name="my_custom",
        data={"key": "val", "n": 42},
    )
    custom_span = Mock(spec=Span)
    custom_span.trace_id = "trace_cust"
    custom_span.span_id = "span_cust"
    custom_span.parent_id = None
    custom_span.span_data = custom_data
    custom_span.started_at = None
    custom_span.ended_at = None
    custom_span.error = None
    processor.on_span_start(custom_span)
    processor.on_span_end(custom_span)

    processor.on_trace_end(trace)

    spans = otel_spans.get_finished_spans()
    custom = next(s for s in spans if s.name == "my_custom")
    attrs = _attrs(custom)
    assert attrs["weave.openai_agents.custom.key"] == "val"
    assert attrs["weave.openai_agents.custom.n"] == 42


def test_error_records_status_and_data(
    client: WeaveClient, otel_spans: InMemorySpanExporter
) -> None:
    """A span with an error records ERROR status and surfaces error.data attr."""
    from opentelemetry.trace import StatusCode

    processor = WeaveOtelTracingProcessor()

    trace = Mock(spec=Trace)
    trace.trace_id = "trace_err"
    trace.name = "wf"
    trace.group_id = None
    processor.on_trace_start(trace)

    agent_span = Mock(spec=Span)
    agent_span.trace_id = "trace_err"
    agent_span.span_id = "span_err"
    agent_span.parent_id = None
    agent_span.span_data = AgentSpanData(name="Bot")
    agent_span.started_at = None
    agent_span.ended_at = None
    agent_span.error = {"message": "boom", "data": {"code": 500}}
    processor.on_span_start(agent_span)
    processor.on_span_end(agent_span)

    processor.on_trace_end(trace)

    spans = otel_spans.get_finished_spans()
    errored = next(s for s in spans if s.name == "invoke_agent Bot")
    assert errored.status.status_code == StatusCode.ERROR
    assert errored.status.description == "boom"
    assert _attrs(errored)["weave.openai_agents.error.data"] == "{'code': 500}"


def test_processor_cleanup(
    client: WeaveClient, otel_spans: InMemorySpanExporter
) -> None:
    """Internal dicts are cleared on shutdown and force_flush."""
    processor = WeaveOtelTracingProcessor()

    trace = Mock(spec=Trace)
    trace.trace_id = "trace_x"
    trace.name = "wf"
    trace.group_id = None
    processor.on_trace_start(trace)
    assert "trace_x" in processor._conversation_ids

    agent_span = Mock(spec=Span)
    agent_span.trace_id = "trace_x"
    agent_span.span_id = "span_x"
    agent_span.parent_id = None
    agent_span.span_data = AgentSpanData(name="Bot")
    agent_span.started_at = None
    agent_span.ended_at = None
    agent_span.error = None
    processor.on_span_start(agent_span)
    assert "span_x" in processor._span_otel

    # force_flush ends any open spans and clears dicts.
    processor.force_flush()
    assert processor._span_otel == {}
    assert processor._span_tokens == {}
    assert processor._conversation_ids == {}

    # shutdown is idempotent when state is already empty.
    processor.shutdown()
    assert processor._span_otel == {}


def test_iso_to_ns_roundtrip() -> None:
    """``_iso_to_ns`` converts ISO 8601 strings to nanoseconds since epoch."""
    from datetime import datetime, timezone

    now = datetime(2026, 5, 20, 12, 30, 45, tzinfo=timezone.utc)
    iso = now.isoformat()
    ns = _iso_to_ns(iso)
    assert ns is not None
    assert ns == int(now.timestamp() * 1_000_000_000)
    assert _iso_to_ns(None) is None
    assert _iso_to_ns("") is None


def test_patcher_install_and_uninstall_lifecycle() -> None:
    """``attempt_patch`` adds the processor; ``undo_patch`` removes it cleanly.

    Verifies the uninstall path doesn't blow away other registered
    processors — we install a sentinel processor first, then install our
    patcher, then uninstall, and confirm the sentinel is still there.
    """
    from agents.tracing import TracingProcessor, set_trace_processors

    from weave.integrations.openai_agents.patcher import (
        OpenAIAgentsOtelPatcher,
        _registered_processors,
    )
    from weave.trace.autopatch import IntegrationSettings

    original = _registered_processors() or []

    class _Sentinel(TracingProcessor):
        def on_trace_start(self, trace):
            return None

        def on_trace_end(self, trace):
            return None

        def on_span_start(self, span):
            return None

        def on_span_end(self, span):
            return None

        def shutdown(self):
            return None

        def force_flush(self):
            return None

    sentinel = _Sentinel()
    set_trace_processors([sentinel])

    patcher = OpenAIAgentsOtelPatcher(IntegrationSettings())
    assert patcher.attempt_patch() is True
    installed_processor = patcher.processor
    assert installed_processor is not None

    registered = _registered_processors() or []
    assert sentinel in registered, "sentinel processor was clobbered on install"
    assert installed_processor in registered

    # Track that shutdown is called as part of uninstall.
    shutdown_calls: list[bool] = []
    original_shutdown = installed_processor.shutdown

    def _tracking_shutdown() -> None:
        shutdown_calls.append(True)
        original_shutdown()

    installed_processor.shutdown = _tracking_shutdown  # type: ignore[method-assign]

    assert patcher.undo_patch() is True
    assert patcher.patched is False
    assert patcher.processor is None
    assert shutdown_calls == [True]

    registered_after = _registered_processors() or []
    assert sentinel in registered_after, "sentinel was removed by uninstall"
    assert installed_processor not in registered_after

    # Restore the prior state so the test doesn't leak processors.
    set_trace_processors(original)


def test_generation_span_threads_model_config_request_params(
    client: WeaveClient, otel_spans: InMemorySpanExporter
) -> None:
    """``GenerationSpanData.model_config`` flows into ``gen_ai.request.*`` attrs."""
    processor = WeaveOtelTracingProcessor()
    trace = Mock(spec=Trace)
    trace.trace_id = "trace_g2"
    trace.name = "wf"
    trace.group_id = None
    processor.on_trace_start(trace)

    gen_span = Mock(spec=Span)
    gen_span.trace_id = "trace_g2"
    gen_span.span_id = "span_g2"
    gen_span.parent_id = None
    gen_span.span_data = GenerationSpanData(
        input=[{"role": "user", "content": "hi"}],
        output=[{"role": "assistant", "content": "hello"}],
        model="gpt-4o",
        model_config={
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 256,
            "frequency_penalty": 0.1,
            "presence_penalty": 0.2,
            "seed": 42,
            "stop": ["END"],
        },
        usage={"input_tokens": 1, "output_tokens": 1},
    )
    gen_span.started_at = None
    gen_span.ended_at = None
    gen_span.error = None
    processor.on_span_start(gen_span)
    processor.on_span_end(gen_span)
    processor.on_trace_end(trace)

    chat = next(s for s in otel_spans.get_finished_spans() if s.name == "chat gpt-4o")
    attrs = _attrs(chat)
    assert attrs["gen_ai.request.temperature"] == 0.7
    assert attrs["gen_ai.request.top_p"] == 0.9
    assert attrs["gen_ai.request.max_tokens"] == 256
    assert attrs["gen_ai.request.frequency_penalty"] == 0.1
    assert attrs["gen_ai.request.presence_penalty"] == 0.2
    assert attrs["gen_ai.request.seed"] == 42
    assert attrs["gen_ai.request.stop_sequences"] == ("END",)
    assert attrs["gen_ai.output.type"] == "text"


def test_on_trace_end_sweeps_leftover_spans(
    client: WeaveClient, otel_spans: InMemorySpanExporter
) -> None:
    """Spans the SDK never closed are swept on on_trace_end so state doesn't leak."""
    processor = WeaveOtelTracingProcessor()
    trace = Mock(spec=Trace)
    trace.trace_id = "trace_leak"
    trace.name = "wf"
    trace.group_id = None
    processor.on_trace_start(trace)

    leaked_span = Mock(spec=Span)
    leaked_span.trace_id = "trace_leak"
    leaked_span.span_id = "span_leaked"
    leaked_span.parent_id = None
    leaked_span.span_data = AgentSpanData(name="Ghost")
    leaked_span.started_at = None
    leaked_span.ended_at = None
    leaked_span.error = None
    processor.on_span_start(leaked_span)
    # Deliberately do NOT call on_span_end — simulate an abrupt failure where
    # the SDK ends the trace without closing the span.

    assert "span_leaked" in processor._span_otel
    assert "span_leaked" in processor._span_tokens
    assert "span_leaked" in processor._trace_spans["trace_leak"]

    processor.on_trace_end(trace)

    # Trace-scoped state is cleared; the leaked span got ended.
    assert "span_leaked" not in processor._span_otel
    assert "span_leaked" not in processor._span_tokens
    assert "trace_leak" not in processor._trace_spans
    assert "trace_leak" not in processor._conversation_ids


@pytest.mark.disable_logging_error_check(
    reason="the test deliberately triggers the enrichment-failure logger.exception"
)
def test_on_span_end_still_ends_span_when_enrichment_raises(
    client: WeaveClient, otel_spans: InMemorySpanExporter
) -> None:
    """Enrichment failures must not leak the OTel span.

    If anything in the attribute-building path raises (e.g. a malformed
    ``response.output`` item that doesn't expose ``model_dump``), the OTel
    span is already popped from internal maps and its context token detached
    before enrichment runs. Without a try/finally the span would never be
    ``.end()``-ed and would never reach the exporter.
    """
    processor = WeaveOtelTracingProcessor()
    trace = Mock(spec=Trace)
    trace.trace_id = "trace_boom"
    trace.name = "wf"
    trace.group_id = None
    processor.on_trace_start(trace)

    bad_output_item = Mock()
    bad_output_item.model_dump.side_effect = RuntimeError("boom")
    response = Mock()
    response.id = "resp_boom"
    response.model = "gpt-4o"
    response.output = [bad_output_item]
    usage = Mock()
    usage.input_tokens = 0
    usage.output_tokens = 0
    usage.output_tokens_details = None
    usage.input_tokens_details = None
    response.usage = usage

    response_data = Mock(spec=ResponseSpanData)
    response_data.__class__ = ResponseSpanData
    response_data.input = "hi"
    response_data.response = response
    response_data.usage = None

    response_span = Mock(spec=Span)
    response_span.trace_id = "trace_boom"
    response_span.span_id = "span_boom"
    response_span.parent_id = None
    response_span.span_data = response_data
    response_span.started_at = None
    response_span.ended_at = None
    response_span.error = None

    processor.on_span_start(response_span)
    processor.on_span_end(response_span)

    # State is cleaned up despite the enrichment exception.
    assert "span_boom" not in processor._span_otel
    assert "span_boom" not in processor._span_tokens
    assert "span_boom" not in processor._trace_spans["trace_boom"]

    # The OTel span made it to the exporter and carries an error status.
    finished = otel_spans.get_finished_spans()
    chat = next(
        s
        for s in finished
        if s.context.span_id is not None and "boom" in (s.status.description or "")
    )
    assert chat.status.status_code.name == "ERROR"

    processor.on_trace_end(trace)


def test_on_trace_end_detaches_leftover_tokens_in_lifo_order(
    client: WeaveClient,
    otel_spans: InMemorySpanExporter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The leftover-sweep must detach context tokens in LIFO order.

    ``otel_context.detach`` uses ``ContextVar.reset``, which restores the value
    captured when the token was *created*. Out-of-order detach leaves the OTel
    current-span context pointing at a stale span, corrupting any work that
    happens after the sweep. Iterating a ``set`` (the previous storage shape
    for ``_trace_spans``) gives hash-bucket order, not LIFO.
    """
    processor, trace = _make_processor_with_open_span_chain()
    expected_lifo_tokens = list(reversed(list(processor._span_tokens.values())))
    detach_calls = _record_detach_calls(monkeypatch)

    # Deliberately do NOT call on_span_end — leave them as leftover for the sweep.
    processor.on_trace_end(trace)

    assert detach_calls == expected_lifo_tokens


def test_end_open_spans_detaches_tokens_in_lifo_order(
    client: WeaveClient,
    otel_spans: InMemorySpanExporter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_end_open_spans`` (shutdown/force_flush path) must detach in LIFO order.

    Dict iteration is insertion order in Python 3.7+, but LIFO detach needs the
    *reverse* of insertion order.
    """
    processor, _trace = _make_processor_with_open_span_chain()
    expected_lifo_tokens = list(reversed(list(processor._span_tokens.values())))
    detach_calls = _record_detach_calls(monkeypatch)

    processor.force_flush()

    assert detach_calls == expected_lifo_tokens


def test_unhandled_span_type_emits_warning(
    client: WeaveClient,
    otel_spans: InMemorySpanExporter,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An unhandled SpanData subtype should emit a single WARNING.

    Otherwise a future openai-agents SDK release could introduce a new span
    type and we'd silently emit OTel spans with no GenAI semconv attributes —
    no signal that the integration needs updating. The warning points the
    user at the Weave issue tracker.
    """

    # Defined inside the test so the type is unique per invocation — the
    # module-level once-per-type dedupe set won't suppress the warning if
    # another test happened to use the same class.
    class _UnknownSpanData:
        type = "future_feature"

    processor = WeaveOtelTracingProcessor()
    trace = Mock(spec=Trace)
    trace.trace_id = "trace_unknown"
    trace.name = "wf"
    trace.group_id = None
    processor.on_trace_start(trace)

    span = Mock(spec=Span)
    span.trace_id = "trace_unknown"
    span.span_id = "span_unknown"
    span.parent_id = None
    span.span_data = _UnknownSpanData()
    span.started_at = None
    span.ended_at = None
    span.error = None

    with caplog.at_level(
        "WARNING", logger="weave.integrations.openai_agents.otel_processor"
    ):
        processor.on_span_start(span)
        processor.on_span_end(span)

    warnings_for_class = [
        r.getMessage()
        for r in caplog.records
        if r.levelname == "WARNING" and "_UnknownSpanData" in r.getMessage()
    ]
    assert len(warnings_for_class) == 1
    assert "https://github.com/wandb/weave/issues/" in warnings_for_class[0]


def test_undo_patch_is_noop_when_not_patched() -> None:
    """Calling undo_patch on a non-installed patcher returns True without error."""
    from weave.integrations.openai_agents.patcher import OpenAIAgentsOtelPatcher
    from weave.trace.autopatch import IntegrationSettings

    patcher = OpenAIAgentsOtelPatcher(IntegrationSettings())
    assert patcher.patched is False
    assert patcher.undo_patch() is True


@pytest.mark.asyncio
async def test_responses_model_and_direct_call_emit_one_record_each(
    client: WeaveClient,
    setup_tests: WeaveOtelTracingProcessor,
    otel_spans: InMemorySpanExporter,
    patched_openai: None,
) -> None:
    transport, requests = _mock_transport(
        _response_payload("resp_agents", "Agent answer"),
        _response_payload("resp_direct", "Direct answer"),
    )
    openai_client = AsyncOpenAI(
        api_key="test",
        http_client=httpx.AsyncClient(transport=transport),
    )
    try:
        model = OpenAIResponsesModel(model="gpt-4o", openai_client=openai_client)
        agent = Agent(name="Assistant", model=model)

        await Runner.run(agent, "Say hi")
        direct_response = await openai_client.responses.create(
            model="gpt-4o", input="Direct call"
        )
    finally:
        await openai_client.close()

    agent_chats = [
        span
        for span in otel_spans.get_finished_spans()
        if span.name.startswith("chat ")
        and _attrs(span).get("gen_ai.response.id") == "resp_agents"
    ]
    openai_calls = _calls_named(client, "openai.responses.create")

    assert direct_response.id == "resp_direct"
    assert len(requests) == 2
    assert len(agent_chats) == 1
    assert len(openai_calls) == 1
    assert openai_calls[0].output["id"] == "resp_direct"


@pytest.mark.asyncio
async def test_sampled_generation_span_bypasses_chat_completions_call(
    client: WeaveClient,
    setup_tests: WeaveOtelTracingProcessor,
    otel_spans: InMemorySpanExporter,
    patched_openai: None,
) -> None:
    transport, requests = _mock_transport(_chat_completion_payload("chatcmpl_agents"))
    openai_client = AsyncOpenAI(
        api_key="test",
        http_client=httpx.AsyncClient(transport=transport),
    )
    try:
        with trace("sampled generation"):
            with generation_span(
                input=[{"role": "user", "content": "Say hi"}],
                output=[{"role": "assistant", "content": "Hi"}],
                model="gpt-4o",
            ):
                response = await openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": "Say hi"}],
                )
    finally:
        await openai_client.close()

    assert response.id == "chatcmpl_agents"
    assert len(requests) == 1
    assert len(_by_name(otel_spans.get_finished_spans(), "chat ")) == 1
    assert _calls_named(client, "openai.chat.completions.create") == []


@pytest.mark.asyncio
async def test_disabled_response_span_keeps_openai_call(
    client: WeaveClient,
    setup_tests: WeaveOtelTracingProcessor,
    otel_spans: InMemorySpanExporter,
    patched_openai: None,
) -> None:
    transport, requests = _mock_transport(
        _response_payload("resp_disabled", "Direct answer")
    )
    openai_client = AsyncOpenAI(
        api_key="test",
        http_client=httpx.AsyncClient(transport=transport),
    )
    try:
        with trace("disabled response"):
            with response_span(disabled=True):
                response = await openai_client.responses.create(
                    model="gpt-4o", input="Direct call"
                )
    finally:
        await openai_client.close()

    openai_calls = _calls_named(client, "openai.responses.create")
    assert response.id == "resp_disabled"
    assert len(requests) == 1
    assert len(openai_calls) == 1
    assert openai_calls[0].output["id"] == "resp_disabled"


@pytest.mark.parametrize(
    "decision",
    [Decision.DROP, Decision.RECORD_ONLY],
    ids=["drop", "record-only"],
)
@pytest.mark.asyncio
async def test_unsampled_response_span_keeps_openai_call(
    decision: Decision,
    client: WeaveClient,
    setup_tests: WeaveOtelTracingProcessor,
    patched_openai: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = SDKTracerProvider(sampler=StaticSampler(decision))
    monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER", provider)
    response_id = f"resp_{decision.name.lower()}"
    transport, requests = _mock_transport(
        _response_payload(response_id, "Direct answer")
    )
    openai_client = AsyncOpenAI(
        api_key="test",
        http_client=httpx.AsyncClient(transport=transport),
    )
    try:
        with trace(f"{decision.name.lower()} response"):
            with response_span() as model_span:
                response = await openai_client.responses.create(
                    model="gpt-4o", input="Direct call"
                )
                model_span.span_data.response = response
    finally:
        await openai_client.close()
        provider.shutdown()

    openai_calls = _calls_named(client, "openai.responses.create")
    assert response.id == response_id
    assert len(requests) == 1
    assert len(openai_calls) == 1
    assert openai_calls[0].output["id"] == response_id


@pytest.mark.asyncio
async def test_model_span_context_is_isolated_between_asyncio_tasks(
    client: WeaveClient,
    setup_tests: WeaveOtelTracingProcessor,
    otel_spans: InMemorySpanExporter,
    patched_openai: None,
) -> None:
    transport, requests = _mock_transport(
        _response_payload("resp_model_task", "Model answer"),
        _response_payload("resp_direct_task", "Direct answer"),
    )
    openai_client = AsyncOpenAI(
        api_key="test",
        http_client=httpx.AsyncClient(transport=transport),
    )
    model_request_finished = asyncio.Event()
    direct_request_finished = asyncio.Event()

    async def direct_request() -> Any:
        await model_request_finished.wait()
        try:
            return await openai_client.responses.create(
                model="gpt-4o", input="Independent direct call"
            )
        finally:
            direct_request_finished.set()

    async def model_request() -> Any:
        with trace("model task"):
            with response_span() as model_span:
                try:
                    response = await openai_client.responses.create(
                        model="gpt-4o", input="Agents model call"
                    )
                    model_span.span_data.response = response
                finally:
                    model_request_finished.set()
                await direct_request_finished.wait()
                return response

    try:
        direct_task = asyncio.create_task(direct_request())
        model_task = asyncio.create_task(model_request())
        model_response, direct_response = await asyncio.gather(model_task, direct_task)
    finally:
        await openai_client.close()

    model_chats = [
        span
        for span in otel_spans.get_finished_spans()
        if span.name.startswith("chat ")
        and _attrs(span).get("gen_ai.response.id") == "resp_model_task"
    ]
    openai_calls = _calls_named(client, "openai.responses.create")

    assert model_response.id == "resp_model_task"
    assert direct_response.id == "resp_direct_task"
    assert len(requests) == 2
    assert len(model_chats) == 1
    assert len(openai_calls) == 1
    assert openai_calls[0].output["id"] == "resp_direct_task"
