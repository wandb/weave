"""Tests for the OTel variant of the OpenAI Agents tracing processor.

Sibling of ``openai_agents_test.py`` — same trigger flows (Agent runs via
recorded cassettes, mock-driven processor unit checks), but asserts on
emitted OTel spans instead of Weave calls.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import agents
import pytest
from agents import Agent, Runner
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
)
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from weave.integrations.openai_agents.otel_processor import (
    WeaveOtelTracingProcessor,
    _iso_to_ns,
)
from weave.trace.weave_client import WeaveClient


@pytest.fixture
def otel_spans(monkeypatch: pytest.MonkeyPatch):
    """Install an in-memory OTel exporter and return it for assertions.

    Mirrors the fixture in ``tests/session/test_session_otel.py`` — overrides
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
def setup_tests():
    """Install only the OTel processor for the duration of the test.

    Mirrors the calls-side fixture but uses ``WeaveOtelTracingProcessor``.
    """
    agents.set_trace_processors([WeaveOtelTracingProcessor()])


def _attrs(span: Any) -> dict[str, Any]:
    """Return span attributes as a plain dict."""
    return dict(span.attributes) if span.attributes is not None else {}


def _by_name(spans: list[Any], prefix: str) -> list[Any]:
    return [s for s in spans if s.name.startswith(prefix)]


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_openai_agents_quickstart_otel(
    client: WeaveClient, setup_tests, otel_spans: InMemorySpanExporter
) -> None:
    agent = Agent(name="Assistant", instructions="You are a helpful assistant")

    Runner.run_sync(agent, "Write a haiku about recursion in programming.")

    spans = otel_spans.get_finished_spans()

    # No chat spans — Response/Generation are skipped in OTel mode.
    assert not _by_name(spans, "chat ")

    # Trace root + Task + Agent + Turn = 4 spans (matches calls-side count).
    assert len(spans) == 4

    # Spans are ordered by end time. The leaf (turn) finishes first, parents
    # finish last. Build a name → span map for stable assertions.
    by_name = {s.name: s for s in spans}

    assert "invoke_agent Agent workflow" in by_name
    workflow = by_name["invoke_agent Agent workflow"]
    workflow_attrs = _attrs(workflow)
    assert workflow_attrs["gen_ai.operation.name"] == "invoke_agent"
    assert workflow_attrs["gen_ai.agent.name"] == "Agent workflow"
    # Without an explicit group_id, conversation.id falls back to trace_id.
    assert workflow_attrs["gen_ai.conversation.id"].startswith("trace_")
    assert workflow_attrs["weave.openai_agents.trace_id"].startswith("trace_")

    assert "invoke_agent Assistant" in by_name
    agent_span = by_name["invoke_agent Assistant"]
    assert _attrs(agent_span)["gen_ai.agent.name"] == "Assistant"

    turn_spans = _by_name(spans, "invoke_agent Assistant turn ")
    assert len(turn_spans) == 1
    assert _attrs(turn_spans[0])["weave.openai_agents.turn.number"] == 1


def test_response_and_generation_spans_are_skipped(
    client: WeaveClient, otel_spans: InMemorySpanExporter
) -> None:
    """ResponseSpan and GenerationSpan don't produce OTel spans.

    The openai-OTel patcher (forthcoming) is the source of truth for chat spans
    — see module docstring on WeaveOtelTracingProcessor.
    """
    processor = WeaveOtelTracingProcessor()

    trace = Mock(spec=Trace)
    trace.trace_id = "trace_abc"
    trace.name = "test"
    trace.group_id = None
    processor.on_trace_start(trace)

    response_data = Mock(spec=ResponseSpanData)
    response_data.__class__ = ResponseSpanData
    response_span = Mock(spec=Span)
    response_span.trace_id = "trace_abc"
    response_span.span_id = "span_resp"
    response_span.parent_id = None
    response_span.span_data = response_data
    response_span.started_at = None
    response_span.ended_at = None
    response_span.error = None

    processor.on_span_start(response_span)
    processor.on_span_end(response_span)

    generation_data = Mock(spec=GenerationSpanData)
    generation_data.__class__ = GenerationSpanData
    generation_span = Mock(spec=Span)
    generation_span.trace_id = "trace_abc"
    generation_span.span_id = "span_gen"
    generation_span.parent_id = None
    generation_span.span_data = generation_data
    generation_span.started_at = None
    generation_span.ended_at = None
    generation_span.error = None

    processor.on_span_start(generation_span)
    processor.on_span_end(generation_span)

    processor.on_trace_end(trace)

    # Only the trace root span; no children for Response/Generation.
    spans = otel_spans.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "invoke_agent test"


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
    """``group_id`` (when set) becomes ``gen_ai.conversation.id``; otherwise trace_id."""
    processor = WeaveOtelTracingProcessor()

    trace_with_group = Mock(spec=Trace)
    trace_with_group.trace_id = "trace_1"
    trace_with_group.name = "wf1"
    trace_with_group.group_id = "chat_456"
    processor.on_trace_start(trace_with_group)
    processor.on_trace_end(trace_with_group)

    trace_no_group = Mock(spec=Trace)
    trace_no_group.trace_id = "trace_2"
    trace_no_group.name = "wf2"
    trace_no_group.group_id = None
    processor.on_trace_start(trace_no_group)
    processor.on_trace_end(trace_no_group)

    spans = otel_spans.get_finished_spans()
    wf1 = next(s for s in spans if s.name == "invoke_agent wf1")
    wf2 = next(s for s in spans if s.name == "invoke_agent wf2")
    assert _attrs(wf1)["gen_ai.conversation.id"] == "chat_456"
    assert _attrs(wf2)["gen_ai.conversation.id"] == "trace_2"


def test_newer_agent_task_and_turn_fields(
    client: WeaveClient, otel_spans: InMemorySpanExporter
) -> None:
    """Task/Turn spans emit invoke_agent OTel spans with structured metadata."""
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
    task = next(s for s in spans if s.name == "invoke_agent Runner task")
    task_attrs = _attrs(task)
    assert task_attrs["gen_ai.operation.name"] == "invoke_agent"
    assert task_attrs["gen_ai.agent.name"] == "Runner task"
    assert task_attrs["weave.openai_agents.task.metadata.session_id"] == "session-1"

    turn = next(s for s in spans if s.name == "invoke_agent Assistant turn 2")
    turn_attrs = _attrs(turn)
    assert turn_attrs["gen_ai.operation.name"] == "invoke_agent"
    assert turn_attrs["gen_ai.agent.name"] == "Assistant"
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
    assert "trace_x" in processor._trace_root_spans

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
    assert processor._trace_root_spans == {}
    assert processor._span_otel == {}
    assert processor._conversation_ids == {}

    # shutdown is idempotent when state is already empty.
    processor.shutdown()
    assert processor._trace_root_spans == {}


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
