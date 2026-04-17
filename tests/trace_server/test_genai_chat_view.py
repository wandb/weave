"""Unit tests for genai_chat_view.py — the backend chat normalization module.

Tests use synthetic GenAISpanSchema fixtures that mimic the span structures
produced by real SDK instrumentations (OpenAI Agents v2, Google ADK).
"""

import datetime
import json

from weave.trace_server.genai_chat_view import (
    build_chat_messages,
    build_span_tree,
    build_trace_chat,
    find_user_prompt,
)
from weave.trace_server.trace_server_interface import GenAISpanSchema

_T0 = datetime.datetime(2025, 1, 1, 0, 0, 0)
_T1 = datetime.datetime(2025, 1, 1, 0, 0, 1)
_T2 = datetime.datetime(2025, 1, 1, 0, 0, 2)
_T3 = datetime.datetime(2025, 1, 1, 0, 0, 3)
_T4 = datetime.datetime(2025, 1, 1, 0, 0, 4)
_T5 = datetime.datetime(2025, 1, 1, 0, 0, 5)
_T6 = datetime.datetime(2025, 1, 1, 0, 0, 6)
_T7 = datetime.datetime(2025, 1, 1, 0, 0, 7)
_T8 = datetime.datetime(2025, 1, 1, 0, 0, 8)
_T9 = datetime.datetime(2025, 1, 1, 0, 0, 9)


def _span(
    span_id: str = "s1",
    parent_span_id: str = "",
    span_name: str = "",
    operation_name: str = "",
    agent_name: str = "",
    request_model: str = "",
    response_model: str = "",
    input_messages: str = "",
    output_messages: str = "",
    system_instructions: str = "",
    tool_name: str = "",
    tool_call_arguments: str = "",
    tool_call_result: str = "",
    status_code: str = "OK",
    input_tokens: int = 0,
    output_tokens: int = 0,
    content_refs: str = "",
    started_at: datetime.datetime | None = None,
    ended_at: datetime.datetime | None = None,
    provider_name: str = "",
    trace_id: str = "t1",
    attributes_dump: str = "",
) -> GenAISpanSchema:
    """Helper to create a GenAISpanSchema with sensible defaults."""
    return GenAISpanSchema(
        project_id="test/project",
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        span_name=span_name,
        operation_name=operation_name,
        agent_name=agent_name,
        request_model=request_model,
        response_model=response_model,
        input_messages=input_messages,
        output_messages=output_messages,
        system_instructions=system_instructions,
        tool_name=tool_name,
        tool_call_arguments=tool_call_arguments,
        tool_call_result=tool_call_result,
        status_code=status_code,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        content_refs=content_refs,
        started_at=started_at or _T0,
        ended_at=ended_at or _T1,
        provider_name=provider_name,
        attributes_dump=attributes_dump,
    )


def _openai_input_messages(text: str) -> str:
    return json.dumps([{"role": "user", "parts": [{"type": "text", "content": text}]}])


def _openai_output_messages(text: str) -> str:
    return json.dumps([{"role": "assistant", "parts": [{"type": "text", "content": text}]}])


def _google_input_messages(text: str) -> str:
    return json.dumps({"contents": [{"role": "user", "parts": [{"text": text}]}]})


def _google_output_messages(text: str) -> str:
    return json.dumps({"content": {"parts": [{"text": text}]}})


# ---------------------------------------------------------------------------
# build_span_tree
# ---------------------------------------------------------------------------


class TestBuildSpanTree:
    def test_single_root(self) -> None:
        spans = [_span(span_id="root")]
        tree = build_span_tree(spans)
        assert len(tree) == 1
        assert tree[0].span.span_id == "root"
        assert tree[0].children == []

    def test_parent_child(self) -> None:
        spans = [
            _span(span_id="root", started_at=_T0),
            _span(span_id="child", parent_span_id="root", started_at=_T1),
        ]
        tree = build_span_tree(spans)
        assert len(tree) == 1
        assert len(tree[0].children) == 1
        assert tree[0].children[0].span.span_id == "child"

    def test_orphan_becomes_root(self) -> None:
        spans = [_span(span_id="orphan", parent_span_id="missing_parent")]
        tree = build_span_tree(spans)
        assert len(tree) == 1
        assert tree[0].span.span_id == "orphan"

    def test_children_sorted_by_time(self) -> None:
        spans = [
            _span(span_id="root"),
            _span(span_id="c2", parent_span_id="root", started_at=_T2),
            _span(span_id="c1", parent_span_id="root", started_at=_T1),
        ]
        tree = build_span_tree(spans)
        children = tree[0].children
        assert children[0].span.span_id == "c1"
        assert children[1].span.span_id == "c2"


# ---------------------------------------------------------------------------
# find_user_prompt
# ---------------------------------------------------------------------------


class TestFindUserPrompt:
    def test_openai_invoke_agent(self) -> None:
        spans = [
            _span(
                operation_name="invoke_agent",
                input_messages=_openai_input_messages("Hello world"),
            )
        ]
        assert find_user_prompt(spans) == "Hello world"

    def test_google_format(self) -> None:
        spans = [
            _span(
                operation_name="generate_content",
                input_messages=_google_input_messages("Weather in Tokyo?"),
            )
        ]
        assert find_user_prompt(spans) == "Weather in Tokyo?"

    def test_multi_turn_returns_last_user_message(self) -> None:
        """Multi-turn: input_messages contains full history, we want last only."""
        history = json.dumps([
            {"role": "user", "parts": [{"type": "text", "content": "Turn 1"}]},
            {"role": "assistant", "parts": [{"type": "text", "content": "Response 1"}]},
            {"role": "user", "parts": [{"type": "text", "content": "Turn 2"}]},
        ])
        spans = [
            _span(operation_name="invoke_agent", input_messages=history)
        ]
        assert find_user_prompt(spans) == "Turn 2"

    def test_skips_tool_call_text(self) -> None:
        spans = [
            _span(
                span_id="s1",
                operation_name="invoke_agent",
                input_messages=json.dumps([
                    {"role": "user", "parts": [{"type": "text", "content": "ResponseFunctionToolCall(...)"}]}
                ]),
                started_at=_T0,
            ),
            _span(
                span_id="s2",
                operation_name="chat",
                input_messages=_openai_input_messages("Real question"),
                started_at=_T1,
            ),
        ]
        assert find_user_prompt(spans) == "Real question"

    def test_fallback_to_attributes_dump(self) -> None:
        spans = [
            _span(attributes_dump=json.dumps({"gen_ai.prompt": "From attrs"}))
        ]
        assert find_user_prompt(spans) == "From attrs"

    def test_empty_spans(self) -> None:
        assert find_user_prompt([]) == ""


# ---------------------------------------------------------------------------
# build_chat_messages — OpenAI patterns
# ---------------------------------------------------------------------------


class TestBuildChatMessagesOpenAI:
    def test_simple_agent_response(self) -> None:
        """Single invoke_agent with user input and assistant output."""
        spans = [
            _span(
                span_id="root",
                operation_name="invoke_agent",
                agent_name="Assistant",
                request_model="gpt-4o-mini",
                input_messages=_openai_input_messages("Hi there"),
                output_messages=_openai_output_messages("Hello! How can I help?"),
                started_at=_T0,
                ended_at=_T1,
            )
        ]
        msgs = build_chat_messages(spans)
        assert len(msgs) == 3
        assert msgs[0].type == "user_message"
        assert msgs[0].text == "Hi there"
        assert msgs[1].type == "agent_start"
        assert msgs[1].agent_name == "Assistant"
        assert msgs[2].type == "agent_message"
        assert "Hello" in msgs[2].text

    def test_tool_call(self) -> None:
        """invoke_agent > execute_tool pattern."""
        spans = [
            _span(
                span_id="root",
                operation_name="invoke_agent",
                agent_name="WeatherBot",
                input_messages=_openai_input_messages("Weather in Tokyo?"),
                output_messages=_openai_output_messages("It's clear, 75°F."),
                started_at=_T0,
                ended_at=_T3,
            ),
            _span(
                span_id="tool1",
                parent_span_id="root",
                operation_name="execute_tool",
                tool_name="get_weather",
                tool_call_arguments='{"city": "Tokyo"}',
                tool_call_result='"Clear, 75°F"',
                started_at=_T1,
                ended_at=_T2,
            ),
        ]
        msgs = build_chat_messages(spans)
        types = [m.type for m in msgs]
        assert "user_message" in types
        assert "agent_start" in types
        assert "tool_call" in types
        assert "agent_message" in types
        tool_msg = next(m for m in msgs if m.type == "tool_call")
        assert tool_msg.tool_name == "get_weather"

    def test_handoff(self) -> None:
        """Triage agent hands off to specialist."""
        spans = [
            _span(
                span_id="root",
                operation_name="invoke_agent",
                span_name="invoke_agent Agent workflow",
                input_messages=_openai_input_messages("What's the weather?"),
                started_at=_T0,
                ended_at=_T5,
            ),
            _span(
                span_id="triage",
                parent_span_id="root",
                operation_name="invoke_agent",
                agent_name="TriageAgent",
                request_model="gpt-4o-mini",
                started_at=_T1,
                ended_at=_T4,
            ),
            _span(
                span_id="handoff",
                parent_span_id="triage",
                operation_name="handoff",
                span_name="agent_handoff OpenAI Agent",
                started_at=_T2,
                ended_at=_T2,
            ),
            _span(
                span_id="weather",
                parent_span_id="root",
                operation_name="invoke_agent",
                agent_name="WeatherBot",
                output_messages=_openai_output_messages("Sunny!"),
                started_at=_T3,
                ended_at=_T5,
            ),
        ]
        msgs = build_chat_messages(spans)
        types = [m.type for m in msgs]
        assert "agent_handoff" in types
        assert "agent_start" in types
        agent_starts = [m for m in msgs if m.type == "agent_start"]
        agent_names = [m.agent_name for m in agent_starts]
        assert "TriageAgent" in agent_names
        assert "WeatherBot" in agent_names

    def test_transfer_to_tool_becomes_handoff(self) -> None:
        """execute_tool with transfer_to_* name renders as handoff."""
        spans = [
            _span(
                span_id="root",
                operation_name="invoke_agent",
                agent_name="Triage",
                input_messages=_openai_input_messages("Help me"),
                started_at=_T0,
                ended_at=_T2,
            ),
            _span(
                span_id="transfer",
                parent_span_id="root",
                operation_name="execute_tool",
                tool_name="transfer_to_weather_bot",
                started_at=_T1,
                ended_at=_T1,
            ),
        ]
        msgs = build_chat_messages(spans)
        handoffs = [m for m in msgs if m.type == "agent_handoff"]
        assert len(handoffs) == 1
        assert "weather_bot" in handoffs[0].text

    def test_chat_spans_skipped(self) -> None:
        """Chat spans under invoke_agent are walked but not rendered."""
        spans = [
            _span(
                span_id="root",
                operation_name="invoke_agent",
                agent_name="Bot",
                input_messages=_openai_input_messages("Hello"),
                output_messages=_openai_output_messages("Hi!"),
                started_at=_T0,
                ended_at=_T2,
            ),
            _span(
                span_id="chat1",
                parent_span_id="root",
                operation_name="chat",
                output_messages=_openai_output_messages("Hi!"),
                started_at=_T1,
                ended_at=_T2,
            ),
        ]
        msgs = build_chat_messages(spans)
        agent_msgs = [m for m in msgs if m.type == "agent_message"]
        assert len(agent_msgs) == 1

    def test_tool_call_noise_filtered(self) -> None:
        """Noise tool names like (merged) and transfer_to_agent are excluded."""
        spans = [
            _span(
                span_id="root",
                operation_name="invoke_agent",
                agent_name="Bot",
                input_messages=_openai_input_messages("Do stuff"),
                started_at=_T0,
                ended_at=_T3,
            ),
            _span(
                span_id="merged",
                parent_span_id="root",
                operation_name="execute_tool",
                tool_name="(merged)",
                started_at=_T1,
                ended_at=_T1,
            ),
            _span(
                span_id="real_tool",
                parent_span_id="root",
                operation_name="execute_tool",
                tool_name="calculator",
                tool_call_arguments='{"expr": "2+2"}',
                tool_call_result='"4"',
                started_at=_T2,
                ended_at=_T2,
            ),
        ]
        msgs = build_chat_messages(spans)
        tool_msgs = [m for m in msgs if m.type == "tool_call"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].tool_name == "calculator"

    def test_system_instructions_extracted(self) -> None:
        instructions = json.dumps([{"role": "system", "content": "You are a helper."}])
        spans = [
            _span(
                span_id="root",
                operation_name="invoke_agent",
                agent_name="Bot",
                system_instructions=instructions,
                input_messages=_openai_input_messages("Hi"),
                started_at=_T0,
                ended_at=_T1,
            )
        ]
        msgs = build_chat_messages(spans)
        agent_start = next(m for m in msgs if m.type == "agent_start")
        assert "helper" in agent_start.system_instructions

    def test_content_refs_passed_through(self) -> None:
        refs = json.dumps([{"digest": "abc123", "media_type": "image/png", "role": "output", "size_bytes": 1024}])
        spans = [
            _span(
                span_id="root",
                operation_name="invoke_agent",
                agent_name="Creative",
                input_messages=_openai_input_messages("Make art"),
                output_messages=_openai_output_messages("Here's your image!"),
                content_refs=refs,
                started_at=_T0,
                ended_at=_T1,
            )
        ]
        msgs = build_chat_messages(spans)
        agent_msg = next(m for m in msgs if m.type == "agent_message")
        parsed = json.loads(agent_msg.content_refs)
        assert parsed[0]["digest"] == "abc123"


# ---------------------------------------------------------------------------
# build_chat_messages — Google ADK patterns
# ---------------------------------------------------------------------------


class TestBuildChatMessagesGoogleADK:
    def test_simple_generate_content(self) -> None:
        """Google ADK: generate_content span with output."""
        spans = [
            _span(
                span_id="root",
                operation_name="invoke_agent",
                agent_name="WeatherAgent",
                input_messages=_google_input_messages("Weather in Tokyo?"),
                started_at=_T0,
                ended_at=_T3,
            ),
            _span(
                span_id="gen",
                parent_span_id="root",
                operation_name="generate_content",
                started_at=_T1,
                ended_at=_T2,
            ),
            _span(
                span_id="llm",
                parent_span_id="gen",
                operation_name="",
                output_messages=_google_output_messages("Clear, 75°F in Tokyo."),
                started_at=_T1,
                ended_at=_T2,
            ),
        ]
        msgs = build_chat_messages(spans)
        assert any(m.type == "user_message" for m in msgs)
        agent_msgs = [m for m in msgs if m.type == "agent_message"]
        assert len(agent_msgs) == 1
        assert "75°F" in agent_msgs[0].text

    def test_tool_call_under_generate_content(self) -> None:
        """Google ADK: execute_tool nested under generate_content."""
        spans = [
            _span(
                span_id="root",
                operation_name="invoke_agent",
                agent_name="Coordinator",
                input_messages=_google_input_messages("Calculate 2+2"),
                started_at=_T0,
                ended_at=_T4,
            ),
            _span(
                span_id="gen",
                parent_span_id="root",
                operation_name="generate_content",
                started_at=_T1,
                ended_at=_T3,
            ),
            _span(
                span_id="tool",
                parent_span_id="gen",
                operation_name="execute_tool",
                tool_name="calculator",
                tool_call_arguments='{"expression": "2+2"}',
                tool_call_result='"4"',
                started_at=_T2,
                ended_at=_T2,
            ),
        ]
        msgs = build_chat_messages(spans)
        tool_msgs = [m for m in msgs if m.type == "tool_call"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].tool_name == "calculator"

    def test_multi_turn_last_user_only(self) -> None:
        """Multi-turn Google ADK: only last user message shown."""
        history = json.dumps({
            "contents": [
                {"role": "user", "parts": [{"text": "Turn 1"}]},
                {"role": "model", "parts": [{"text": "Response 1"}]},
                {"role": "user", "parts": [{"text": "Turn 2 question"}]},
            ]
        })
        spans = [
            _span(
                operation_name="invoke_agent",
                agent_name="Bot",
                input_messages=history,
                output_messages=_google_output_messages("Turn 2 answer"),
                started_at=_T0,
                ended_at=_T1,
            )
        ]
        msgs = build_chat_messages(spans)
        user_msgs = [m for m in msgs if m.type == "user_message"]
        assert len(user_msgs) == 1
        assert user_msgs[0].text == "Turn 2 question"


# ---------------------------------------------------------------------------
# build_trace_chat (full response)
# ---------------------------------------------------------------------------


class TestBuildTraceChat:
    def test_metadata_populated(self) -> None:
        spans = [
            _span(
                span_id="root",
                operation_name="invoke_agent",
                agent_name="MyAgent",
                provider_name="openai",
                input_messages=_openai_input_messages("Hello"),
                output_messages=_openai_output_messages("Hi!"),
                started_at=_T0,
                ended_at=_T5,
            )
        ]
        res = build_trace_chat(spans, "trace123")
        assert res.trace_id == "trace123"
        assert res.root_span_name == "MyAgent"
        assert res.provider == "openai"
        assert res.total_duration_ms == 5000
        assert len(res.messages) > 0

    def test_empty_spans(self) -> None:
        res = build_trace_chat([], "t1")
        assert res.messages == []
        assert res.root_span_name == ""

    def test_duration_calculated(self) -> None:
        spans = [
            _span(
                span_id="root",
                operation_name="invoke_agent",
                agent_name="Bot",
                request_model="gpt-4o",
                input_messages=_openai_input_messages("Hi"),
                output_messages=_openai_output_messages("Hey"),
                started_at=_T0,
                ended_at=_T2,
            )
        ]
        msgs = build_chat_messages(spans)
        agent_msg = next(m for m in msgs if m.type == "agent_message")
        assert agent_msg.duration_ms == 2000


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_spans_returns_empty(self) -> None:
        assert build_chat_messages([]) == []

    def test_tool_call_output_filtered(self) -> None:
        """Output that looks like a tool call is not rendered as agent response."""
        spans = [
            _span(
                span_id="root",
                operation_name="invoke_agent",
                agent_name="Triage",
                input_messages=_openai_input_messages("Help"),
                output_messages=json.dumps([
                    {"role": "assistant", "parts": [{"type": "text", "content": "ResponseFunctionToolCall(arguments='{}')"}]}
                ]),
                started_at=_T0,
                ended_at=_T1,
            )
        ]
        msgs = build_chat_messages(spans)
        agent_msgs = [m for m in msgs if m.type == "agent_message"]
        assert len(agent_msgs) == 0

    def test_no_agent_name_no_agent_start(self) -> None:
        """invoke_agent without agent_name doesn't emit agent_start."""
        spans = [
            _span(
                span_id="root",
                operation_name="invoke_agent",
                span_name="invoke_agent Agent workflow",
                input_messages=_openai_input_messages("Hello"),
                started_at=_T0,
                ended_at=_T1,
            )
        ]
        msgs = build_chat_messages(spans)
        starts = [m for m in msgs if m.type == "agent_start"]
        assert len(starts) == 0

    def test_content_refs_python_repr_fixed(self) -> None:
        """Python-style repr (single quotes) in content_refs is normalized."""
        bad_refs = "[{'digest': 'abc', 'media_type': 'image/png', 'role': 'output', 'size_bytes': 100}]"
        spans = [
            _span(
                span_id="root",
                operation_name="execute_tool",
                tool_name="generate_image",
                content_refs=bad_refs,
                started_at=_T0,
                ended_at=_T1,
            )
        ]
        msgs = build_chat_messages(spans)
        tool_msg = next(m for m in msgs if m.type == "tool_call")
        parsed = json.loads(tool_msg.content_refs)
        assert parsed[0]["digest"] == "abc"
