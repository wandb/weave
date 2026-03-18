"""Tests for atif_to_otel.py — ATIF → OTel GenAI span conversion.

Run with:
    uv run --group test python -m pytest examples/otel_genai/test_atif_to_otel.py -v
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from atif_to_otel import (
    _assign_step_times,
    _message_to_str,
    _parse_timestamp,
    _span_id_from_seed,
    _to_iso,
    _trace_id_from_session,
    atif_to_otel_spans,
)

# ---------------------------------------------------------------------------
# Fixtures: canonical ATIF examples
# ---------------------------------------------------------------------------

# The example from the ATIF RFC (section IV), slightly shortened for brevity.
RFC_TRAJECTORY: dict = {
    "schema_version": "ATIF-v1.5",
    "session_id": "025B810F-B3A2-4C67-93C0-FE7A142A947A",
    "agent": {
        "name": "harbor-agent",
        "version": "1.0.0",
        "model_name": "gemini-2.5-flash",
        "tool_definitions": [
            {
                "type": "function",
                "function": {
                    "name": "financial_search",
                    "description": "Search for financial data",
                },
            }
        ],
    },
    "final_metrics": {
        "total_prompt_tokens": 1120,
        "total_completion_tokens": 124,
        "total_cached_tokens": 200,
        "total_cost_usd": 0.00078,
        "total_steps": 3,
    },
    "steps": [
        {
            "step_id": 1,
            "timestamp": "2025-10-11T10:30:00Z",
            "source": "user",
            "message": "What is the current trading price of Alphabet (GOOGL)?",
        },
        {
            "step_id": 2,
            "timestamp": "2025-10-11T10:30:02Z",
            "source": "agent",
            "model_name": "gemini-2.5-flash",
            "reasoning_effort": "medium",
            "message": "I will search for the current trading price and volume for GOOGL.",
            "reasoning_content": "The request requires two data points.",
            "tool_calls": [
                {
                    "tool_call_id": "call_price_1",
                    "function_name": "financial_search",
                    "arguments": {"ticker": "GOOGL", "metric": "price"},
                },
                {
                    "tool_call_id": "call_volume_2",
                    "function_name": "financial_search",
                    "arguments": {"ticker": "GOOGL", "metric": "volume"},
                },
            ],
            "observation": {
                "results": [
                    {
                        "source_call_id": "call_price_1",
                        "content": "GOOGL is currently trading at $185.35",
                    },
                    {
                        "source_call_id": "call_volume_2",
                        "content": "GOOGL volume: 1.5M shares traded.",
                    },
                ]
            },
            "metrics": {
                "prompt_tokens": 520,
                "completion_tokens": 80,
                "cached_tokens": 200,
                "cost_usd": 0.00045,
            },
        },
        {
            "step_id": 3,
            "timestamp": "2025-10-11T10:30:05Z",
            "source": "agent",
            "model_name": "gemini-2.5-flash",
            "reasoning_effort": "low",
            "message": "As of October 11, 2025, Alphabet (GOOGL) is trading at $185.35.",
            "reasoning_content": "All data retrieved; format for the user.",
            "metrics": {
                "prompt_tokens": 600,
                "completion_tokens": 44,
                "completion_token_ids": [1722, 310, 5533],
                "logprobs": [-0.1, -0.05, -0.02],
                "cost_usd": 0.00033,
            },
        },
    ],
}

MINIMAL_TRAJECTORY: dict = {
    "schema_version": "ATIF-v1.0",
    "session_id": "minimal-session",
    "agent": {"name": "MinAgent", "version": "0.1"},
    "steps": [
        {"step_id": 1, "source": "user", "message": "Hello"},
        {"step_id": 2, "source": "agent", "message": "Hi there"},
    ],
}

SYSTEM_PROMPT_TRAJECTORY: dict = {
    "schema_version": "ATIF-v1.5",
    "session_id": "sys-session",
    "agent": {"name": "SysAgent", "version": "1.0"},
    "steps": [
        {
            "step_id": 1,
            "source": "system",
            "message": "You are a helpful assistant.",
        },
        {
            "step_id": 2,
            "source": "user",
            "message": "What day is it?",
        },
        {
            "step_id": 3,
            "source": "agent",
            "message": "Today is Wednesday.",
        },
    ],
}

MULTIMODAL_TRAJECTORY: dict = {
    "schema_version": "ATIF-v1.6",
    "session_id": "multimodal-session",
    "agent": {"name": "VisionAgent", "version": "1.0"},
    "steps": [
        {
            "step_id": 1,
            "source": "user",
            "message": [
                {"type": "text", "text": "What is in this image?"},
                {"type": "image", "source": {"media_type": "image/png", "path": "images/cat.png"}},
            ],
        },
        {
            "step_id": 2,
            "source": "agent",
            "message": "The image shows a cat sitting on a chair.",
        },
    ],
}


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_trace_id_length(self) -> None:
        assert len(_trace_id_from_session("abc")) == 32

    def test_trace_id_deterministic(self) -> None:
        assert _trace_id_from_session("same") == _trace_id_from_session("same")

    def test_trace_id_different_sessions(self) -> None:
        assert _trace_id_from_session("a") != _trace_id_from_session("b")

    def test_span_id_length(self) -> None:
        assert len(_span_id_from_seed("seed")) == 16

    def test_span_id_deterministic(self) -> None:
        assert _span_id_from_seed("x") == _span_id_from_seed("x")

    def test_parse_timestamp_z_suffix(self) -> None:
        dt = _parse_timestamp("2025-10-11T10:30:00Z")
        assert dt is not None
        assert dt.year == 2025
        assert dt.tzinfo is not None

    def test_parse_timestamp_none(self) -> None:
        assert _parse_timestamp(None) is None

    def test_to_iso_format(self) -> None:
        dt = datetime(2025, 10, 11, 10, 30, 0, 123000, tzinfo=timezone.utc)
        assert _to_iso(dt) == "2025-10-11T10:30:00.123Z"

    def test_message_to_str_string(self) -> None:
        assert _message_to_str("hello") == "hello"

    def test_message_to_str_list(self) -> None:
        parts = [{"type": "text", "text": "hi"}]
        result = _message_to_str(parts)
        assert json.loads(result) == parts

    def test_assign_step_times_with_timestamps(self) -> None:
        steps = [
            {"timestamp": "2025-01-01T00:00:00Z"},
            {"timestamp": "2025-01-01T00:00:02Z"},
        ]
        starts, ends = _assign_step_times(steps)
        assert len(starts) == 2
        assert starts[1] > starts[0]
        # End of first span == start of second span
        assert ends[0] == starts[1]

    def test_assign_step_times_without_timestamps(self) -> None:
        steps = [{"source": "user"}, {"source": "agent"}]
        starts, ends = _assign_step_times(steps)
        assert len(starts) == 2
        assert all(e > s for s, e in zip(starts, ends))


# ---------------------------------------------------------------------------
# Span count and operation types
# ---------------------------------------------------------------------------


class TestSpanStructure:
    def test_rfc_example_span_count(self) -> None:
        # 1 invoke_agent + 2 chat + 2 execute_tool(step2) + 0 execute_tool(step3) = 5
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        assert len(spans) == 5

    def test_rfc_operation_names(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        ops = [s["operation_name"] for s in spans]
        assert ops.count("invoke_agent") == 1
        assert ops.count("chat") == 2
        assert ops.count("execute_tool") == 2

    def test_minimal_span_count(self) -> None:
        # 1 invoke_agent + 1 chat (user step is not a span)
        spans = atif_to_otel_spans(MINIMAL_TRAJECTORY)
        assert len(spans) == 2

    def test_root_span_is_first(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        assert spans[0]["operation_name"] == "invoke_agent"

    def test_system_step_not_a_span(self) -> None:
        spans = atif_to_otel_spans(SYSTEM_PROMPT_TRAJECTORY)
        ops = [s["operation_name"] for s in spans]
        assert "system" not in ops
        # system + user + agent → invoke_agent + chat
        assert len(spans) == 2


# ---------------------------------------------------------------------------
# Hierarchy (parent_span_id linkage)
# ---------------------------------------------------------------------------


class TestSpanHierarchy:
    def test_root_has_no_parent(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        root = next(s for s in spans if s["operation_name"] == "invoke_agent")
        assert root["parent_span_id"] == ""

    def test_chat_spans_parent_is_root(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        root = next(s for s in spans if s["operation_name"] == "invoke_agent")
        chats = [s for s in spans if s["operation_name"] == "chat"]
        for chat in chats:
            assert chat["parent_span_id"] == root["span_id"]

    def test_execute_tool_parent_is_chat(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        chat_ids = {s["span_id"] for s in spans if s["operation_name"] == "chat"}
        tool_spans = [s for s in spans if s["operation_name"] == "execute_tool"]
        for ts in tool_spans:
            assert ts["parent_span_id"] in chat_ids

    def test_all_spans_share_trace_id(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        trace_ids = {s["trace_id"] for s in spans}
        assert len(trace_ids) == 1

    def test_span_ids_unique(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        ids = [s["span_id"] for s in spans]
        assert len(ids) == len(set(ids))

    def test_deterministic_ids(self) -> None:
        spans_a = atif_to_otel_spans(RFC_TRAJECTORY)
        spans_b = atif_to_otel_spans(RFC_TRAJECTORY)
        assert [s["span_id"] for s in spans_a] == [s["span_id"] for s in spans_b]


# ---------------------------------------------------------------------------
# Root invoke_agent span
# ---------------------------------------------------------------------------


class TestRootSpan:
    @pytest.fixture()
    def root(self) -> dict:
        return next(
            s for s in atif_to_otel_spans(RFC_TRAJECTORY) if s["operation_name"] == "invoke_agent"
        )

    def test_agent_name(self, root: dict) -> None:
        assert root["agent_name"] == "harbor-agent"

    def test_agent_version(self, root: dict) -> None:
        assert root["agent_version"] == "1.0.0"

    def test_request_model(self, root: dict) -> None:
        assert root["request_model"] == "gemini-2.5-flash"

    def test_conversation_id_is_session_id(self, root: dict) -> None:
        assert root["conversation_id"] == RFC_TRAJECTORY["session_id"]

    def test_tool_definitions_present(self, root: dict) -> None:
        defs = json.loads(root["tool_definitions"])
        assert len(defs) == 1
        assert defs[0]["function"]["name"] == "financial_search"

    def test_aggregate_input_tokens(self, root: dict) -> None:
        assert root["input_tokens"] == 1120

    def test_aggregate_output_tokens(self, root: dict) -> None:
        assert root["output_tokens"] == 124

    def test_aggregate_total_tokens(self, root: dict) -> None:
        assert root["total_tokens"] == 1244

    def test_cost_usd_in_attributes(self, root: dict) -> None:
        assert root["attributes"]["gen_ai.usage.cost_usd"] == pytest.approx(0.00078)

    def test_cached_tokens_in_attributes(self, root: dict) -> None:
        assert root["attributes"]["gen_ai.usage.cached_tokens"] == 200

    def test_schema_version_in_attributes(self, root: dict) -> None:
        assert root["attributes"]["atif.schema_version"] == "ATIF-v1.5"

    def test_span_name(self, root: dict) -> None:
        assert root["span_name"] == "invoke_agent harbor-agent"

    def test_timing_covers_all_steps(self, root: dict) -> None:
        # Root should start at first step and end at or after last step.
        root_start = _parse_timestamp(root["started_at"])
        root_end = _parse_timestamp(root["ended_at"])
        assert root_end > root_start  # type: ignore[operator]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


class TestSystemPrompt:
    def test_system_instructions_on_root(self) -> None:
        spans = atif_to_otel_spans(SYSTEM_PROMPT_TRAJECTORY)
        root = next(s for s in spans if s["operation_name"] == "invoke_agent")
        assert root["system_instructions"] == "You are a helpful assistant."

    def test_no_system_prompt_when_absent(self) -> None:
        spans = atif_to_otel_spans(MINIMAL_TRAJECTORY)
        root = next(s for s in spans if s["operation_name"] == "invoke_agent")
        assert root["system_instructions"] == ""


# ---------------------------------------------------------------------------
# Chat spans
# ---------------------------------------------------------------------------


class TestChatSpans:
    def test_user_message_accumulates_into_chat_input(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        # Step 2 is the first agent step; it should see the user message from step 1.
        chat2 = next(s for s in spans if s["operation_name"] == "chat" and s["attributes"]["atif.step_id"] == 2)
        input_msgs = json.loads(chat2["input_messages"])
        assert len(input_msgs) == 1
        assert input_msgs[0]["role"] == "user"
        assert "GOOGL" in input_msgs[0]["content"]

    def test_assistant_message_in_output(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        chat2 = next(s for s in spans if s["operation_name"] == "chat" and s["attributes"]["atif.step_id"] == 2)
        output_msgs = json.loads(chat2["output_messages"])
        assert output_msgs[0]["role"] == "assistant"
        assert "GOOGL" in output_msgs[0]["content"]

    def test_chat_token_counts(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        chat2 = next(s for s in spans if s["operation_name"] == "chat" and s["attributes"]["atif.step_id"] == 2)
        assert chat2["input_tokens"] == 520
        assert chat2["output_tokens"] == 80
        assert chat2["total_tokens"] == 600

    def test_reasoning_content_in_attributes(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        chat2 = next(s for s in spans if s["operation_name"] == "chat" and s["attributes"]["atif.step_id"] == 2)
        assert "gen_ai.response.reasoning_content" in chat2["attributes"]
        assert "two data points" in chat2["attributes"]["gen_ai.response.reasoning_content"]

    def test_reasoning_effort_in_attributes(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        chat2 = next(s for s in spans if s["operation_name"] == "chat" and s["attributes"]["atif.step_id"] == 2)
        assert chat2["attributes"]["gen_ai.request.reasoning_effort"] == "medium"

    def test_cost_usd_per_step(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        chat2 = next(s for s in spans if s["operation_name"] == "chat" and s["attributes"]["atif.step_id"] == 2)
        assert chat2["attributes"]["gen_ai.usage.cost_usd"] == pytest.approx(0.00045)

    def test_cached_tokens_per_step(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        chat2 = next(s for s in spans if s["operation_name"] == "chat" and s["attributes"]["atif.step_id"] == 2)
        assert chat2["attributes"]["gen_ai.usage.cached_tokens"] == 200

    def test_logprobs_in_attributes(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        chat3 = next(s for s in spans if s["operation_name"] == "chat" and s["attributes"]["atif.step_id"] == 3)
        logprobs = json.loads(chat3["attributes"]["gen_ai.response.logprobs"])
        assert logprobs == [-0.1, -0.05, -0.02]

    def test_completion_token_ids_in_attributes(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        chat3 = next(s for s in spans if s["operation_name"] == "chat" and s["attributes"]["atif.step_id"] == 3)
        ids = json.loads(chat3["attributes"]["gen_ai.response.completion_token_ids"])
        assert ids == [1722, 310, 5533]

    def test_no_logprobs_when_absent(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        chat2 = next(s for s in spans if s["operation_name"] == "chat" and s["attributes"]["atif.step_id"] == 2)
        assert "gen_ai.response.logprobs" not in chat2["attributes"]

    def test_model_name_propagated(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        chats = [s for s in spans if s["operation_name"] == "chat"]
        for chat in chats:
            assert chat["request_model"] == "gemini-2.5-flash"

    def test_second_agent_step_has_empty_input_messages(self) -> None:
        # Step 3 has no user message before it — input_messages should be empty.
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        chat3 = next(s for s in spans if s["operation_name"] == "chat" and s["attributes"]["atif.step_id"] == 3)
        assert json.loads(chat3["input_messages"]) == []


# ---------------------------------------------------------------------------
# Execute_tool spans
# ---------------------------------------------------------------------------


class TestToolSpans:
    def test_tool_names(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        tool_spans = [s for s in spans if s["operation_name"] == "execute_tool"]
        names = {s["tool_name"] for s in tool_spans}
        assert names == {"financial_search"}

    def test_tool_call_ids(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        tool_spans = [s for s in spans if s["operation_name"] == "execute_tool"]
        ids = {s["tool_call_id"] for s in tool_spans}
        assert ids == {"call_price_1", "call_volume_2"}

    def test_tool_arguments(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        price_span = next(s for s in spans if s["tool_call_id"] == "call_price_1")
        args = json.loads(price_span["tool_call_arguments"])
        assert args == {"ticker": "GOOGL", "metric": "price"}

    def test_tool_results_matched(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        price_span = next(s for s in spans if s["tool_call_id"] == "call_price_1")
        assert "$185.35" in price_span["tool_call_result"]

        volume_span = next(s for s in spans if s["tool_call_id"] == "call_volume_2")
        assert "1.5M" in volume_span["tool_call_result"]

    def test_tool_type_is_function(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        for s in spans:
            if s["operation_name"] == "execute_tool":
                assert s["tool_type"] == "function"

    def test_tool_span_name(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        tool_spans = [s for s in spans if s["operation_name"] == "execute_tool"]
        for ts in tool_spans:
            assert ts["span_name"].startswith("execute_tool ")

    def test_tool_step_id_in_attributes(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        tool_spans = [s for s in spans if s["operation_name"] == "execute_tool"]
        for ts in tool_spans:
            assert ts["attributes"]["atif.step_id"] == 2


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------


class TestTiming:
    def test_timestamps_are_iso_strings(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        for span in spans:
            # Should parse without error.
            _parse_timestamp(span["started_at"])
            _parse_timestamp(span["ended_at"])

    def test_end_after_start(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        for span in spans:
            start = _parse_timestamp(span["started_at"])
            end = _parse_timestamp(span["ended_at"])
            assert end >= start  # type: ignore[operator]

    def test_synthetic_timing_when_no_timestamps(self) -> None:
        spans = atif_to_otel_spans(MINIMAL_TRAJECTORY)
        for span in spans:
            start = _parse_timestamp(span["started_at"])
            end = _parse_timestamp(span["ended_at"])
            assert end > start  # type: ignore[operator]

    def test_timestamps_respected_from_atif(self) -> None:
        spans = atif_to_otel_spans(RFC_TRAJECTORY)
        # Step 2 has timestamp 10:30:02, step 3 has 10:30:05.
        chat2 = next(s for s in spans if s["operation_name"] == "chat" and s["attributes"]["atif.step_id"] == 2)
        chat3 = next(s for s in spans if s["operation_name"] == "chat" and s["attributes"]["atif.step_id"] == 3)
        assert _parse_timestamp(chat3["started_at"]) > _parse_timestamp(chat2["started_at"])  # type: ignore[operator]


# ---------------------------------------------------------------------------
# Multimodal content
# ---------------------------------------------------------------------------


class TestMultimodal:
    def test_multimodal_user_message_json_encoded(self) -> None:
        spans = atif_to_otel_spans(MULTIMODAL_TRAJECTORY)
        chat = next(s for s in spans if s["operation_name"] == "chat")
        input_msgs = json.loads(chat["input_messages"])
        assert len(input_msgs) == 1
        # The multimodal message should be JSON-encoded inside the content field.
        content = input_msgs[0]["content"]
        parsed = json.loads(content)
        assert parsed[0]["type"] == "text"
        assert parsed[1]["type"] == "image"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_steps(self) -> None:
        traj = {"session_id": "empty", "agent": {"name": "A", "version": "1"}, "steps": []}
        spans = atif_to_otel_spans(traj)
        # Should still produce the root invoke_agent span.
        assert len(spans) == 1
        assert spans[0]["operation_name"] == "invoke_agent"

    def test_no_agent_block(self) -> None:
        traj = {
            "session_id": "no-agent",
            "steps": [{"step_id": 1, "source": "agent", "message": "Hi"}],
        }
        spans = atif_to_otel_spans(traj)
        assert spans[0]["agent_name"] == ""

    def test_agent_step_no_tool_calls(self) -> None:
        spans = atif_to_otel_spans(MINIMAL_TRAJECTORY)
        tool_spans = [s for s in spans if s["operation_name"] == "execute_tool"]
        assert tool_spans == []

    def test_missing_observation_result(self) -> None:
        # Tool call with no matching observation result → empty tool_call_result.
        traj = {
            "session_id": "missing-obs",
            "agent": {"name": "A", "version": "1"},
            "steps": [
                {
                    "step_id": 1,
                    "source": "agent",
                    "message": "doing stuff",
                    "tool_calls": [
                        {"tool_call_id": "tc1", "function_name": "my_tool", "arguments": {}}
                    ],
                    "observation": {"results": []},
                }
            ],
        }
        spans = atif_to_otel_spans(traj)
        tc = next(s for s in spans if s["operation_name"] == "execute_tool")
        assert tc["tool_call_result"] == ""

    def test_no_final_metrics(self) -> None:
        traj = {
            "session_id": "no-metrics",
            "agent": {"name": "A", "version": "1"},
            "steps": [{"step_id": 1, "source": "agent", "message": "Hi"}],
        }
        spans = atif_to_otel_spans(traj)
        root = spans[0]
        assert root["input_tokens"] == 0
        assert root["output_tokens"] == 0
        assert "gen_ai.usage.cost_usd" not in root["attributes"]

    def test_multiple_user_messages_before_agent(self) -> None:
        traj = {
            "session_id": "multi-user",
            "agent": {"name": "A", "version": "1"},
            "steps": [
                {"step_id": 1, "source": "user", "message": "First"},
                {"step_id": 2, "source": "user", "message": "Second"},
                {"step_id": 3, "source": "agent", "message": "Reply"},
            ],
        }
        spans = atif_to_otel_spans(traj)
        chat = next(s for s in spans if s["operation_name"] == "chat")
        input_msgs = json.loads(chat["input_messages"])
        assert len(input_msgs) == 2
        assert input_msgs[0]["content"] == "First"
        assert input_msgs[1]["content"] == "Second"

    def test_consecutive_agent_steps_no_user_between(self) -> None:
        traj = {
            "session_id": "consecutive",
            "agent": {"name": "A", "version": "1"},
            "steps": [
                {"step_id": 1, "source": "agent", "message": "First agent reply"},
                {"step_id": 2, "source": "agent", "message": "Second agent reply"},
            ],
        }
        spans = atif_to_otel_spans(traj)
        chats = [s for s in spans if s["operation_name"] == "chat"]
        assert len(chats) == 2
        # Second chat has no pending user messages.
        chat2 = next(s for s in chats if s["attributes"]["atif.step_id"] == 2)
        assert json.loads(chat2["input_messages"]) == []
