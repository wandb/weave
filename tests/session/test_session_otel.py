"""Tests for OTel GenAI attribute builders and span emission in session_otel.py."""

from __future__ import annotations

import json
import time

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import NoOpTracerProvider, StatusCode

from weave.session.session import (
    Message,
    Reasoning,
    Session,
    Usage,
    get_current_llm,
    get_current_session,
    get_current_turn,
    start_session,
    start_tool,
)
from weave.session.session_otel import (
    execute_tool_attributes,
    invoke_agent_attributes,
    llm_attributes,
)


@pytest.fixture(autouse=True)
def _reset_contextvars():
    """Reset contextvar state after each test to prevent leakage."""
    yield
    if (llm := get_current_llm()) is not None:
        llm.end()
    if (turn := get_current_turn()) is not None:
        turn.end()
    if (session := get_current_session()) is not None:
        session.end()


@pytest.fixture
def otel_spans(monkeypatch: pytest.MonkeyPatch):
    """Provide an in-memory span exporter for capturing OTel spans.

    Overrides the global OTel tracer provider for the duration of the test.
    Uses ``monkeypatch.setattr`` on the private ``_TRACER_PROVIDER`` symbol
    rather than ``set_tracer_provider`` to avoid the "set once" warning
    and to guarantee restoration of the prior value.
    """
    exporter = InMemorySpanExporter()
    provider = SDKTracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER", provider)
    yield exporter
    provider.shutdown()


# ---------------------------------------------------------------------------
# invoke_agent_attributes
# ---------------------------------------------------------------------------


class TestInvokeAgentAttributes:
    def test_minimal_required_only(self) -> None:
        attrs = invoke_agent_attributes(agent_name="weather-bot")
        assert attrs == {
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "weather-bot",
        }

    def test_all_scalar_fields(self) -> None:
        attrs = invoke_agent_attributes(
            agent_name="weather-bot",
            conversation_id="conv-123",
            conversation_name="Weather Chat",
            provider_name="openai",
            model="gpt-4o",
        )
        assert attrs["gen_ai.operation.name"] == "invoke_agent"
        assert attrs["gen_ai.agent.name"] == "weather-bot"
        assert attrs["gen_ai.conversation.id"] == "conv-123"
        assert attrs["gen_ai.conversation.name"] == "Weather Chat"
        assert attrs["gen_ai.provider.name"] == "openai"
        assert attrs["gen_ai.request.model"] == "gpt-4o"

    def test_empty_optional_strings_omitted(self) -> None:
        attrs = invoke_agent_attributes(
            agent_name="bot",
            conversation_id="",
            conversation_name="",
            provider_name="",
            model="",
        )
        assert "gen_ai.conversation.id" not in attrs
        assert "gen_ai.conversation.name" not in attrs
        assert "gen_ai.provider.name" not in attrs
        assert "gen_ai.request.model" not in attrs

    def test_input_messages_serialized(self) -> None:
        msgs = [Message(role="user", content="Hello")]
        attrs = invoke_agent_attributes(agent_name="bot", input_messages=msgs)
        raw = json.loads(attrs["gen_ai.input.messages"])
        assert len(raw) == 1
        assert raw[0]["role"] == "user"
        assert raw[0]["content"] == "Hello"

    def test_output_messages_serialized(self) -> None:
        msgs = [Message(role="assistant", content="Hi there!")]
        attrs = invoke_agent_attributes(agent_name="bot", output_messages=msgs)
        raw = json.loads(attrs["gen_ai.output.messages"])
        assert len(raw) == 1
        assert raw[0]["role"] == "assistant"
        assert raw[0]["content"] == "Hi there!"

    def test_empty_message_list_omitted(self) -> None:
        attrs = invoke_agent_attributes(
            agent_name="bot",
            input_messages=[],
            output_messages=[],
        )
        assert "gen_ai.input.messages" not in attrs
        assert "gen_ai.output.messages" not in attrs

    def test_none_message_list_omitted(self) -> None:
        attrs = invoke_agent_attributes(
            agent_name="bot",
            input_messages=None,
            output_messages=None,
        )
        assert "gen_ai.input.messages" not in attrs
        assert "gen_ai.output.messages" not in attrs

    def test_messages_exclude_defaults(self) -> None:
        """Messages with default fields should omit those in serialization."""
        msgs = [Message(role="user", content="hi")]
        attrs = invoke_agent_attributes(agent_name="bot", input_messages=msgs)
        raw = json.loads(attrs["gen_ai.input.messages"])
        # tool_call_id and tool_name are defaults ("") so should be excluded
        assert "tool_call_id" not in raw[0]
        assert "tool_name" not in raw[0]

    def test_multiple_messages(self) -> None:
        msgs = [
            Message(role="user", content="Hi"),
            Message(role="assistant", content="Hello!"),
        ]
        attrs = invoke_agent_attributes(agent_name="bot", input_messages=msgs)
        raw = json.loads(attrs["gen_ai.input.messages"])
        assert len(raw) == 2
        assert raw[0]["role"] == "user"
        assert raw[1]["role"] == "assistant"

    def test_tool_message_preserves_tool_fields(self) -> None:
        msgs = [
            Message(
                role="tool",
                content="result",
                tool_call_id="tc_1",
                tool_name="get_weather",
            )
        ]
        attrs = invoke_agent_attributes(agent_name="bot", input_messages=msgs)
        raw = json.loads(attrs["gen_ai.input.messages"])
        assert raw[0]["tool_call_id"] == "tc_1"
        assert raw[0]["tool_name"] == "get_weather"


# ---------------------------------------------------------------------------
# llm_attributes
# ---------------------------------------------------------------------------


class TestLLMAttributes:
    def test_minimal_required_only(self) -> None:
        attrs = llm_attributes(model="gpt-4o")
        assert attrs == {
            "gen_ai.operation.name": "chat",
            "gen_ai.request.model": "gpt-4o",
        }

    def test_all_fields_populated(self) -> None:
        attrs = llm_attributes(
            model="gpt-4o",
            provider_name="openai",
            conversation_id="conv-123",
            response_id="resp-abc",
            finish_reasons=["stop"],
            system_instructions=["Be helpful", "Be concise"],
            usage=Usage(input_tokens=100, output_tokens=50, reasoning_tokens=20),
            input_messages=[Message(role="user", content="Hello")],
            output_messages=[Message(role="assistant", content="Hi!")],
        )
        assert attrs["gen_ai.operation.name"] == "chat"
        assert attrs["gen_ai.request.model"] == "gpt-4o"
        assert attrs["gen_ai.provider.name"] == "openai"
        assert attrs["gen_ai.conversation.id"] == "conv-123"
        assert attrs["gen_ai.response.id"] == "resp-abc"
        assert attrs["gen_ai.response.finish_reasons"] == ["stop"]
        assert attrs["gen_ai.usage.input_tokens"] == 100
        assert attrs["gen_ai.usage.output_tokens"] == 50
        assert attrs["gen_ai.usage.reasoning_tokens"] == 20
        # system_instructions serialized as JSON list
        raw_si = json.loads(attrs["gen_ai.system_instructions"])
        assert raw_si == ["Be helpful", "Be concise"]
        # messages serialized as JSON
        raw_in = json.loads(attrs["gen_ai.input.messages"])
        assert raw_in[0]["role"] == "user"
        raw_out = json.loads(attrs["gen_ai.output.messages"])
        assert raw_out[0]["role"] == "assistant"

    def test_conversation_id(self) -> None:
        attrs = llm_attributes(model="gpt-4o", conversation_id="sess-abc")
        assert attrs["gen_ai.conversation.id"] == "sess-abc"

    def test_empty_conversation_id_omitted(self) -> None:
        attrs = llm_attributes(model="gpt-4o", conversation_id="")
        assert "gen_ai.conversation.id" not in attrs

    def test_empty_optional_strings_omitted(self) -> None:
        attrs = llm_attributes(model="gpt-4o", provider_name="", response_id="")
        assert "gen_ai.provider.name" not in attrs
        assert "gen_ai.response.id" not in attrs

    def test_empty_finish_reasons_omitted(self) -> None:
        attrs = llm_attributes(model="gpt-4o", finish_reasons=[])
        assert "gen_ai.response.finish_reasons" not in attrs

    def test_none_finish_reasons_omitted(self) -> None:
        attrs = llm_attributes(model="gpt-4o", finish_reasons=None)
        assert "gen_ai.response.finish_reasons" not in attrs

    def test_zero_usage_tokens_omitted(self) -> None:
        attrs = llm_attributes(model="gpt-4o", usage=Usage())
        assert "gen_ai.usage.input_tokens" not in attrs
        assert "gen_ai.usage.output_tokens" not in attrs
        assert "gen_ai.usage.reasoning_tokens" not in attrs

    def test_none_usage_omitted(self) -> None:
        attrs = llm_attributes(model="gpt-4o", usage=None)
        assert "gen_ai.usage.input_tokens" not in attrs
        assert "gen_ai.usage.output_tokens" not in attrs
        assert "gen_ai.usage.reasoning_tokens" not in attrs

    def test_partial_usage_only_includes_nonzero(self) -> None:
        attrs = llm_attributes(
            model="gpt-4o",
            usage=Usage(input_tokens=100, output_tokens=0, reasoning_tokens=0),
        )
        assert attrs["gen_ai.usage.input_tokens"] == 100
        assert "gen_ai.usage.output_tokens" not in attrs
        assert "gen_ai.usage.reasoning_tokens" not in attrs

    def test_empty_system_instructions_omitted(self) -> None:
        attrs = llm_attributes(model="gpt-4o", system_instructions=[])
        assert "gen_ai.system_instructions" not in attrs

    def test_none_system_instructions_omitted(self) -> None:
        attrs = llm_attributes(model="gpt-4o", system_instructions=None)
        assert "gen_ai.system_instructions" not in attrs

    def test_empty_messages_omitted(self) -> None:
        attrs = llm_attributes(model="gpt-4o", input_messages=[], output_messages=[])
        assert "gen_ai.input.messages" not in attrs
        assert "gen_ai.output.messages" not in attrs

    def test_none_messages_omitted(self) -> None:
        attrs = llm_attributes(
            model="gpt-4o", input_messages=None, output_messages=None
        )
        assert "gen_ai.input.messages" not in attrs
        assert "gen_ai.output.messages" not in attrs

    def test_reasoning_is_not_an_attribute(self) -> None:
        """Reasoning is accepted by the function but does not produce an attribute."""
        attrs = llm_attributes(
            model="gpt-4o", reasoning=Reasoning(content="thinking...")
        )
        # reasoning is not part of the OTel GenAI attributes
        assert "gen_ai.reasoning" not in attrs
        assert "gen_ai.reasoning.content" not in attrs

    def test_multiple_finish_reasons(self) -> None:
        attrs = llm_attributes(model="gpt-4o", finish_reasons=["stop", "length"])
        assert attrs["gen_ai.response.finish_reasons"] == ["stop", "length"]


# ---------------------------------------------------------------------------
# execute_tool_attributes
# ---------------------------------------------------------------------------


class TestExecuteToolAttributes:
    def test_minimal_required_only(self) -> None:
        attrs = execute_tool_attributes(tool_name="get_weather")
        assert attrs == {
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": "get_weather",
        }

    def test_all_fields_populated(self) -> None:
        attrs = execute_tool_attributes(
            tool_name="get_weather",
            conversation_id="conv-123",
            tool_call_id="tc_1",
            tool_call_arguments='{"city": "Tokyo"}',
            tool_call_result='{"temp": "75F"}',
        )
        assert attrs["gen_ai.operation.name"] == "execute_tool"
        assert attrs["gen_ai.tool.name"] == "get_weather"
        assert attrs["gen_ai.conversation.id"] == "conv-123"
        assert attrs["gen_ai.tool.call.id"] == "tc_1"
        assert attrs["gen_ai.tool.call.arguments"] == '{"city": "Tokyo"}'
        assert attrs["gen_ai.tool.call.result"] == '{"temp": "75F"}'

    def test_conversation_id(self) -> None:
        attrs = execute_tool_attributes(tool_name="search", conversation_id="sess-abc")
        assert attrs["gen_ai.conversation.id"] == "sess-abc"

    def test_empty_conversation_id_omitted(self) -> None:
        attrs = execute_tool_attributes(tool_name="search", conversation_id="")
        assert "gen_ai.conversation.id" not in attrs

    def test_empty_optional_strings_omitted(self) -> None:
        attrs = execute_tool_attributes(
            tool_name="search",
            tool_call_id="",
            tool_call_arguments="",
            tool_call_result="",
        )
        assert "gen_ai.tool.call.id" not in attrs
        assert "gen_ai.tool.call.arguments" not in attrs
        assert "gen_ai.tool.call.result" not in attrs

    def test_partial_optional_fields(self) -> None:
        attrs = execute_tool_attributes(
            tool_name="search",
            tool_call_id="tc_2",
        )
        assert attrs["gen_ai.tool.call.id"] == "tc_2"
        assert "gen_ai.tool.call.arguments" not in attrs
        assert "gen_ai.tool.call.result" not in attrs


# ---------------------------------------------------------------------------
# Cross-cutting
# ---------------------------------------------------------------------------


class TestCrossCutting:
    def test_return_type_is_plain_dict(self) -> None:
        """All builders return plain dicts, not special types."""
        a = invoke_agent_attributes(agent_name="bot")
        b = llm_attributes(model="gpt-4o")
        c = execute_tool_attributes(tool_name="search")
        assert type(a) is dict
        assert type(b) is dict
        assert type(c) is dict


# ---------------------------------------------------------------------------
# OTel span emission
# ---------------------------------------------------------------------------


class TestOTelSpanEmission:
    def test_turn_creates_invoke_agent_span(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Session(
            agent_name="weather-bot", session_id="sess-1", session_name="Weather Chat"
        ) as s:
            with s.start_turn(user_message="What's the weather?") as turn:
                pass

        spans = otel_spans.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        assert span.name == "invoke_agent weather-bot"
        attrs = dict(span.attributes or {})
        assert attrs["gen_ai.operation.name"] == "invoke_agent"
        assert attrs["gen_ai.agent.name"] == "weather-bot"
        assert attrs["gen_ai.conversation.id"] == "sess-1"
        assert attrs["gen_ai.conversation.name"] == "Weather Chat"

    def test_llm_creates_chat_span(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(agent_name="bot", session_id="sess-llm") as s:
            with s.start_turn() as turn:
                with turn.llm(model="gpt-4o", provider_name="openai") as llm:
                    llm.usage = Usage(input_tokens=100, output_tokens=50)
                    llm.output("Hello!")

        spans = otel_spans.get_finished_spans()
        # LLM span ends first, then Turn span
        llm_spans = [sp for sp in spans if sp.name == "chat gpt-4o"]
        assert len(llm_spans) == 1
        attrs = dict(llm_spans[0].attributes or {})
        assert attrs["gen_ai.operation.name"] == "chat"
        assert attrs["gen_ai.request.model"] == "gpt-4o"
        assert attrs["gen_ai.provider.name"] == "openai"
        assert attrs["gen_ai.conversation.id"] == "sess-llm"
        assert attrs["gen_ai.usage.input_tokens"] == 100
        assert attrs["gen_ai.usage.output_tokens"] == 50

    def test_tool_creates_execute_tool_span(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Session(agent_name="bot", session_id="sess-tool") as s:
            with s.start_turn() as turn:
                with turn.tool(
                    name="get_weather",
                    arguments='{"city":"Tokyo"}',
                    tool_call_id="tc_1",
                ) as tool:
                    tool.result = "75F"

        spans = otel_spans.get_finished_spans()
        tool_spans = [sp for sp in spans if sp.name == "execute_tool get_weather"]
        assert len(tool_spans) == 1
        attrs = dict(tool_spans[0].attributes or {})
        assert attrs["gen_ai.operation.name"] == "execute_tool"
        assert attrs["gen_ai.tool.name"] == "get_weather"
        assert attrs["gen_ai.conversation.id"] == "sess-tool"
        assert attrs["gen_ai.tool.call.id"] == "tc_1"
        assert attrs["gen_ai.tool.call.arguments"] == '{"city":"Tokyo"}'
        assert attrs["gen_ai.tool.call.result"] == "75F"

    def test_subagent_creates_nested_invoke_agent_span(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Session(agent_name="orchestrator") as s:
            with s.start_turn() as turn:
                with turn.subagent(name="research-bot", model="gpt-4o-mini") as sa:
                    pass

        spans = otel_spans.get_finished_spans()
        sa_spans = [sp for sp in spans if sp.name == "invoke_agent research-bot"]
        turn_spans = [sp for sp in spans if sp.name == "invoke_agent orchestrator"]
        assert len(sa_spans) == 1
        assert len(turn_spans) == 1
        # SubAgent and Turn should share the same trace_id
        assert sa_spans[0].context.trace_id == turn_spans[0].context.trace_id
        # SubAgent's parent should be the Turn span
        assert sa_spans[0].parent.span_id == turn_spans[0].context.span_id

    def test_parent_child_hierarchy(self, otel_spans: InMemorySpanExporter) -> None:
        """LLM and Tool are both children of Turn (flat model)."""
        with Session(agent_name="bot") as s:
            with s.start_turn() as turn:
                with turn.llm(model="gpt-4o") as llm:
                    llm.output("checking...")
                with turn.tool(name="search", arguments='{"q":"X"}') as tool:
                    tool.result = "found"

        spans = otel_spans.get_finished_spans()
        turn_spans = [sp for sp in spans if sp.name == "invoke_agent bot"]
        llm_spans = [sp for sp in spans if sp.name == "chat gpt-4o"]
        tool_spans = [sp for sp in spans if sp.name == "execute_tool search"]

        assert len(turn_spans) == 1
        assert len(llm_spans) == 1
        assert len(tool_spans) == 1

        turn_span = turn_spans[0]
        llm_span = llm_spans[0]
        tool_span = tool_spans[0]

        # Both LLM and Tool share the same trace
        assert llm_span.context.trace_id == turn_span.context.trace_id
        assert tool_span.context.trace_id == turn_span.context.trace_id

        # Both are children of the Turn span
        assert llm_span.parent.span_id == turn_span.context.span_id
        assert tool_span.parent.span_id == turn_span.context.span_id

    def test_no_spans_without_setup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No errors when no provider configured (no-op spans)."""
        # Install a NoOpTracerProvider as the global provider. This produces
        # non-recording spans (no exporter, no recording overhead) and is the
        # canonical OTel pattern for "tracing not configured".
        monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER", NoOpTracerProvider())
        with Session(agent_name="bot") as s:
            with s.start_turn() as turn:
                with turn.llm(model="gpt-4o") as llm:
                    llm.output("Hello")
                with turn.tool(name="search") as tool:
                    tool.result = "done"
        # Should not raise — just silently use no-op spans

    def test_include_content_false_omits_messages(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Session(agent_name="bot", include_content=False) as s:
            with s.start_turn(user_message="secret input") as turn:
                with turn.llm(model="gpt-4o") as llm:
                    llm.input_messages.append(Message(role="user", content="secret"))
                    llm.output("secret output")
                    llm.system_instructions = ["be helpful"]
                with turn.tool(name="search", arguments='{"q":"secret"}') as tool:
                    tool.result = "secret result"

        spans = otel_spans.get_finished_spans()

        # Check Turn span — no input messages
        turn_spans = [sp for sp in spans if sp.name.startswith("invoke_agent")]
        assert len(turn_spans) == 1
        turn_attrs = dict(turn_spans[0].attributes or {})
        assert "gen_ai.input.messages" not in turn_attrs

        # Check LLM span — no messages or system instructions
        llm_spans = [sp for sp in spans if sp.name == "chat gpt-4o"]
        assert len(llm_spans) == 1
        llm_attrs = dict(llm_spans[0].attributes or {})
        assert "gen_ai.input.messages" not in llm_attrs
        assert "gen_ai.output.messages" not in llm_attrs
        assert "gen_ai.system_instructions" not in llm_attrs

        # Check Tool span — no arguments or result
        tool_spans = [sp for sp in spans if sp.name == "execute_tool search"]
        assert len(tool_spans) == 1
        tool_attrs = dict(tool_spans[0].attributes or {})
        assert "gen_ai.tool.call.arguments" not in tool_attrs
        assert "gen_ai.tool.call.result" not in tool_attrs


# ---------------------------------------------------------------------------
# Error recording
# ---------------------------------------------------------------------------


class TestErrorRecording:
    def test_llm_records_exception(self, otel_spans: InMemorySpanExporter) -> None:
        with start_session(agent_name="bot") as session:
            with session.start_turn() as turn:
                try:
                    with turn.llm(model="gpt-4o") as llm:
                        raise ValueError("LLM call failed")
                except ValueError:
                    pass
        spans = otel_spans.get_finished_spans()
        chat_span = next(
            s for s in spans if s.attributes.get("gen_ai.operation.name") == "chat"
        )
        assert chat_span.status.status_code == StatusCode.ERROR
        assert "LLM call failed" in chat_span.status.description
        assert len(chat_span.events) >= 1
        assert chat_span.events[0].name == "exception"

    def test_tool_records_exception(self, otel_spans: InMemorySpanExporter) -> None:
        with start_session(agent_name="bot") as session:
            with session.start_turn() as turn:
                try:
                    with turn.tool(name="search") as tool:
                        raise RuntimeError("tool broke")
                except RuntimeError:
                    pass
        spans = otel_spans.get_finished_spans()
        tool_span = next(
            s
            for s in spans
            if s.attributes.get("gen_ai.operation.name") == "execute_tool"
        )
        assert tool_span.status.status_code == StatusCode.ERROR

    def test_turn_records_exception(self, otel_spans: InMemorySpanExporter) -> None:
        with start_session(agent_name="bot") as session:
            try:
                with session.start_turn() as turn:
                    raise RuntimeError("turn broke")
            except RuntimeError:
                pass
        spans = otel_spans.get_finished_spans()
        turn_span = next(
            s
            for s in spans
            if s.attributes.get("gen_ai.operation.name") == "invoke_agent"
        )
        assert turn_span.status.status_code == StatusCode.ERROR

    def test_subagent_records_exception(self, otel_spans: InMemorySpanExporter) -> None:
        with start_session(agent_name="bot") as session:
            with session.start_turn() as turn:
                try:
                    with turn.subagent(name="sub") as sa:
                        raise RuntimeError("sub broke")
                except RuntimeError:
                    pass
        spans = otel_spans.get_finished_spans()
        sa_spans = [s for s in spans if s.attributes.get("gen_ai.agent.name") == "sub"]
        assert len(sa_spans) == 1
        assert sa_spans[0].status.status_code == StatusCode.ERROR


class TestStartToolSpan:
    def test_start_tool_creates_child_of_turn(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with start_session(agent_name="bot", session_id="sess-st") as s:
            with s.start_turn() as turn:
                with start_tool(
                    name="get_weather",
                    arguments='{"city":"Tokyo"}',
                    tool_call_id="tc_1",
                ) as t:
                    t.result = "75F"

        spans = otel_spans.get_finished_spans()
        turn_spans = [sp for sp in spans if sp.name.startswith("invoke_agent")]
        tool_spans = [sp for sp in spans if sp.name == "execute_tool get_weather"]
        assert len(tool_spans) == 1
        assert len(turn_spans) == 1
        # Tool is child of Turn
        assert tool_spans[0].parent.span_id == turn_spans[0].context.span_id
        # Same trace
        assert tool_spans[0].context.trace_id == turn_spans[0].context.trace_id
        # Attributes correct
        attrs = dict(tool_spans[0].attributes or {})
        assert attrs["gen_ai.operation.name"] == "execute_tool"
        assert attrs["gen_ai.tool.name"] == "get_weather"
        assert attrs["gen_ai.conversation.id"] == "sess-st"
        assert attrs["gen_ai.tool.call.id"] == "tc_1"


class TestDistinctTracePerTurn:
    def test_two_turns_have_different_trace_ids(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with start_session(agent_name="bot") as s:
            with s.start_turn(user_message="first") as t1:
                pass
            with s.start_turn(user_message="second") as t2:
                pass

        spans = otel_spans.get_finished_spans()
        assert len(spans) == 2
        trace_ids = {sp.context.trace_id for sp in spans}
        assert len(trace_ids) == 2, "Each turn should have a distinct trace_id"


class TestContinueParentTrace:
    """Verifies the ``continue_parent_trace`` knob nests turns inside an
    outer trace instead of starting a fresh one. Mirrors the case where the
    application is already instrumented (e.g. fastapi/django) and weave is
    invoked inside an existing request span.
    """

    def test_default_starts_new_trace_even_under_outer_span(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        # Default behavior: turn ignores the ambient trace.
        tracer = otel_trace.get_tracer("test.outer")
        with tracer.start_as_current_span("outer-request") as outer:
            outer_trace_id = outer.get_span_context().trace_id
            with start_session(agent_name="bot") as s:
                with s.start_turn() as turn:
                    pass

        spans = otel_spans.get_finished_spans()
        turn_spans = [sp for sp in spans if sp.name == "invoke_agent bot"]
        assert len(turn_spans) == 1
        assert turn_spans[0].context.trace_id != outer_trace_id

    def test_continue_parent_trace_nests_turn_under_outer_span(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        tracer = otel_trace.get_tracer("test.outer")
        with tracer.start_as_current_span("outer-request") as outer:
            outer_trace_id = outer.get_span_context().trace_id
            outer_span_id = outer.get_span_context().span_id
            with start_session(agent_name="bot", continue_parent_trace=True) as s:
                with s.start_turn() as turn:
                    pass

        spans = otel_spans.get_finished_spans()
        turn_spans = [sp for sp in spans if sp.name == "invoke_agent bot"]
        assert len(turn_spans) == 1
        # Same trace and Turn parents under the outer request span
        assert turn_spans[0].context.trace_id == outer_trace_id
        assert turn_spans[0].parent is not None
        assert turn_spans[0].parent.span_id == outer_span_id


class TestStartTimeFromLogicalConstruction:
    """Verifies that the OTel span ``start_time`` reflects when the SDK
    object was constructed (``started_at``), not when ``__enter__`` ran.
    Addresses prior-PR review feedback about start-time drift on Turn/LLM.
    """

    def test_turn_span_start_time_matches_started_at(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with start_session(agent_name="bot") as s:
            turn = s.start_turn()  # constructed here, started_at set
            assert turn.started_at is not None
            expected_ns = int(turn.started_at.timestamp() * 1_000_000_000)
            # Sleep so __enter__ runs measurably later than construction.
            time.sleep(0.05)
            with turn:
                pass

        spans = otel_spans.get_finished_spans()
        turn_spans = [sp for sp in spans if sp.name == "invoke_agent bot"]
        assert len(turn_spans) == 1
        # Allow up to 1ms of drift from int conversion / pydantic timing.
        assert abs(turn_spans[0].start_time - expected_ns) <= 1_000_000

    def test_llm_span_start_time_matches_started_at(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with start_session(agent_name="bot") as s:
            with s.start_turn() as turn:
                llm = turn.llm(model="gpt-4o")
                assert llm.started_at is not None
                expected_ns = int(llm.started_at.timestamp() * 1_000_000_000)
                time.sleep(0.05)
                with llm:
                    pass

        spans = otel_spans.get_finished_spans()
        llm_spans = [sp for sp in spans if sp.name == "chat gpt-4o"]
        assert len(llm_spans) == 1
        assert abs(llm_spans[0].start_time - expected_ns) <= 1_000_000
