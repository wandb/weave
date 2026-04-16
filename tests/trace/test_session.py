"""Tests for weave.start_session / log_session / log_turn / log_step."""

from __future__ import annotations

import json

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from weave.trace.session import (
    LogResult,
    Message,
    Reasoning,
    Session,
    Step,
    Tool,
    Turn,
    Usage,
    log_session,
    log_step,
    log_turn,
    start_session,
    start_step,
    start_turn,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def otel_setup():
    """Create an OTel TracerProvider + InMemorySpanExporter for testing."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


# ===========================================================================
# OTel mode tests
# ===========================================================================


class TestOtelTurnSpan:
    """Turn emits invoke_agent span with correct attributes."""

    def test_turn_emits_invoke_agent_span(self, otel_setup):
        provider, exporter = otel_setup
        session = start_session(
            agent_name="weather-bot",
            session_id="sess-1",
            _tracer_provider=provider,
        )
        with session.start_turn() as turn:
            turn.user("What's the weather?")
            with turn.start_step(model="gpt-4o") as step:
                step.output_messages.append(
                    Message(role="assistant", content="It's sunny!")
                )
                step.usage = Usage(input_tokens=10, output_tokens=5)
        session.end()

        spans = exporter.get_finished_spans()
        # Should have 2 spans: chat + invoke_agent (finished order)
        assert len(spans) == 2

        # Find the invoke_agent span
        invoke_spans = [s for s in spans if s.name == "invoke_agent"]
        assert len(invoke_spans) == 1
        invoke_span = invoke_spans[0]

        # Check attributes
        attrs = dict(invoke_span.attributes)
        assert attrs["gen_ai.operation.name"] == "invoke_agent"
        assert attrs["gen_ai.agent.name"] == "weather-bot"
        assert attrs["gen_ai.conversation.id"] == "sess-1"

    def test_turn_aggregates_token_usage(self, otel_setup):
        provider, exporter = otel_setup
        session = start_session(agent_name="bot", _tracer_provider=provider)
        with session.start_turn() as turn:
            turn.user("Hi")
            with turn.start_step(model="gpt-4o") as step1:
                step1.usage = Usage(input_tokens=100, output_tokens=50)
                step1.output_messages.append(
                    Message(role="assistant", content="Step 1")
                )
            with turn.start_step(model="gpt-4o") as step2:
                step2.usage = Usage(input_tokens=200, output_tokens=100)
                step2.output_messages.append(
                    Message(role="assistant", content="Step 2")
                )
        session.end()

        spans = exporter.get_finished_spans()
        invoke_span = next(s for s in spans if s.name == "invoke_agent")
        attrs = dict(invoke_span.attributes)

        # Token counts aggregated from both steps
        assert attrs["gen_ai.usage.input_tokens"] == 300
        assert attrs["gen_ai.usage.output_tokens"] == 150

    def test_turn_has_input_and_output_messages(self, otel_setup):
        provider, exporter = otel_setup
        session = start_session(agent_name="bot", _tracer_provider=provider)
        with session.start_turn() as turn:
            turn.user("Hello")
            with turn.start_step(model="gpt-4o") as step:
                step.output_messages.append(
                    Message(role="assistant", content="Hi there!")
                )
                step.usage = Usage(input_tokens=5, output_tokens=3)
        session.end()

        spans = exporter.get_finished_spans()
        invoke_span = next(s for s in spans if s.name == "invoke_agent")
        attrs = dict(invoke_span.attributes)

        # Input messages = user messages on the turn
        input_msgs = json.loads(attrs["gen_ai.input.messages"])
        assert len(input_msgs) == 1
        assert input_msgs[0]["role"] == "user"
        assert input_msgs[0]["content"] == "Hello"

        # Output messages = aggregated from steps
        output_msgs = json.loads(attrs["gen_ai.output.messages"])
        assert len(output_msgs) == 1
        assert output_msgs[0]["role"] == "assistant"
        assert output_msgs[0]["content"] == "Hi there!"


class TestOtelStepSpan:
    """Step emits chat span as child of invoke_agent."""

    def test_step_emits_chat_span(self, otel_setup):
        provider, exporter = otel_setup
        session = start_session(agent_name="bot", _tracer_provider=provider)
        with session.start_turn() as turn:
            turn.user("Hi")
            with turn.start_step(model="gpt-4o") as step:
                step.usage = Usage(input_tokens=10, output_tokens=5)
                step.output_messages.append(Message(role="assistant", content="Hello!"))
        session.end()

        spans = exporter.get_finished_spans()
        chat_spans = [s for s in spans if s.name == "chat"]
        assert len(chat_spans) == 1

        chat_span = chat_spans[0]
        attrs = dict(chat_span.attributes)
        assert attrs["gen_ai.operation.name"] == "chat"
        assert attrs["gen_ai.request.model"] == "gpt-4o"
        assert attrs["gen_ai.usage.input_tokens"] == 10
        assert attrs["gen_ai.usage.output_tokens"] == 5

    def test_step_is_child_of_turn(self, otel_setup):
        provider, exporter = otel_setup
        session = start_session(agent_name="bot", _tracer_provider=provider)
        with session.start_turn() as turn:
            turn.user("Hi")
            with turn.start_step(model="gpt-4o") as step:
                step.output_messages.append(Message(role="assistant", content="Hey"))
        session.end()

        spans = exporter.get_finished_spans()
        chat_span = next(s for s in spans if s.name == "chat")
        invoke_span = next(s for s in spans if s.name == "invoke_agent")

        # chat is child of invoke_agent
        assert chat_span.parent is not None
        assert chat_span.parent.span_id == invoke_span.get_span_context().span_id

        # Same trace_id
        assert (
            chat_span.get_span_context().trace_id
            == invoke_span.get_span_context().trace_id
        )

    def test_step_has_chat_messages(self, otel_setup):
        provider, exporter = otel_setup
        session = start_session(agent_name="bot", _tracer_provider=provider)
        with session.start_turn() as turn:
            turn.user("Hi")
            with turn.start_step(model="gpt-4o") as step:
                step.input_messages.append(Message(role="user", content="Hi"))
                step.output_messages.append(Message(role="assistant", content="Hello!"))
        session.end()

        spans = exporter.get_finished_spans()
        chat_span = next(s for s in spans if s.name == "chat")
        attrs = dict(chat_span.attributes)

        input_msgs = json.loads(attrs["gen_ai.input.messages"])
        assert input_msgs[0]["role"] == "user"

        output_msgs = json.loads(attrs["gen_ai.output.messages"])
        assert output_msgs[0]["role"] == "assistant"


class TestOtelToolSpan:
    """Tool emits execute_tool span as child of chat."""

    def test_tool_emits_execute_tool_span(self, otel_setup):
        provider, exporter = otel_setup
        session = start_session(agent_name="bot", _tracer_provider=provider)
        with session.start_turn() as turn:
            turn.user("Search for X")
            with turn.start_step(model="gpt-4o") as step:
                with step.start_tool(name="search", arguments='{"q":"X"}') as tool:
                    tool.result = "found it"
                step.output_messages.append(
                    Message(role="assistant", content="Found it!")
                )
        session.end()

        spans = exporter.get_finished_spans()
        tool_spans = [s for s in spans if s.name == "execute_tool"]
        assert len(tool_spans) == 1

        tool_span = tool_spans[0]
        attrs = dict(tool_span.attributes)
        assert attrs["gen_ai.operation.name"] == "execute_tool"
        assert attrs["gen_ai.tool.name"] == "search"
        assert attrs["gen_ai.tool.call.arguments"] == '{"q":"X"}'
        assert attrs["gen_ai.tool.call.result"] == "found it"

    def test_tool_is_child_of_step(self, otel_setup):
        provider, exporter = otel_setup
        session = start_session(agent_name="bot", _tracer_provider=provider)
        with session.start_turn() as turn:
            turn.user("Do it")
            with turn.start_step(model="gpt-4o") as step:
                with step.start_tool(name="my_tool") as tool:
                    tool.result = "done"
                step.output_messages.append(Message(role="assistant", content="Done!"))
        session.end()

        spans = exporter.get_finished_spans()
        tool_span = next(s for s in spans if s.name == "execute_tool")
        chat_span = next(s for s in spans if s.name == "chat")

        # execute_tool is child of chat
        assert tool_span.parent is not None
        assert tool_span.parent.span_id == chat_span.get_span_context().span_id

        # Same trace_id
        assert (
            tool_span.get_span_context().trace_id
            == chat_span.get_span_context().trace_id
        )


class TestOtelSpanHierarchy:
    """Full hierarchy and trace isolation tests."""

    def test_multiple_steps_share_trace_id(self, otel_setup):
        provider, exporter = otel_setup
        session = start_session(agent_name="bot", _tracer_provider=provider)
        with session.start_turn() as turn:
            turn.user("Q")
            with turn.start_step(model="gpt-4o") as step1:
                step1.output_messages.append(Message(role="assistant", content="A1"))
            with turn.start_step(model="gpt-4o") as step2:
                step2.output_messages.append(Message(role="assistant", content="A2"))
        session.end()

        spans = exporter.get_finished_spans()
        chat_spans = [s for s in spans if s.name == "chat"]
        assert len(chat_spans) == 2

        # Both chat spans share the same trace_id
        assert (
            chat_spans[0].get_span_context().trace_id
            == chat_spans[1].get_span_context().trace_id
        )

    def test_separate_turns_get_separate_trace_ids(self, otel_setup):
        provider, exporter = otel_setup
        session = start_session(agent_name="bot", _tracer_provider=provider)

        # Turn 1
        with session.start_turn() as turn1:
            turn1.user("Q1")
            with turn1.start_step(model="gpt-4o") as step1:
                step1.output_messages.append(Message(role="assistant", content="A1"))

        # Turn 2
        with session.start_turn() as turn2:
            turn2.user("Q2")
            with turn2.start_step(model="gpt-4o") as step2:
                step2.output_messages.append(Message(role="assistant", content="A2"))

        session.end()

        spans = exporter.get_finished_spans()
        invoke_spans = [s for s in spans if s.name == "invoke_agent"]
        assert len(invoke_spans) == 2

        # Different trace_ids
        assert (
            invoke_spans[0].get_span_context().trace_id
            != invoke_spans[1].get_span_context().trace_id
        )

    def test_conversation_id_propagated_to_all_spans(self, otel_setup):
        provider, exporter = otel_setup
        session = start_session(
            agent_name="bot",
            session_id="conv-abc",
            session_name="My Conversation",
            _tracer_provider=provider,
        )
        with session.start_turn() as turn:
            turn.user("Hi")
            with turn.start_step(model="gpt-4o") as step:
                with step.start_tool(name="tool1") as tool:
                    tool.result = "ok"
                step.output_messages.append(Message(role="assistant", content="Done"))
        session.end()

        spans = exporter.get_finished_spans()
        assert len(spans) == 3

        # All spans should have conversation_id and conversation_name
        for span in spans:
            attrs = dict(span.attributes)
            assert attrs["gen_ai.conversation.id"] == "conv-abc", (
                f"Span '{span.name}' missing gen_ai.conversation.id"
            )
            assert attrs["gen_ai.conversation.name"] == "My Conversation", (
                f"Span '{span.name}' missing gen_ai.conversation.name"
            )

    def test_full_hierarchy_three_levels(self, otel_setup):
        """invoke_agent -> chat -> execute_tool full hierarchy."""
        provider, exporter = otel_setup
        session = start_session(agent_name="bot", _tracer_provider=provider)
        with session.start_turn() as turn:
            turn.user("Do work")
            with turn.start_step(model="gpt-4o") as step:
                with step.start_tool(name="calc") as tool:
                    tool.result = "42"
                step.output_messages.append(Message(role="assistant", content="42"))
        session.end()

        spans = exporter.get_finished_spans()
        assert len(spans) == 3

        tool_span = next(s for s in spans if s.name == "execute_tool")
        chat_span = next(s for s in spans if s.name == "chat")
        invoke_span = next(s for s in spans if s.name == "invoke_agent")

        # All same trace
        trace_id = invoke_span.get_span_context().trace_id
        assert chat_span.get_span_context().trace_id == trace_id
        assert tool_span.get_span_context().trace_id == trace_id

        # Hierarchy: invoke_agent (root) -> chat -> execute_tool
        assert invoke_span.parent is None
        assert chat_span.parent.span_id == invoke_span.get_span_context().span_id
        assert tool_span.parent.span_id == chat_span.get_span_context().span_id


class TestOtelSpanKinds:
    """Verify correct SpanKind for each span type."""

    def test_span_kinds(self, otel_setup):
        from opentelemetry.trace import SpanKind

        provider, exporter = otel_setup
        session = start_session(agent_name="bot", _tracer_provider=provider)
        with session.start_turn() as turn:
            turn.user("Hi")
            with turn.start_step(model="gpt-4o") as step:
                with step.start_tool(name="t") as tool:
                    tool.result = "r"
                step.output_messages.append(Message(role="assistant", content="Done"))
        session.end()

        spans = exporter.get_finished_spans()
        invoke_span = next(s for s in spans if s.name == "invoke_agent")
        chat_span = next(s for s in spans if s.name == "chat")
        tool_span = next(s for s in spans if s.name == "execute_tool")

        assert invoke_span.kind == SpanKind.INTERNAL
        assert chat_span.kind == SpanKind.CLIENT
        assert tool_span.kind == SpanKind.INTERNAL


class TestOtelManualEnd:
    """Manual .end() works same as context manager for OTel."""

    def test_manual_end_emits_spans(self, otel_setup):
        provider, exporter = otel_setup
        session = start_session(
            agent_name="bot",
            session_id="manual-sess",
            _tracer_provider=provider,
        )
        turn = session.start_turn()
        turn.user("Hello")

        step = turn.start_step(model="gpt-4o")
        step.output_messages.append(Message(role="assistant", content="Hi!"))
        step.usage = Usage(input_tokens=10, output_tokens=5)

        tool = step.start_tool(name="calc", arguments='{"x": 1}')
        tool.result = "42"
        tool.end()

        step.end()
        turn.end()
        session.end()

        spans = exporter.get_finished_spans()
        assert len(spans) == 3

        names = {s.name for s in spans}
        assert names == {"invoke_agent", "chat", "execute_tool"}

    def test_double_end_is_safe(self, otel_setup):
        provider, exporter = otel_setup
        session = start_session(agent_name="bot", _tracer_provider=provider)
        turn = session.start_turn()
        turn.user("Hi")
        step = turn.start_step(model="gpt-4o")
        step.output_messages.append(Message(role="assistant", content="Hey"))
        step.end()
        step.end()  # no-op

        turn.end()
        turn.end()  # no-op
        session.end()
        session.end()  # no-op

        spans = exporter.get_finished_spans()
        # Should still only have 2 spans (chat + invoke_agent), not duplicates
        assert len(spans) == 2


def test_otel_mode_does_not_require_init(otel_setup):
    """OTel mode with _tracer_provider does NOT require weave.init()."""
    provider, exporter = otel_setup
    # Should not raise even without weave.init()
    session = start_session(agent_name="bot", _tracer_provider=provider)
    assert isinstance(session, Session)
    session.end()


class TestTopLevelStartTurn:
    """weave.start_turn() reads session from contextvar."""

    def test_start_turn_with_active_session(self, otel_setup):
        provider, exporter = otel_setup
        with start_session(agent_name="bot", _tracer_provider=provider):
            with start_turn() as turn:
                turn.user("Hello")
                with start_step(model="gpt-4o") as step:
                    step.usage = Usage(input_tokens=10, output_tokens=5)
                    step.output_messages.append(
                        Message(role="assistant", content="Hi!")
                    )

        spans = exporter.get_finished_spans()
        names = {s.name for s in spans}
        assert "invoke_agent" in names
        assert "chat" in names

    def test_start_turn_without_session_returns_disconnected_turn(self):
        """No active session — returns a Turn that works but emits no spans."""
        turn = start_turn(agent_name="bot")
        assert isinstance(turn, Turn)
        turn.user("Hello")
        turn.end()  # should not crash

    def test_start_turn_separate_traces(self, otel_setup):
        provider, exporter = otel_setup
        with start_session(agent_name="bot", _tracer_provider=provider):
            with start_turn() as t1:
                t1.user("Hello")
                with start_step(model="gpt-4o") as s:
                    s.output_messages.append(Message(role="assistant", content="Hi!"))
            with start_turn() as t2:
                t2.user("Bye")
                with start_step(model="gpt-4o") as s:
                    s.output_messages.append(
                        Message(role="assistant", content="Goodbye!")
                    )

        spans = exporter.get_finished_spans()
        invoke_spans = [s for s in spans if s.name == "invoke_agent"]
        assert len(invoke_spans) == 2
        assert invoke_spans[0].context.trace_id != invoke_spans[1].context.trace_id


class TestTopLevelStartStep:
    """weave.start_step() reads turn from contextvar."""

    def test_start_step_with_active_turn(self, otel_setup):
        provider, exporter = otel_setup
        with start_session(agent_name="bot", _tracer_provider=provider):
            with start_turn() as turn:
                turn.user("Hello")
                with start_step(model="gpt-4o") as step:
                    step.usage = Usage(input_tokens=10, output_tokens=5)
                    step.output_messages.append(
                        Message(role="assistant", content="Hi!")
                    )

        spans = exporter.get_finished_spans()
        names = {s.name for s in spans}
        assert "chat" in names
        assert "invoke_agent" in names

        # chat should be child of invoke_agent
        chat = next(s for s in spans if s.name == "chat")
        invoke = next(s for s in spans if s.name == "invoke_agent")
        assert chat.parent.span_id == invoke.context.span_id

    def test_start_step_without_turn_returns_disconnected_step(self):
        """No active turn — returns a Step that works but emits no spans."""
        step = start_step(model="gpt-4o")
        assert isinstance(step, Step)
        step.usage = Usage(input_tokens=10, output_tokens=5)
        step.end()  # should not crash

    def test_start_step_with_tool(self, otel_setup):
        provider, exporter = otel_setup
        with start_session(agent_name="bot", _tracer_provider=provider):
            with start_turn() as turn:
                turn.user("Hello")
                with start_step(model="gpt-4o") as step:
                    with step.start_tool(name="calc", arguments="1+1") as tool:
                        tool.result = "2"

        spans = exporter.get_finished_spans()
        names = {s.name for s in spans}
        assert "execute_tool" in names
        assert "chat" in names
        assert "invoke_agent" in names


class TestFullTopLevelAPI:
    """All top-level functions work together."""

    def test_full_flow(self, otel_setup):
        provider, exporter = otel_setup
        with start_session(
            agent_name="bot", session_id="s1", _tracer_provider=provider
        ):
            with start_turn() as turn:
                turn.user("What is 2+2?")
                with start_step(model="gpt-4o") as step:
                    step.usage = Usage(input_tokens=10, output_tokens=5)
                    step.output_messages.append(
                        Message(role="assistant", content="Let me calculate.")
                    )
                    with step.start_tool(name="calc", arguments="2+2") as tool:
                        tool.result = "4"
                with start_step(model="gpt-4o") as step:
                    step.usage = Usage(input_tokens=15, output_tokens=3)
                    step.output_messages.append(Message(role="assistant", content="4"))

        spans = exporter.get_finished_spans()
        assert len(spans) == 4  # invoke_agent, chat, execute_tool, chat
        names = [s.name for s in spans]
        assert names.count("chat") == 2
        assert "invoke_agent" in names
        assert "execute_tool" in names


def test_context_manager_full(otel_setup):
    provider, exporter = otel_setup
    with start_session(agent_name="weather-bot", _tracer_provider=provider) as session:
        assert isinstance(session, Session)
        assert session.agent_name == "weather-bot"
        assert session.session_id  # auto-generated

        with session.start_turn() as turn:
            assert isinstance(turn, Turn)
            turn.user("What's the weather?")

            with turn.start_step(model="gpt-4o") as step:
                assert isinstance(step, Step)
                step.usage = Usage(input_tokens=100, output_tokens=50)
                step.output_messages.append(
                    Message(role="assistant", content="Let me check.")
                )

                with step.start_tool(
                    name="get_weather", arguments='{"city":"Tokyo"}'
                ) as tool:
                    assert isinstance(tool, Tool)
                    tool.result = "75F"

                step.output_messages.append(
                    Message(role="tool", content="75F", tool_name="get_weather")
                )

            with turn.start_step(model="gpt-4o") as step2:
                step2.output_messages.append(
                    Message(role="assistant", content="It's 75F in Tokyo.")
                )
                step2.usage = Usage(input_tokens=150, output_tokens=20)

    spans = exporter.get_finished_spans()
    # 1 invoke_agent + 2 chat + 1 execute_tool = 4 spans
    assert len(spans) == 4

    invoke_span = next(s for s in spans if s.name == "invoke_agent")
    chat_spans = [s for s in spans if s.name == "chat"]
    tool_spans = [s for s in spans if s.name == "execute_tool"]

    assert len(chat_spans) == 2
    assert len(tool_spans) == 1

    # Tool attributes
    tool_attrs = dict(tool_spans[0].attributes)
    assert tool_attrs["gen_ai.tool.name"] == "get_weather"
    assert tool_attrs["gen_ai.tool.call.result"] == "75F"

    # Aggregated token usage on invoke_agent
    invoke_attrs = dict(invoke_span.attributes)
    assert invoke_attrs["gen_ai.usage.input_tokens"] == 250
    assert invoke_attrs["gen_ai.usage.output_tokens"] == 70


def test_model_inherits_from_session(otel_setup):
    """Step model should fall back to turn model, then session model."""
    provider, exporter = otel_setup
    session = start_session(agent_name="bot", model="gpt-4o", _tracer_provider=provider)
    turn = session.start_turn()
    turn.user("Hi")

    step = turn.start_step()  # no model specified
    step.output_messages.append(Message(role="assistant", content="Hey"))
    step.end()

    turn.end()
    session.end()

    spans = exporter.get_finished_spans()
    chat_span = next(s for s in spans if s.name == "chat")
    assert dict(chat_span.attributes)["gen_ai.request.model"] == "gpt-4o"


def test_session_end_closes_open_turn(otel_setup):
    provider, exporter = otel_setup
    session = start_session(agent_name="bot", _tracer_provider=provider)
    turn = session.start_turn()
    turn.user("Hi")

    step = turn.start_step(model="gpt-4o")
    step.output_messages.append(Message(role="assistant", content="Hey"))
    step.end()

    # Don't explicitly end turn -- session.end() should do it
    session.end()

    spans = exporter.get_finished_spans()
    assert len(spans) == 2  # chat + invoke_agent


def test_new_turn_ends_previous(otel_setup):
    """Starting a new turn should end the previous one."""
    provider, exporter = otel_setup
    session = start_session(agent_name="bot", _tracer_provider=provider)

    turn1 = session.start_turn()
    turn1.user("First question")

    turn2 = session.start_turn()  # should auto-end turn1
    assert turn1._ended

    turn2.user("Second question")
    step = turn2.start_step(model="gpt-4o")
    step.output_messages.append(Message(role="assistant", content="Answer"))
    step.end()
    turn2.end()
    session.end()

    spans = exporter.get_finished_spans()
    invoke_spans = [s for s in spans if s.name == "invoke_agent"]
    assert len(invoke_spans) == 2  # both turns got spans


# ---------------------------------------------------------------------------
# Pydantic serialization
# ---------------------------------------------------------------------------


def test_step_model_dump(otel_setup):
    """Step should serialize cleanly via model_dump()."""
    provider, exporter = otel_setup
    session = start_session(agent_name="bot", _tracer_provider=provider)
    turn = session.start_turn()
    turn.user("Hi")

    step = turn.start_step(model="gpt-4o")
    step.usage = Usage(input_tokens=100, output_tokens=50, reasoning_tokens=10)
    step.reasoning = Reasoning(content="thinking...")
    step.output_messages.append(Message(role="assistant", content="Hello!"))
    step.input_messages.append(Message(role="user", content="Hi"))

    data = step.model_dump()
    assert data["model"] == "gpt-4o"
    assert data["usage"]["input_tokens"] == 100
    assert data["usage"]["reasoning_tokens"] == 10
    assert data["reasoning"]["content"] == "thinking..."

    # Private attrs should NOT appear in model_dump
    assert "_turn" not in data
    assert "_ended" not in data
    assert "_otel_span" not in data

    step.end()
    turn.end()
    session.end()


def test_tool_model_dump():
    """Tool should serialize cleanly via model_dump()."""
    tool = Tool(name="search", arguments='{"q":"test"}', result="found", duration_ms=42)
    data = tool.model_dump()
    assert data["name"] == "search"
    assert data["result"] == "found"
    assert data["duration_ms"] == 42
    assert "_started_at" not in data
    assert "_ended" not in data


# ---------------------------------------------------------------------------
# Imperative batch: log_session / log_turn / log_step (OTel path)
# ---------------------------------------------------------------------------


def test_log_session(otel_setup):
    provider, exporter = otel_setup
    result = log_session(
        agent_name="bot",
        turns=[
            {
                "messages": [
                    {"role": "user", "content": "Hi"},
                    {"role": "assistant", "content": "Hello!"},
                ],
                "model": "gpt-4o",
                "steps": [
                    {
                        "model": "gpt-4o",
                        "output_messages": [{"role": "assistant", "content": "Hello!"}],
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "tool_calls": [
                            {"tool_name": "greet", "arguments": "{}", "result": "hi"},
                        ],
                    }
                ],
            }
        ],
        _tracer_provider=provider,
    )

    assert isinstance(result, LogResult)
    assert result.session_id  # auto-generated
    assert len(result.trace_ids) == 1
    assert len(result.root_span_ids) == 1
    # 1 invoke_agent + 1 chat + 1 execute_tool = 3
    assert result.span_count == 3

    spans = exporter.get_finished_spans()
    assert len(spans) == 3

    invoke_spans = [s for s in spans if s.name == "invoke_agent"]
    chat_spans = [s for s in spans if s.name == "chat"]
    tool_spans = [s for s in spans if s.name == "execute_tool"]
    assert len(invoke_spans) == 1
    assert len(chat_spans) == 1
    assert len(tool_spans) == 1

    # Check invoke_agent attributes
    invoke_attrs = dict(invoke_spans[0].attributes)
    assert invoke_attrs["gen_ai.operation.name"] == "invoke_agent"
    assert invoke_attrs["gen_ai.agent.name"] == "bot"
    assert invoke_attrs["gen_ai.usage.input_tokens"] == 10
    assert invoke_attrs["gen_ai.usage.output_tokens"] == 5

    # Check chat attributes
    chat_attrs = dict(chat_spans[0].attributes)
    assert chat_attrs["gen_ai.request.model"] == "gpt-4o"
    assert chat_attrs["gen_ai.usage.input_tokens"] == 10
    assert chat_attrs["gen_ai.usage.output_tokens"] == 5

    # Check tool attributes
    tool_attrs = dict(tool_spans[0].attributes)
    assert tool_attrs["gen_ai.tool.name"] == "greet"
    assert tool_attrs["gen_ai.tool.call.result"] == "hi"

    # Check hierarchy: chat is child of invoke_agent, tool is child of chat
    assert chat_spans[0].parent is not None
    assert chat_spans[0].parent.span_id == invoke_spans[0].get_span_context().span_id
    assert tool_spans[0].parent is not None
    assert tool_spans[0].parent.span_id == chat_spans[0].get_span_context().span_id


def test_log_session_custom_id(otel_setup):
    provider, exporter = otel_setup
    result = log_session(
        session_id="my-session",
        turns=[{"messages": [{"role": "user", "content": "Hi"}]}],
        _tracer_provider=provider,
    )
    assert result.session_id == "my-session"

    spans = exporter.get_finished_spans()
    invoke_span = next(s for s in spans if s.name == "invoke_agent")
    assert dict(invoke_span.attributes)["gen_ai.conversation.id"] == "my-session"


def test_log_session_multiple_turns(otel_setup):
    provider, exporter = otel_setup
    result = log_session(
        agent_name="bot",
        turns=[
            {
                "messages": [{"role": "user", "content": "Q1"}],
                "steps": [
                    {
                        "model": "gpt-4o",
                        "output_messages": [{"role": "assistant", "content": "A1"}],
                    }
                ],
            },
            {
                "messages": [{"role": "user", "content": "Q2"}],
                "steps": [
                    {
                        "model": "gpt-4o",
                        "output_messages": [{"role": "assistant", "content": "A2"}],
                    }
                ],
            },
        ],
        _tracer_provider=provider,
    )

    assert len(result.trace_ids) == 2
    # Each turn gets a separate trace
    assert result.trace_ids[0] != result.trace_ids[1]

    spans = exporter.get_finished_spans()
    invoke_spans = [s for s in spans if s.name == "invoke_agent"]
    assert len(invoke_spans) == 2
    assert (
        invoke_spans[0].get_span_context().trace_id
        != invoke_spans[1].get_span_context().trace_id
    )


def test_log_turn(otel_setup):
    provider, exporter = otel_setup
    result = log_turn(
        session_id="session-1",
        messages=[{"role": "user", "content": "Hello"}],
        steps=[
            {
                "model": "gpt-4o",
                "output_messages": [{"role": "assistant", "content": "Hi!"}],
            }
        ],
        agent_name="bot",
        model="gpt-4o",
        _tracer_provider=provider,
    )

    assert isinstance(result, LogResult)
    assert result.session_id == "session-1"
    assert len(result.trace_ids) == 1

    spans = exporter.get_finished_spans()
    # 1 invoke_agent + 1 chat = 2
    assert len(spans) == 2

    invoke_span = next(s for s in spans if s.name == "invoke_agent")
    chat_span = next(s for s in spans if s.name == "chat")

    assert dict(invoke_span.attributes)["gen_ai.conversation.id"] == "session-1"
    assert dict(chat_span.attributes)["gen_ai.request.model"] == "gpt-4o"


def test_log_step(otel_setup):
    provider, exporter = otel_setup
    result = log_step(
        session_id="session-1",
        trace_id="trace-1",
        parent_span_id="span-1",
        model="gpt-4o",
        output_messages=[{"role": "assistant", "content": "Done!"}],
        input_tokens=50,
        output_tokens=25,
        tool_calls=[
            {"tool_name": "search", "arguments": '{"q":"test"}', "result": "found"}
        ],
        _tracer_provider=provider,
    )

    assert isinstance(result, LogResult)
    assert result.session_id == "session-1"

    spans = exporter.get_finished_spans()
    # 1 chat + 1 execute_tool = 2
    assert len(spans) == 2

    chat_span = next(s for s in spans if s.name == "chat")
    tool_span = next(s for s in spans if s.name == "execute_tool")

    chat_attrs = dict(chat_span.attributes)
    assert chat_attrs["gen_ai.request.model"] == "gpt-4o"
    assert chat_attrs["gen_ai.usage.input_tokens"] == 50
    assert chat_attrs["gen_ai.usage.output_tokens"] == 25
    assert chat_attrs["gen_ai.conversation.id"] == "session-1"

    tool_attrs = dict(tool_span.attributes)
    assert tool_attrs["gen_ai.tool.name"] == "search"
    assert tool_attrs["gen_ai.tool.call.arguments"] == '{"q":"test"}'
    assert tool_attrs["gen_ai.tool.call.result"] == "found"


# ---------------------------------------------------------------------------
# Error handling: flush failures are logged, not raised
# ---------------------------------------------------------------------------


def test_log_session_always_succeeds_with_otel(otel_setup):
    """OTel-based batch log always produces spans locally (no server dependency)."""
    provider, exporter = otel_setup
    result = log_session(
        turns=[{"messages": [{"role": "user", "content": "Hi"}]}],
        _tracer_provider=provider,
    )
    assert isinstance(result, LogResult)
    # OTel spans are created locally -- always succeeds
    assert len(result.trace_ids) == 1
    assert result.span_count == 1  # just invoke_agent, no steps


# ---------------------------------------------------------------------------
# Direct attribute assignment on Step
# ---------------------------------------------------------------------------


def test_step_direct_assignment(otel_setup):
    """Step fields should be set via direct assignment, not setter methods."""
    provider, exporter = otel_setup
    session = start_session(agent_name="bot", _tracer_provider=provider)
    turn = session.start_turn()
    turn.user("Hi")

    step = turn.start_step(model="gpt-4o")
    step.input_messages.append(Message(role="user", content="context message"))
    step.input_messages.append(Message(role="system", content="you are a bot"))
    step.output_messages.append(Message(role="assistant", content="hello!"))
    step.output_messages.append(
        Message(role="tool", content="result", tool_call_id="tc-1", tool_name="search")
    )
    step.usage = Usage(input_tokens=100, output_tokens=50, reasoning_tokens=10)
    step.reasoning = Reasoning(content="thinking about it")
    step.end()

    turn.end()
    session.end()

    spans = exporter.get_finished_spans()
    chat_span = next(s for s in spans if s.name == "chat")
    attrs = dict(chat_span.attributes)

    # Check messages
    input_msgs = json.loads(attrs["gen_ai.input.messages"])
    assert len(input_msgs) == 2
    assert input_msgs[0]["role"] == "user"
    assert input_msgs[1]["role"] == "system"

    output_msgs = json.loads(attrs["gen_ai.output.messages"])
    # Reasoning is encoded as an assistant message with parts[type=reasoning]
    reasoning_msgs = [
        m for m in output_msgs if m.get("role") == "assistant" and "parts" in m
    ]
    assert len(reasoning_msgs) == 1
    assert reasoning_msgs[0]["parts"][0]["content"] == "thinking about it"

    # Regular assistant and tool messages
    regular_assistant = [
        m for m in output_msgs if m.get("role") == "assistant" and "parts" not in m
    ]
    tool_msgs = [m for m in output_msgs if m.get("role") == "tool"]
    assert len(regular_assistant) == 1
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["tool_call_id"] == "tc-1"

    # Usage
    assert attrs["gen_ai.usage.input_tokens"] == 100
    assert attrs["gen_ai.usage.output_tokens"] == 50
    assert attrs["gen_ai.usage.reasoning_tokens"] == 10
