"""Tests for the Session SDK API surface."""

from __future__ import annotations

import pytest

from weave.session.session import (
    LLM,
    LogResult,
    Message,
    Reasoning,
    Session,
    SubAgent,
    Tool,
    Turn,
    Usage,
    end_llm,
    end_session,
    end_turn,
    get_current_llm,
    get_current_session,
    get_current_turn,
    log_session,
    log_turn,
    start_llm,
    start_session,
    start_turn,
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


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class TestMessage:
    def test_defaults(self) -> None:
        msg = Message(role="user")
        assert msg.role == "user"
        assert msg.content == ""
        assert msg.tool_call_id == ""
        assert msg.tool_name == ""

    def test_all_fields(self) -> None:
        msg = Message(
            role="tool",
            content="result",
            tool_call_id="tc_1",
            tool_name="get_weather",
        )
        assert msg.role == "tool"
        assert msg.content == "result"
        assert msg.tool_call_id == "tc_1"
        assert msg.tool_name == "get_weather"


class TestUsage:
    def test_defaults(self) -> None:
        u = Usage()
        assert u.input_tokens == 0
        assert u.output_tokens == 0
        assert u.reasoning_tokens == 0

    def test_set_fields(self) -> None:
        u = Usage(input_tokens=100, output_tokens=50, reasoning_tokens=20)
        assert u.input_tokens == 100
        assert u.output_tokens == 50
        assert u.reasoning_tokens == 20


class TestReasoning:
    def test_defaults(self) -> None:
        r = Reasoning()
        assert r.content == ""

    def test_set_content(self) -> None:
        r = Reasoning(content="thinking...")
        assert r.content == "thinking..."


class TestLogResult:
    def test_defaults(self) -> None:
        lr = LogResult()
        assert lr.session_id == ""
        assert lr.trace_ids == []
        assert lr.root_span_ids == []
        assert lr.span_count == 0


# ---------------------------------------------------------------------------
# Core classes
# ---------------------------------------------------------------------------


class TestTool:
    def test_defaults(self) -> None:
        t = Tool(name="get_weather")
        assert t.name == "get_weather"
        assert t.arguments == ""
        assert t.result == ""
        assert t.tool_call_id == ""
        assert t.duration_ms == 0

    def test_context_manager(self) -> None:
        with Tool(name="search", arguments='{"q":"test"}') as t:
            t.result = "found it"
        assert t.result == "found it"
        assert t.duration_ms >= 0

    def test_end_idempotent(self) -> None:
        t = Tool(name="x")
        t.end()
        t.end()  # second call is a no-op


class TestLLM:
    def test_defaults(self) -> None:
        c = LLM(model="gpt-4o")
        assert c.model == "gpt-4o"
        assert c.provider_name == ""
        assert c.response_id == ""
        assert c.system_instructions == []
        assert isinstance(c.usage, Usage)
        assert isinstance(c.reasoning, Reasoning)
        assert c.finish_reasons == []
        assert c.input_messages == []
        assert c.output_messages == []

    def test_fluent_builders(self) -> None:
        c = LLM(model="gpt-4o")
        assert c.output("Hello!") is c
        assert len(c.output_messages) == 1
        assert c.output_messages[0].role == "assistant"
        assert c.output_messages[0].content == "Hello!"
        assert c.think("Let me consider...") is c
        assert c.reasoning.content == "Let me consider..."

    def test_attach_methods_return_self(self) -> None:
        c = LLM(model="gpt-4o")
        assert c.attach_file("file_123") is c
        assert c.attach_image(b"png_bytes") is c
        assert c.attach_uri("https://example.com/img.png") is c

    def test_context_manager_sets_timestamps(self) -> None:
        with LLM(model="gpt-4o") as c:
            assert c.started_at is not None
        assert c.ended_at is not None

    def test_usage_assignment(self) -> None:
        c = LLM(model="gpt-4o")
        c.usage = Usage(input_tokens=100, output_tokens=50, reasoning_tokens=20)
        assert c.usage.input_tokens == 100


class TestSubAgent:
    def test_defaults(self) -> None:
        sa = SubAgent(name="research-bot")
        assert sa.name == "research-bot"
        assert sa.model == ""

    def test_llm_returns_llm_and_inherits_model(self) -> None:
        sa = SubAgent(name="research-bot", model="gpt-4o-mini")
        c = sa.llm(model="gpt-4o-mini")
        assert isinstance(c, LLM)
        assert c.model == "gpt-4o-mini"
        # inherits model when not specified
        c2 = sa.llm()
        assert c2.model == "gpt-4o-mini"

    def test_tool_returns_tool(self) -> None:
        sa = SubAgent(name="bot")
        t = sa.tool(name="web_search", arguments='{"q":"X"}', tool_call_id="tc_2")
        assert isinstance(t, Tool)
        assert t.name == "web_search"

    def test_context_manager_sets_timestamps(self) -> None:
        with SubAgent(name="bot") as sa:
            assert sa.started_at is not None
        assert sa.ended_at is not None

    def test_subagent_with_nested_tools(self) -> None:
        with Turn(agent_name="bot") as turn:
            with turn.subagent(name="sub") as sa:
                with sa.tool(name="tool1", arguments='{"x":1}') as t1:
                    t1.result = "result1"
                with sa.tool(name="tool2", arguments='{"x":2}') as t2:
                    t2.result = "result2"
        assert t1.result == "result1"
        assert t1.duration_ms >= 0
        assert t2.result == "result2"
        assert sa.ended_at is not None


# ---------------------------------------------------------------------------
# Turn and Session
# ---------------------------------------------------------------------------


class TestTurn:
    def test_defaults(self) -> None:
        t = Turn(agent_name="weather-bot")
        assert t.agent_name == "weather-bot"
        assert t.model == ""
        assert t.messages == []

    def test_user_appends_message_and_returns_self(self) -> None:
        t = Turn()
        result = t.user("Hello")
        assert result is t
        assert len(t.messages) == 1
        assert t.messages[0].role == "user"
        assert t.messages[0].content == "Hello"

    def test_llm_returns_llm_and_inherits_model(self) -> None:
        t = Turn(model="gpt-4o")
        c = t.llm(
            model="gpt-4o",
            provider_name="openai",
            system_instructions=["Be helpful"],
        )
        assert isinstance(c, LLM)
        assert c.model == "gpt-4o"
        assert c.provider_name == "openai"
        assert c.system_instructions == ["Be helpful"]
        # inherits model when not specified
        c2 = t.llm()
        assert c2.model == "gpt-4o"

    def test_tool_returns_tool(self) -> None:
        t = Turn()
        tool = t.tool(
            name="get_weather", arguments='{"city":"Tokyo"}', tool_call_id="tc_1"
        )
        assert isinstance(tool, Tool)
        assert tool.name == "get_weather"
        assert tool.tool_call_id == "tc_1"

    def test_subagent_returns_subagent_and_inherits_model(self) -> None:
        t = Turn(model="gpt-4o")
        sa = t.subagent(name="research-bot", model="gpt-4o-mini")
        assert isinstance(sa, SubAgent)
        assert sa.name == "research-bot"
        assert sa.model == "gpt-4o-mini"
        # inherits model when not specified
        sa2 = t.subagent(name="bot")
        assert sa2.model == "gpt-4o"

    def test_context_manager_sets_timestamps(self) -> None:
        with Turn() as t:
            assert t.started_at is not None
        assert t.ended_at is not None


class TestSession:
    def test_auto_generates_session_id(self) -> None:
        s = Session()
        assert s.session_id != ""
        assert len(s.session_id) == 36  # UUID format

    def test_explicit_session_id(self) -> None:
        s = Session(session_id="my-session-123")
        assert s.session_id == "my-session-123"

    def test_include_content_default_true(self) -> None:
        s = Session()
        assert s.include_content is True

    def test_include_content_false(self) -> None:
        s = Session(include_content=False)
        assert s.include_content is False

    def test_start_turn_returns_turn(self) -> None:
        s = Session(agent_name="weather-bot", model="gpt-4o")
        t = s.start_turn(user_message="What's the weather?")
        assert isinstance(t, Turn)
        assert t.agent_name == "weather-bot"
        assert t.model == "gpt-4o"
        assert len(t.messages) == 1
        assert t.messages[0].role == "user"
        assert t.messages[0].content == "What's the weather?"

    def test_start_turn_inherits_and_overrides_agent_name(self) -> None:
        s = Session(agent_name="weather-bot")
        t = s.start_turn()
        assert t.agent_name == "weather-bot"
        t2 = s.start_turn(agent_name="custom-bot")
        assert t2.agent_name == "custom-bot"

    def test_start_turn_no_user_message(self) -> None:
        s = Session()
        t = s.start_turn()
        assert t.messages == []

    def test_start_turn_auto_ends_previous(self) -> None:
        s = Session()
        t1 = s.start_turn()
        t2 = s.start_turn()
        assert t1._ended is True
        assert t2._ended is False

    def test_context_manager(self) -> None:
        with Session(agent_name="bot") as s:
            assert s.session_id != ""


# ---------------------------------------------------------------------------
# Contextvars and top-level functions
# ---------------------------------------------------------------------------


class TestContextVars:
    """Test contextvar-based cross-module tracing."""

    def test_start_session_sets_contextvar(self) -> None:
        s = start_session(agent_name="bot")
        try:
            assert get_current_session() is s
        finally:
            s.end()
        assert get_current_session() is None

    def test_session_context_manager_sets_contextvar(self) -> None:
        with Session(agent_name="bot") as s:
            assert get_current_session() is s
        assert get_current_session() is None

    def test_start_turn_sets_contextvar(self) -> None:
        s = start_session(agent_name="bot")
        try:
            t = start_turn(user_message="hi")
            assert get_current_turn() is t
            assert len(t.messages) == 1
            assert t.messages[0].content == "hi"
            assert t.agent_name == "bot"  # inherited from session
            t.end()
            assert get_current_turn() is None
        finally:
            s.end()

    def test_start_turn_without_session_returns_disconnected(self) -> None:
        t = start_turn(user_message="hi", agent_name="standalone")
        assert t.agent_name == "standalone"
        assert t.messages[0].content == "hi"
        assert get_current_turn() is None  # not set in contextvar

    def test_start_llm_sets_contextvar(self) -> None:
        s = start_session(agent_name="bot")
        try:
            t = start_turn()
            try:
                c = start_llm(model="gpt-4o")
                assert get_current_llm() is c
                assert c.model == "gpt-4o"
                c.end()
                assert get_current_llm() is None
            finally:
                t.end()
        finally:
            s.end()

    def test_start_llm_without_turn_returns_disconnected(self) -> None:
        c = start_llm(model="gpt-4o")
        assert c.model == "gpt-4o"
        assert get_current_llm() is None  # not set in contextvar

    def test_end_convenience_functions(self) -> None:
        s = start_session()
        start_turn()
        start_llm(model="gpt-4o")
        end_llm()
        assert get_current_llm() is None
        end_turn()
        assert get_current_turn() is None
        end_session()
        assert get_current_session() is None

    def test_end_when_nothing_active(self) -> None:
        # Should not raise
        end_llm()
        end_turn()
        end_session()

    def test_full_context_manager_pattern(self) -> None:
        with start_session(agent_name="weather-bot") as s:
            with s.start_turn(user_message="What's the weather?") as turn:
                with turn.llm(model="gpt-4o") as llm:
                    llm.output("Let me check.")
                    llm.usage = Usage(input_tokens=100, output_tokens=50)
                with turn.tool(
                    name="get_weather",
                    arguments='{"city":"Tokyo"}',
                    tool_call_id="tc_1",
                ) as tool:
                    tool.result = "75F"
                with turn.llm(model="gpt-4o") as llm:
                    llm.output("It's 75F in Tokyo!")

        assert get_current_session() is None
        assert get_current_turn() is None
        assert get_current_llm() is None


class TestBatchLogging:
    def test_log_turn_returns_log_result(self) -> None:
        result = log_turn(
            session_id="sess-123",
            messages=[{"role": "user", "content": "hi"}],
            spans=[
                LLM(
                    model="gpt-4o",
                    output_messages=[Message(role="assistant", content="hello")],
                ),
                Tool(name="search", result="found"),
            ],
            agent_name="bot",
            model="gpt-4o",
        )
        assert isinstance(result, LogResult)
        assert result.session_id == "sess-123"

    def test_log_session_returns_log_result(self) -> None:
        result = log_session(
            turns=[{"messages": [{"role": "user", "content": "hi"}]}],
            agent_name="bot",
            model="gpt-4o",
            session_id="sess-456",
        )
        assert isinstance(result, LogResult)
        assert result.session_id == "sess-456"

    def test_log_session_auto_generates_session_id(self) -> None:
        result = log_session(turns=[], agent_name="bot")
        assert result.session_id != ""


# ---------------------------------------------------------------------------
# OTel span emission
# ---------------------------------------------------------------------------

from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture
def otel_spans():
    """Provide an in-memory span exporter for capturing OTel spans."""
    from weave.session import otel_setup

    exporter = InMemorySpanExporter()
    provider = SDKTracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    otel_setup._provider = provider
    yield exporter
    provider.shutdown()
    otel_setup._provider = None


class TestOTelSpanEmission:
    def test_turn_creates_invoke_agent_span(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(agent_name="weather-bot", session_id="sess-1", session_name="Weather Chat") as s:
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
        with Session(agent_name="bot") as s:
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
        assert attrs["gen_ai.usage.input_tokens"] == 100
        assert attrs["gen_ai.usage.output_tokens"] == 50

    def test_tool_creates_execute_tool_span(self, otel_spans: InMemorySpanExporter) -> None:
        with Session(agent_name="bot") as s:
            with s.start_turn() as turn:
                with turn.tool(name="get_weather", arguments='{"city":"Tokyo"}', tool_call_id="tc_1") as tool:
                    tool.result = "75F"

        spans = otel_spans.get_finished_spans()
        tool_spans = [sp for sp in spans if sp.name == "execute_tool get_weather"]
        assert len(tool_spans) == 1
        attrs = dict(tool_spans[0].attributes or {})
        assert attrs["gen_ai.operation.name"] == "execute_tool"
        assert attrs["gen_ai.tool.name"] == "get_weather"
        assert attrs["gen_ai.tool.call.id"] == "tc_1"
        assert attrs["gen_ai.tool.call.arguments"] == '{"city":"Tokyo"}'
        assert attrs["gen_ai.tool.call.result"] == "75F"

    def test_subagent_creates_nested_invoke_agent_span(self, otel_spans: InMemorySpanExporter) -> None:
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

    def test_no_spans_without_setup(self) -> None:
        """No errors when no provider configured (no-op spans)."""
        from weave.session import otel_setup

        original = otel_setup._provider
        otel_setup._provider = None
        try:
            with Session(agent_name="bot") as s:
                with s.start_turn() as turn:
                    with turn.llm(model="gpt-4o") as llm:
                        llm.output("Hello")
                    with turn.tool(name="search") as tool:
                        tool.result = "done"
            # Should not raise — just silently use no-op spans
        finally:
            otel_setup._provider = original

    def test_include_content_false_omits_messages(self, otel_spans: InMemorySpanExporter) -> None:
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

from opentelemetry.trace import StatusCode


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
        chat_span = [s for s in spans if s.attributes.get("gen_ai.operation.name") == "chat"][0]
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
        tool_span = [s for s in spans if s.attributes.get("gen_ai.operation.name") == "execute_tool"][0]
        assert tool_span.status.status_code == StatusCode.ERROR

    def test_turn_records_exception(self, otel_spans: InMemorySpanExporter) -> None:
        with start_session(agent_name="bot") as session:
            try:
                with session.start_turn() as turn:
                    raise RuntimeError("turn broke")
            except RuntimeError:
                pass
        spans = otel_spans.get_finished_spans()
        turn_span = [s for s in spans if s.attributes.get("gen_ai.operation.name") == "invoke_agent"][0]
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
