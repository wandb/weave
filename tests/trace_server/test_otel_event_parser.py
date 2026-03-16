"""Tests for the generalized OTEL span-to-events parser (event_parser.py).

Each test exercises one real-world instrumentation source by feeding
hand-crafted Span objects that mirror what those libraries actually emit.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from weave.trace_server.opentelemetry.event_parser import (
    EventType,
    OtelEvent,
    OtelTrace,
    TokenUsage,
    _detect_event_type,
    _extract_inputs,
    _extract_output,
    _extract_usage,
    _normalise_messages,
    _normalise_pydantic_ai_messages,
    _system_instructions_to_msg,
    span_to_event,
    spans_to_traces,
)
from weave.trace_server.opentelemetry.python_spans import Event, Span, Status, StatusCode


# ---------------------------------------------------------------------------
# Helpers to build minimal Span objects
# ---------------------------------------------------------------------------


def _make_status(code: str = "UNSET", message: str = "") -> Status:
    status = Status()
    status.code = StatusCode[code]
    status.message = message
    return status


def _make_span(
    span_id: str,
    trace_id: str,
    name: str,
    attributes: dict[str, Any],
    parent_id: str | None = None,
    events: list[Event] | None = None,
    status_code: str = "UNSET",
    status_msg: str = "",
    start_ns: int = 1_000_000_000,
    end_ns: int = 2_000_000_000,
) -> Span:
    span = MagicMock(spec=Span)
    span.span_id = span_id
    span.trace_id = trace_id
    span.name = name
    span.attributes = attributes
    span.parent_id = parent_id
    span.events = events or []
    span.status = _make_status(status_code, status_msg)
    span.start_time_unix_nano = start_ns
    span.end_time_unix_nano = end_ns
    span.start_time = datetime.fromtimestamp(start_ns / 1e9)
    span.end_time = datetime.fromtimestamp(end_ns / 1e9)
    return span


def _make_event(name: str, attributes: dict[str, Any]) -> Event:
    evt = MagicMock(spec=Event)
    evt.name = name
    evt.attributes = attributes
    return evt


# ===========================================================================
# 1. Message normalisation helpers
# ===========================================================================


class TestNormaliseMessages:
    def test_plain_string(self):
        msgs = _normalise_messages("hello")
        assert msgs == [{"role": "user", "content": "hello"}]

    def test_json_string_list(self):
        raw = json.dumps([{"role": "user", "content": "hi"}])
        msgs = _normalise_messages(raw)
        assert msgs == [{"role": "user", "content": "hi"}]

    def test_logfire_v2_parts(self):
        raw = [
            {"role": "system", "parts": [{"type": "text", "content": "You are helpful"}]},
            {"role": "user", "parts": [{"type": "text", "content": "Hello"}]},
        ]
        msgs = _normalise_messages(raw)
        assert len(msgs) == 2
        assert msgs[0] == {"role": "system", "content": "You are helpful"}
        assert msgs[1] == {"role": "user", "content": "Hello"}

    def test_logfire_v2_tool_call_part(self):
        raw = [
            {
                "role": "assistant",
                "parts": [
                    {"type": "tool_call", "id": "tc1", "name": "search", "arguments": {"q": "cats"}}
                ],
            }
        ]
        msgs = _normalise_messages(raw)
        assert msgs[0]["role"] == "assistant"
        assert msgs[0]["tool_calls"] == [{"id": "tc1", "name": "search", "arguments": {"q": "cats"}}]

    def test_logfire_v2_tool_response_part(self):
        raw = [
            {
                "role": "tool",
                "name": "search",
                "parts": [{"type": "tool_call_response", "id": "tc1", "response": "Paris"}],
            }
        ]
        msgs = _normalise_messages(raw)
        assert msgs[0]["role"] == "tool"
        assert msgs[0]["tool_call_id"] == "tc1"
        assert msgs[0]["name"] == "search"

    def test_openai_style_messages(self):
        raw = [
            {"role": "system", "content": "Be helpful"},
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "4"},
        ]
        msgs = _normalise_messages(raw)
        assert len(msgs) == 3
        assert msgs[2]["content"] == "4"

    def test_openai_tool_calls(self):
        raw = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"id": "x", "type": "function", "function": {"name": "add", "arguments": '{"a":1}'}}
                ],
            }
        ]
        msgs = _normalise_messages(raw)
        assert msgs[0]["tool_calls"] is not None


class TestNormalisePydanticAIMessages:
    def test_request_and_response(self):
        raw = [
            {
                "kind": "request",
                "parts": [
                    {"part_kind": "system-prompt", "content": "Be helpful"},
                    {"part_kind": "user-prompt", "content": "Hello"},
                ],
            },
            {
                "kind": "response",
                "parts": [{"part_kind": "text", "content": "Hi there!"}],
            },
        ]
        msgs = _normalise_pydantic_ai_messages(raw)
        assert msgs[0] == {"role": "system", "content": "Be helpful"}
        assert msgs[1] == {"role": "user", "content": "Hello"}
        assert msgs[2] == {"role": "assistant", "content": "Hi there!"}

    def test_tool_call_in_response(self):
        raw = [
            {
                "kind": "response",
                "parts": [
                    {
                        "part_kind": "tool-call",
                        "tool_call_id": "tc1",
                        "tool_name": "search",
                        "args": {"q": "test"},
                    }
                ],
            },
        ]
        msgs = _normalise_pydantic_ai_messages(raw)
        assert msgs[0]["role"] == "assistant"
        assert msgs[0]["tool_calls"][0]["name"] == "search"

    def test_tool_return(self):
        raw = [
            {
                "kind": "request",
                "parts": [
                    {
                        "part_kind": "tool-return",
                        "tool_name": "search",
                        "content": "result",
                        "tool_call_id": "tc1",
                    }
                ],
            }
        ]
        msgs = _normalise_pydantic_ai_messages(raw)
        assert msgs[0]["role"] == "tool"
        assert msgs[0]["name"] == "search"

    def test_fallback_to_generic(self):
        # If it doesn't have kind-based structure, falls back to generic parsing
        raw = [{"role": "user", "content": "hi"}]
        msgs = _normalise_pydantic_ai_messages(raw)
        assert msgs == [{"role": "user", "content": "hi"}]


# ===========================================================================
# 2. Span type detection
# ===========================================================================


class TestDetectEventType:
    def test_openinference_kind(self):
        span = _make_span("s1", "t1", "some-span", {"openinference.span.kind": "LLM"})
        assert _detect_event_type(span) == EventType.LLM

    def test_traceloop_kind(self):
        span = _make_span("s1", "t1", "some-span", {"traceloop.span.kind": "tool"})
        assert _detect_event_type(span) == EventType.TOOL

    def test_gen_ai_operation(self):
        span = _make_span("s1", "t1", "Chat", {"gen_ai.operation.name": "chat"})
        assert _detect_event_type(span) == EventType.LLM

    def test_llm_indicator_attr(self):
        span = _make_span("s1", "t1", "inference", {"gen_ai.request.model": "gpt-4o"})
        assert _detect_event_type(span) == EventType.LLM

    def test_span_events_trigger_llm(self):
        evt = _make_event("gen_ai.user.message", {"content": "hi"})
        span = _make_span("s1", "t1", "model_call", {}, events=[evt])
        assert _detect_event_type(span) == EventType.LLM

    def test_name_heuristic_tool(self):
        span = _make_span("s1", "t1", "execute_tool", {})
        assert _detect_event_type(span) == EventType.TOOL

    def test_name_heuristic_embedding(self):
        span = _make_span("s1", "t1", "embed_text", {})
        assert _detect_event_type(span) == EventType.EMBEDDING

    def test_unknown(self):
        span = _make_span("s1", "t1", "unrelated-span", {})
        assert _detect_event_type(span) == EventType.UNKNOWN


# ===========================================================================
# 3. Input extraction
# ===========================================================================


class TestExtractInputs:
    def test_gen_ai_input_messages(self):
        raw = json.dumps([
            {"role": "system", "content": "Be helpful"},
            {"role": "user", "content": "Hello"},
        ])
        span = _make_span("s1", "t1", "Chat", {"gen_ai.input.messages": raw})
        inputs = _extract_inputs(span)
        assert isinstance(inputs, list)
        assert inputs[0]["role"] == "system"
        assert inputs[1]["role"] == "user"

    def test_gen_ai_input_messages_with_system_instructions(self):
        """gen_ai.system_instructions should be prepended when not already present."""
        raw = json.dumps([{"role": "user", "content": "Hello"}])
        span = _make_span("s1", "t1", "Chat", {
            "gen_ai.input.messages": raw,
            "gen_ai.system_instructions": json.dumps([{"type": "text", "content": "System prompt"}]),
        })
        inputs = _extract_inputs(span)
        assert isinstance(inputs, list)
        assert inputs[0]["role"] == "system"
        assert inputs[1]["role"] == "user"

    def test_gen_ai_prompt_string(self):
        span = _make_span("s1", "t1", "Completion", {"gen_ai.prompt": "Say hello"})
        inputs = _extract_inputs(span)
        assert isinstance(inputs, list)
        assert inputs[0]["content"] == "Say hello"

    def test_gen_ai_prompt_json(self):
        raw = json.dumps([{"role": "user", "content": "test"}])
        span = _make_span("s1", "t1", "Completion", {"gen_ai.prompt": raw})
        inputs = _extract_inputs(span)
        assert inputs[0]["role"] == "user"

    def test_pydantic_ai_all_messages(self):
        raw = json.dumps([
            {"kind": "request", "parts": [{"part_kind": "user-prompt", "content": "hi"}]},
        ])
        span = _make_span("s1", "t1", "agent", {"pydantic_ai.all_messages": raw})
        inputs = _extract_inputs(span)
        assert isinstance(inputs, list)
        assert inputs[0] == {"role": "user", "content": "hi"}

    def test_input_value_openinference_string(self):
        span = _make_span("s1", "t1", "chain", {"input.value": "some input"})
        inputs = _extract_inputs(span)
        # A bare string value is treated as a user message
        assert isinstance(inputs, list)
        assert inputs[0] == {"role": "user", "content": "some input"}

    def test_generic_input_dict(self):
        span = _make_span("s1", "t1", "fn", {"inputs": json.dumps({"x": 1})})
        inputs = _extract_inputs(span)
        # A dict without role/parts is returned as-is (not treated as a message)
        assert inputs == {"x": 1}

    def test_span_events_google_genai(self):
        """Google GenAI emits span events with event_body JSON."""
        events = [
            _make_event("gen_ai.system.message", {
                "event_body": json.dumps({"role": "system", "content": "Be helpful"})
            }),
            _make_event("gen_ai.user.message", {
                "event_body": json.dumps({"role": "user", "content": "Hello"})
            }),
            # gen_ai.choice is not an input event
            _make_event("gen_ai.choice", {
                "event_body": json.dumps({"message": {"role": "assistant", "content": "Hi!"}})
            }),
        ]
        span = _make_span("s1", "t1", "generate", {}, events=events)
        inputs = _extract_inputs(span)
        assert len(inputs) == 2  # type: ignore[arg-type]
        assert inputs[0]["role"] == "system"
        assert inputs[1]["role"] == "user"

    def test_span_events_standard_otel(self):
        """Standard OTel gen_ai events (no event_body wrapper)."""
        events = [
            _make_event("gen_ai.user.message", {"role": "user", "content": "What is 2+2?"}),
        ]
        span = _make_span("s1", "t1", "chat", {}, events=events)
        inputs = _extract_inputs(span)
        assert inputs[0]["role"] == "user"
        assert inputs[0]["content"] == "What is 2+2?"

    def test_empty_span_returns_empty_dict(self):
        span = _make_span("s1", "t1", "unknown", {})
        inputs = _extract_inputs(span)
        assert inputs == {}


# ===========================================================================
# 4. Output extraction
# ===========================================================================


class TestExtractOutput:
    def test_gen_ai_output_messages(self):
        raw = json.dumps([{"role": "assistant", "content": "Hello!", "parts": [{"type": "text", "content": "Hello!"}]}])
        span = _make_span("s1", "t1", "Chat", {"gen_ai.output.messages": raw})
        output = _extract_output(span)
        assert output["role"] == "assistant"

    def test_gen_ai_completion_string(self):
        span = _make_span("s1", "t1", "Chat", {"gen_ai.completion": "The answer is 42"})
        output = _extract_output(span)
        assert output == "The answer is 42"

    def test_final_result_pydantic(self):
        span = _make_span("s1", "t1", "agent", {"final_result": json.dumps({"answer": 42})})
        output = _extract_output(span)
        assert output == {"answer": 42}

    def test_output_value_openinference(self):
        span = _make_span("s1", "t1", "chain", {"output.value": "result text"})
        output = _extract_output(span)
        assert output == "result text"

    def test_span_events_choice(self):
        """gen_ai.choice span event → output."""
        events = [
            _make_event("gen_ai.choice", {
                "event_body": json.dumps({
                    "message": {"role": "assistant", "content": "I can help"},
                    "finish_reason": "stop",
                })
            }),
        ]
        span = _make_span("s1", "t1", "generate", {}, events=events)
        output = _extract_output(span)
        assert output["role"] == "assistant"
        assert output["content"] == "I can help"
        assert output["finish_reason"] == "stop"

    def test_no_output_returns_none(self):
        span = _make_span("s1", "t1", "unknown", {})
        assert _extract_output(span) is None


# ===========================================================================
# 5. Usage extraction
# ===========================================================================


class TestExtractUsage:
    def test_new_semconv(self):
        attrs = {"gen_ai.usage.input_tokens": 10, "gen_ai.usage.output_tokens": 20}
        usage = _extract_usage(attrs)
        assert usage is not None
        assert usage.input_tokens == 10
        assert usage.output_tokens == 20
        assert usage.total_tokens == 30

    def test_old_semconv(self):
        attrs = {"gen_ai.usage.prompt_tokens": 5, "gen_ai.usage.completion_tokens": 15}
        usage = _extract_usage(attrs)
        assert usage is not None
        assert usage.input_tokens == 5
        assert usage.output_tokens == 15
        assert usage.total_tokens == 20

    def test_vercel_ai(self):
        attrs = {"ai.usage.promptTokens": 8, "ai.usage.completionTokens": 12}
        usage = _extract_usage(attrs)
        assert usage is not None
        assert usage.input_tokens == 8
        assert usage.output_tokens == 12

    def test_openinference(self):
        attrs = {"llm.token_count.prompt": 3, "llm.token_count.completion": 7}
        usage = _extract_usage(attrs)
        assert usage is not None
        assert usage.input_tokens == 3
        assert usage.output_tokens == 7

    def test_no_usage(self):
        assert _extract_usage({}) is None

    def test_string_tokens(self):
        """Token counts may arrive as strings from some providers."""
        attrs = {"gen_ai.usage.input_tokens": "10", "gen_ai.usage.output_tokens": "5"}
        usage = _extract_usage(attrs)
        assert usage is not None
        assert usage.input_tokens == 10


# ===========================================================================
# 6. span_to_event
# ===========================================================================


class TestSpanToEvent:
    def test_basic_llm_span(self):
        attrs = {
            "gen_ai.request.model": "gpt-4o",
            "gen_ai.provider.name": "openai",
            "gen_ai.input.messages": json.dumps([{"role": "user", "content": "Hi"}]),
            "gen_ai.output.messages": json.dumps([
                {"role": "assistant", "parts": [{"type": "text", "content": "Hello!"}]}
            ]),
            "gen_ai.usage.input_tokens": 5,
            "gen_ai.usage.output_tokens": 3,
        }
        span = _make_span("span1", "trace1", "Chat Completion", attrs)
        event = span_to_event(span, known_span_ids={"span1"})

        assert event.id == "span1"
        assert event.type == EventType.LLM
        assert event.model == "gpt-4o"
        assert event.provider == "openai"
        assert event.usage is not None
        assert event.usage.total_tokens == 8
        assert event.parent_id is None

    def test_parent_outside_batch_becomes_root(self):
        span = _make_span("s2", "t1", "inner", {}, parent_id="s1")
        event = span_to_event(span, known_span_ids={"s2"})
        assert event.parent_id is None  # s1 not in batch

    def test_parent_inside_batch_preserved(self):
        span = _make_span("s2", "t1", "inner", {}, parent_id="s1")
        event = span_to_event(span, known_span_ids={"s1", "s2"})
        assert event.parent_id == "s1"

    def test_error_span(self):
        span = _make_span("s1", "t1", "oops", {}, status_code="ERROR", status_msg="timeout")
        event = span_to_event(span)
        assert event.status == "error"
        assert event.error == "timeout"

    def test_as_dict(self):
        span = _make_span("s1", "t1", "call", {"gen_ai.request.model": "claude-3"})
        event = span_to_event(span)
        d = event.as_dict()
        assert d["id"] == "s1"
        assert "inputs" in d
        assert "output" in d


# ===========================================================================
# 7. spans_to_traces — full pipeline
# ===========================================================================


class TestSpansToTraces:
    def test_single_trace_ordering(self):
        """Events should be in start-time order."""
        spans = [
            _make_span("s2", "t1", "child",  {}, parent_id="s1", start_ns=2_000_000_000),
            _make_span("s1", "t1", "parent", {},               start_ns=1_000_000_000),
        ]
        traces = spans_to_traces(spans)
        assert len(traces) == 1
        assert traces[0].root_id == "s1"
        assert traces[0].events[0].id == "s1"
        assert traces[0].events[1].id == "s2"

    def test_multiple_traces(self):
        spans = [
            _make_span("a1", "trace-a", "root", {}),
            _make_span("b1", "trace-b", "root", {}),
        ]
        traces = spans_to_traces(spans)
        assert len(traces) == 2
        ids = {t.trace_id for t in traces}
        assert "trace-a" in ids
        assert "trace-b" in ids

    def test_full_openai_conversation(self):
        """Simulate an OpenAI 2-turn conversation with a tool call."""
        # Turn 1: user asks, model calls a tool
        llm_span_1 = _make_span(
            "llm1", "t1", "Chat Completion with 'gpt-4o'",
            {
                "gen_ai.request.model": "gpt-4o",
                "gen_ai.provider.name": "openai",
                "gen_ai.input.messages": json.dumps([
                    {"role": "user", "content": "What's the weather in London?"}
                ]),
                "gen_ai.output.messages": json.dumps([{
                    "role": "assistant",
                    "parts": [{"type": "tool_call", "id": "tc1", "name": "get_weather", "arguments": {"city": "London"}}],
                }]),
                "gen_ai.usage.input_tokens": 12,
                "gen_ai.usage.output_tokens": 8,
            },
            parent_id="root",
            start_ns=2_000_000_000,
        )

        # Tool execution
        tool_span = _make_span(
            "tool1", "t1", "get_weather",
            {
                "gen_ai.tool.name": "get_weather",
                "openinference.span.kind": "TOOL",
                "inputs": json.dumps({"city": "London"}),
                "output": json.dumps({"temp": 15, "condition": "cloudy"}),
            },
            parent_id="llm1",
            start_ns=3_000_000_000,
        )

        # Turn 2: model sees tool result and responds
        llm_span_2 = _make_span(
            "llm2", "t1", "Chat Completion with 'gpt-4o'",
            {
                "gen_ai.request.model": "gpt-4o",
                "gen_ai.provider.name": "openai",
                "gen_ai.input.messages": json.dumps([
                    {"role": "user", "content": "What's the weather in London?"},
                    {"role": "assistant", "content": None,
                     "tool_calls": [{"id": "tc1", "name": "get_weather"}]},
                    {"role": "tool", "tool_call_id": "tc1", "content": '{"temp":15}'},
                ]),
                "gen_ai.output.messages": json.dumps([{
                    "role": "assistant",
                    "parts": [{"type": "text", "content": "It's 15°C and cloudy in London."}],
                }]),
                "gen_ai.usage.input_tokens": 40,
                "gen_ai.usage.output_tokens": 15,
            },
            parent_id="root",
            start_ns=4_000_000_000,
        )

        root_span = _make_span("root", "t1", "agent-run", {}, start_ns=1_000_000_000)

        traces = spans_to_traces([llm_span_2, tool_span, llm_span_1, root_span])
        assert len(traces) == 1
        trace = traces[0]

        assert trace.root_id == "root"
        assert len(trace.events) == 4

        # Sorted by start time
        ids_in_order = [e.id for e in trace.events]
        assert ids_in_order == ["root", "llm1", "tool1", "llm2"]

        # Types — "agent-run" name triggers AGENT heuristic for the root span
        assert trace.events[0].type == EventType.AGENT  # root matches "run" heuristic
        assert trace.events[1].type == EventType.LLM
        assert trace.events[2].type == EventType.TOOL
        assert trace.events[3].type == EventType.LLM

        # Parent relationships
        assert trace.events[0].parent_id is None
        assert trace.events[1].parent_id == "root"
        assert trace.events[2].parent_id == "llm1"
        assert trace.events[3].parent_id == "root"

        # Last LLM call has full conversation history in inputs
        last_llm = trace.events[3]
        assert isinstance(last_llm.inputs, list)
        roles = [m["role"] for m in last_llm.inputs]
        assert "user" in roles
        assert "tool" in roles  # tool result fed back

        # Tool span inputs are the function arguments
        tool_event = trace.events[2]
        assert isinstance(tool_event.inputs, dict)

    def test_google_genai_span_events(self):
        """Google GenAI emits input/output as OTEL span events."""
        events = [
            _make_event("gen_ai.system.message", {
                "event_body": json.dumps({"role": "system", "content": "You are helpful"})
            }),
            _make_event("gen_ai.user.message", {
                "event_body": json.dumps({"role": "user", "content": "Who are you?"})
            }),
            _make_event("gen_ai.choice", {
                "event_body": json.dumps({
                    "message": {"role": "assistant", "content": "I am Gemini"},
                    "finish_reason": "stop",
                })
            }),
        ]
        span = _make_span("s1", "t1", "generate_content", {}, events=events)
        traces = spans_to_traces([span])
        event = traces[0].events[0]

        assert event.type == EventType.LLM
        assert len(event.inputs) == 2  # type: ignore[arg-type]
        assert event.inputs[0]["role"] == "system"  # type: ignore[index]
        assert event.inputs[1]["role"] == "user"    # type: ignore[index]
        assert event.output["role"] == "assistant"
        assert event.output["content"] == "I am Gemini"

    def test_pydantic_ai_agent_span(self):
        """PydanticAI uses pydantic_ai.all_messages + final_result."""
        all_msgs = json.dumps([
            {"kind": "request", "parts": [{"part_kind": "user-prompt", "content": "Summarize this"}]},
            {"kind": "response", "parts": [{"part_kind": "text", "content": "Summary: ..."}]},
        ])
        span = _make_span("s1", "t1", "agent run", {
            "pydantic_ai.all_messages": all_msgs,
            "final_result": json.dumps({"summary": "brief summary"}),
        })
        traces = spans_to_traces([span])
        event = traces[0].events[0]

        assert event.type == EventType.LLM
        assert isinstance(event.inputs, list)
        assert event.inputs[0]["role"] == "user"
        assert event.output == {"summary": "brief summary"}

    def test_vercel_ai_sdk(self):
        """Vercel AI SDK uses ai.prompt and ai.response."""
        span = _make_span("s1", "t1", "chat-completion", {
            "ai.model.id": "gpt-4o",
            "ai.model.provider": "openai",
            "ai.prompt": json.dumps([{"role": "user", "content": "Hello"}]),
            "ai.response": json.dumps({"role": "assistant", "content": "Hi!"}),
            "ai.usage.promptTokens": 5,
            "ai.usage.completionTokens": 3,
        })
        traces = spans_to_traces([span])
        event = traces[0].events[0]

        assert event.type == EventType.LLM
        assert event.model == "gpt-4o"
        assert event.provider == "openai"
        assert isinstance(event.inputs, list)
        assert event.inputs[0]["content"] == "Hello"
        assert event.output["content"] == "Hi!"
        assert event.usage is not None
        assert event.usage.total_tokens == 8

    def test_anthropic_span(self):
        """Anthropic messages have a separate system field."""
        span = _make_span("s1", "t1", "Message with 'claude-3-5-sonnet'", {
            "gen_ai.system": "anthropic",
            "gen_ai.request.model": "claude-3-5-sonnet-20241022",
            "gen_ai.input.messages": json.dumps([
                {"role": "user", "content": "Explain quantum computing"}
            ]),
            "gen_ai.system_instructions": json.dumps([
                {"type": "text", "content": "You are a physics teacher"}
            ]),
            "gen_ai.output.messages": json.dumps([{
                "role": "assistant",
                "parts": [{"type": "text", "content": "Quantum computing uses qubits..."}],
                "finish_reason": "end_turn",
            }]),
            "gen_ai.usage.input_tokens": 20,
            "gen_ai.usage.output_tokens": 50,
        })
        traces = spans_to_traces([span])
        event = traces[0].events[0]

        assert event.type == EventType.LLM
        assert event.provider == "anthropic"
        assert event.model == "claude-3-5-sonnet-20241022"

        # System instructions should be prepended
        assert isinstance(event.inputs, list)
        assert event.inputs[0]["role"] == "system"
        assert event.inputs[0]["content"] == "You are a physics teacher"
        assert event.inputs[1]["role"] == "user"

        assert event.output["role"] == "assistant"
        assert event.usage.total_tokens == 70  # type: ignore[union-attr]

    def test_traceloop_span(self):
        """Traceloop / OpenLLMetry conventions."""
        span = _make_span("s1", "t1", "llm_call", {
            "traceloop.span.kind": "llm",
            "gen_ai.system": "openai",
            "traceloop.entity.input": json.dumps({"messages": [{"role": "user", "content": "test"}]}),
            "traceloop.entity.output": json.dumps({"choices": [{"message": {"role": "assistant", "content": "ok"}}]}),
        })
        event = span_to_event(span)
        assert event.type == EventType.LLM

    def test_empty_trace(self):
        traces = spans_to_traces([])
        assert traces == []

    def test_as_dict_serialisable(self):
        """OtelTrace.as_dict() should be JSON-serialisable."""
        span = _make_span("s1", "t1", "Chat", {
            "gen_ai.request.model": "gpt-4o",
            "gen_ai.input.messages": json.dumps([{"role": "user", "content": "hi"}]),
            "gen_ai.output.messages": json.dumps([
                {"role": "assistant", "parts": [{"type": "text", "content": "hello"}]}
            ]),
            "gen_ai.usage.input_tokens": 3,
            "gen_ai.usage.output_tokens": 2,
        })
        traces = spans_to_traces([span])
        # Should not raise
        serialised = json.dumps(traces[0].as_dict())
        data = json.loads(serialised)
        assert data["trace_id"] == "t1"
        assert len(data["events"]) == 1
