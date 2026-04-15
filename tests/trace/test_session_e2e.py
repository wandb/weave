"""End-to-end integration test: Session SDK -> OTel spans -> genai_extraction.

This test verifies the full pipeline without requiring ClickHouse:
1. Session SDK emits OTel spans (via InMemorySpanExporter)
2. Spans are converted to the server's Span format
3. extract_genai_span() produces correct GenAISpanCHInsertable rows
"""

from __future__ import annotations

import json

from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from weave.trace.session import (
    Message,
    Reasoning,
    Usage,
    start_session,
)
from weave.trace_server.opentelemetry.genai_extraction import extract_genai_span
from weave.trace_server.opentelemetry.helpers import expand_attributes
from weave.trace_server.opentelemetry.python_spans import (
    Event,
    Resource,
    Span,
    SpanKind,
    Status,
    StatusCode,
)

PROJECT_ID = "test-entity/test-project"


def _readable_span_to_server_span(readable: ReadableSpan) -> Span:
    """Convert an OTel SDK ReadableSpan to the server's Span dataclass.

    This bridges the gap between what InMemorySpanExporter captures and what
    extract_genai_span() expects, without going through protobuf serialization.
    """
    ctx = readable.get_span_context()
    trace_id = f"{ctx.trace_id:032x}"
    span_id = f"{ctx.span_id:016x}"

    parent_id = None
    if readable.parent is not None:
        parent_id = f"{readable.parent.span_id:016x}"

    # Expand flat dotted keys into nested dicts (mirrors unflatten_key_values)
    flat_attrs = readable.attributes or {}
    nested_attrs = expand_attributes(flat_attrs.items())

    # Convert events
    events = []
    for ev in readable.events or []:
        ev_attrs = dict(ev.attributes) if ev.attributes else {}
        events.append(
            Event(
                name=ev.name,
                timestamp=ev.timestamp or 0,
                attributes=expand_attributes(ev_attrs.items()),
            )
        )

    # Map OTel SDK SpanKind to server SpanKind
    kind_map = {
        0: SpanKind.UNSPECIFIED,
        1: SpanKind.INTERNAL,
        2: SpanKind.SERVER,
        3: SpanKind.CLIENT,
        4: SpanKind.PRODUCER,
        5: SpanKind.CONSUMER,
    }
    kind = kind_map.get(readable.kind.value if readable.kind else 0, SpanKind.INTERNAL)

    # Status
    status = Status(code=StatusCode.UNSET)
    if readable.status is not None:
        status_code_map = {
            0: StatusCode.UNSET,
            1: StatusCode.OK,
            2: StatusCode.ERROR,
        }
        status = Status(
            code=status_code_map.get(
                readable.status.status_code.value, StatusCode.UNSET
            ),
            message=readable.status.description or "",
        )

    resource = None
    if readable.resource:
        resource = Resource(
            attributes=dict(readable.resource.attributes),
        )

    return Span(
        resource=resource,
        name=readable.name,
        trace_id=trace_id,
        span_id=span_id,
        start_time_unix_nano=readable.start_time or 0,
        end_time_unix_nano=readable.end_time or 0,
        attributes=nested_attrs,
        kind=kind,
        parent_id=parent_id,
        events=events,
        status=status,
    )


def _create_session_spans() -> list[ReadableSpan]:
    """Create a session with turn, step, and tool, returning captured OTel spans."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    session = start_session(
        agent_name="WeatherBot",
        session_id="sess-abc-123",
        session_name="Weather Chat",
        _tracer_provider=provider,
    )
    with session.start_turn() as turn:
        turn.user("What's the weather in SF?")
        with turn.start_step(
            model="gpt-4o",
            provider_name="openai",
        ) as step:
            step.input_messages.append(
                Message(role="user", content="What's the weather in SF?")
            )
            # Tool call
            with step.start_tool(
                name="get_weather",
                arguments='{"city": "San Francisco"}',
            ) as tool:
                tool.result = '{"temp": 65, "condition": "sunny"}'

            step.output_messages.append(
                Message(role="assistant", content="It's 65F and sunny in SF!")
            )
            step.reasoning = Reasoning(content="I need to look up the weather first.")
            step.usage = Usage(
                input_tokens=50,
                output_tokens=30,
                reasoning_tokens=10,
            )
    session.end()

    return list(exporter.get_finished_spans())


class TestSessionE2EPipeline:
    """Full pipeline: Session SDK -> OTel spans -> extract_genai_span."""

    def test_pipeline_produces_correct_span_count(self):
        readable_spans = _create_session_spans()
        # Should have 3 spans: execute_tool, chat, invoke_agent
        assert len(readable_spans) == 3

    def test_invoke_agent_extraction(self):
        readable_spans = _create_session_spans()
        server_spans = [_readable_span_to_server_span(s) for s in readable_spans]

        invoke_spans = [s for s in server_spans if s.name == "invoke_agent"]
        assert len(invoke_spans) == 1
        result = extract_genai_span(invoke_spans[0], PROJECT_ID)
        row = result.span

        assert row.project_id == PROJECT_ID
        assert row.operation_name == "invoke_agent"
        assert row.agent_name == "WeatherBot"
        assert row.conversation_id == "sess-abc-123"
        assert row.conversation_name == "Weather Chat"
        assert row.status_code == "OK"

        # Aggregated tokens from child steps
        assert row.input_tokens == 50
        assert row.output_tokens == 30

    def test_chat_extraction(self):
        readable_spans = _create_session_spans()
        server_spans = [_readable_span_to_server_span(s) for s in readable_spans]

        chat_spans = [s for s in server_spans if s.name == "chat"]
        assert len(chat_spans) == 1
        result = extract_genai_span(chat_spans[0], PROJECT_ID)
        row = result.span

        assert row.operation_name == "chat"
        assert row.request_model == "gpt-4o"
        assert row.provider_name == "openai"
        assert row.input_tokens == 50
        assert row.output_tokens == 30
        assert row.reasoning_tokens == 10

        # Check reasoning content
        assert "I need to look up the weather first." in row.reasoning_content

        # Input messages
        assert len(row.input_messages) >= 1
        user_msgs = [m for m in row.input_messages if m.role == "user"]
        assert len(user_msgs) >= 1
        assert "weather" in user_msgs[0].content.lower()

        # Output messages: reasoning part comes first, then the actual response
        assert len(row.output_messages) >= 1
        asst_msgs = [m for m in row.output_messages if m.role == "assistant"]
        assert len(asst_msgs) >= 2  # reasoning + actual response
        # The actual response content (not reasoning) should mention "65"
        content_msgs = [m for m in asst_msgs if "65" in m.content]
        assert len(content_msgs) >= 1

    def test_execute_tool_extraction(self):
        readable_spans = _create_session_spans()
        server_spans = [_readable_span_to_server_span(s) for s in readable_spans]

        tool_spans = [s for s in server_spans if s.name == "execute_tool"]
        assert len(tool_spans) == 1
        result = extract_genai_span(tool_spans[0], PROJECT_ID)
        row = result.span

        assert row.operation_name == "execute_tool"
        assert row.tool_name == "get_weather"

        # Tool arguments
        args = json.loads(row.tool_call_arguments)
        assert args["city"] == "San Francisco"

        # Tool result
        tool_result = json.loads(row.tool_call_result)
        assert tool_result["temp"] == 65

    def test_parent_child_relationships(self):
        readable_spans = _create_session_spans()
        server_spans = [_readable_span_to_server_span(s) for s in readable_spans]

        by_name = {}
        for s in server_spans:
            by_name[s.name] = s

        invoke_span = by_name["invoke_agent"]
        chat_span = by_name["chat"]
        tool_span = by_name["execute_tool"]

        # All share the same trace_id
        assert chat_span.trace_id == invoke_span.trace_id
        assert tool_span.trace_id == invoke_span.trace_id

        # chat's parent is invoke_agent
        assert chat_span.parent_id == invoke_span.span_id

        # tool's parent is chat
        assert tool_span.parent_id == chat_span.span_id

        # Verify these relationships survive extraction
        invoke_result = extract_genai_span(invoke_span, PROJECT_ID)
        chat_result = extract_genai_span(chat_span, PROJECT_ID)
        tool_result = extract_genai_span(tool_span, PROJECT_ID)

        assert chat_result.span.parent_span_id == invoke_result.span.span_id
        assert tool_result.span.parent_span_id == chat_result.span.span_id
        assert invoke_result.span.parent_span_id == ""

    def test_eav_attribute_rows_generated(self):
        """Verify EAV rows are produced for non-semconv attributes."""
        readable_spans = _create_session_spans()
        server_spans = [_readable_span_to_server_span(s) for s in readable_spans]

        # All spans should produce extraction results
        for s in server_spans:
            result = extract_genai_span(s, PROJECT_ID)
            assert result.span is not None
            # EAV rows should have correct project_id
            for attr_row in result.attributes:
                assert attr_row.project_id == PROJECT_ID
                assert attr_row.span_id == s.span_id

    def test_timestamps_are_set(self):
        """Verify started_at and ended_at are populated."""
        readable_spans = _create_session_spans()
        server_spans = [_readable_span_to_server_span(s) for s in readable_spans]

        for s in server_spans:
            result = extract_genai_span(s, PROJECT_ID)
            row = result.span
            assert row.started_at is not None
            assert row.ended_at is not None
            # ended_at should be >= started_at
            assert row.ended_at >= row.started_at
