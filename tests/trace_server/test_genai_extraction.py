"""Unit tests for genai_extraction.py — OTel span → schema extraction."""

import datetime
from typing import Any

from weave.trace_server.opentelemetry.genai_extraction import (
    extract_agent_name,
    extract_conversation_id,
    extract_conversation_name,
    extract_finish_reasons,
    extract_genai_span,
    extract_input_tokens,
    extract_operation_name,
    extract_output_tokens,
    extract_provider,
    extract_reasoning_content,
    extract_reasoning_tokens,
    extract_tool_call_arguments,
    extract_tool_call_result,
    extract_total_tokens,
)
from weave.trace_server.opentelemetry.python_spans import (
    Resource,
    Span,
    SpanKind,
    Status,
    StatusCode,
)


def _make_span(
    attrs: dict[str, Any] | None = None,
    name: str = "test-span",
    events: list | None = None,
) -> Span:
    """Build a minimal Span for testing."""
    now_ns = int(datetime.datetime.now().timestamp() * 1_000_000_000)
    return Span(
        resource=Resource(attributes={}),
        name=name,
        trace_id="abc123",
        span_id="def456",
        start_time_unix_nano=now_ns,
        end_time_unix_nano=now_ns + 100_000_000,
        attributes=attrs or {},
        kind=SpanKind.CLIENT,
        status=Status(code=StatusCode.OK),
        events=events or [],
    )


# ============================================================================
# Provider extraction
# ============================================================================


class TestExtractProvider:
    def test_weave_key(self) -> None:
        assert extract_provider({"weave.provider.name": "openai"}) == "openai"

    def test_genai_key(self) -> None:
        assert extract_provider({"gen_ai.provider.name": "Anthropic"}) == "anthropic"

    def test_genai_system_fallback(self) -> None:
        assert extract_provider({"gen_ai.system": "OpenAI"}) == "openai"

    def test_weave_takes_priority(self) -> None:
        assert (
            extract_provider(
                {"weave.provider.name": "weave", "gen_ai.provider.name": "genai"}
            )
            == "weave"
        )

    def test_empty(self) -> None:
        assert extract_provider({}) == ""


# ============================================================================
# Operation name extraction
# ============================================================================


class TestExtractOperationName:
    def test_weave_key(self) -> None:
        assert extract_operation_name({"weave.operation.name": "chat"}, "") == "chat"

    def test_genai_key(self) -> None:
        assert (
            extract_operation_name({"gen_ai.operation.name": "invoke_agent"}, "")
            == "invoke_agent"
        )

    def test_span_name_inference(self) -> None:
        assert extract_operation_name({}, "chat gpt-4o") == "chat"
        assert extract_operation_name({}, "invoke_agent my-bot") == "invoke_agent"
        assert extract_operation_name({}, "execute_tool get_weather") == "execute_tool"
        assert (
            extract_operation_name({}, "generate_content gemini") == "generate_content"
        )

    def test_unknown_span_name(self) -> None:
        assert extract_operation_name({}, "unknown_thing") == ""

    def test_empty(self) -> None:
        assert extract_operation_name({}, "") == ""


# ============================================================================
# Agent name extraction
# ============================================================================


class TestExtractAgentName:
    def test_weave_key(self) -> None:
        assert extract_agent_name({"weave.agent.name": "my-bot"}, "") == "my-bot"

    def test_genai_key(self) -> None:
        assert extract_agent_name({"gen_ai.agent.name": "assistant"}, "") == "assistant"

    def test_span_name_inference(self) -> None:
        assert extract_agent_name({}, "invoke_agent weather-bot") == "weather-bot"

    def test_empty(self) -> None:
        assert extract_agent_name({}, "random-span") == ""


# ============================================================================
# Token extraction
# ============================================================================


class TestTokenExtraction:
    def test_input_tokens_weave(self) -> None:
        assert extract_input_tokens({"weave.usage.input_tokens": 100}) == 100

    def test_input_tokens_genai(self) -> None:
        assert extract_input_tokens({"gen_ai.usage.input_tokens": 200}) == 200

    def test_output_tokens(self) -> None:
        assert extract_output_tokens({"weave.usage.output_tokens": 50}) == 50

    def test_total_tokens_computed(self) -> None:
        assert extract_total_tokens({}, 100, 50) == 150

    def test_reasoning_tokens(self) -> None:
        assert extract_reasoning_tokens({"weave.usage.reasoning_tokens": 30}) == 30

    def test_zero_on_missing(self) -> None:
        assert extract_input_tokens({}) == 0
        assert extract_output_tokens({}) == 0
        assert extract_reasoning_tokens({}) == 0


# ============================================================================
# Conversation extraction
# ============================================================================


class TestConversation:
    def test_conversation_id(self) -> None:
        assert extract_conversation_id({"weave.conversation.id": "conv-1"}) == "conv-1"
        assert extract_conversation_id({"gen_ai.conversation.id": "conv-2"}) == "conv-2"
        assert extract_conversation_id({}) == ""

    def test_conversation_name(self) -> None:
        assert (
            extract_conversation_name({"weave.conversation.name": "My Chat"})
            == "My Chat"
        )
        assert extract_conversation_name({}) == ""


# ============================================================================
# Finish reasons
# ============================================================================


class TestFinishReasons:
    def test_list(self) -> None:
        assert extract_finish_reasons({"weave.response.finish_reasons": ["stop"]}) == [
            "stop"
        ]

    def test_string(self) -> None:
        assert extract_finish_reasons({"gen_ai.response.finish_reasons": "stop"}) == [
            "stop"
        ]

    def test_empty(self) -> None:
        assert extract_finish_reasons({}) == []


# ============================================================================
# Tool call extraction
# ============================================================================


class TestToolCallExtraction:
    def test_arguments_from_attrs(self) -> None:
        result = extract_tool_call_arguments(
            {"weave.tool.call.arguments": '{"city": "Paris"}'}, []
        )
        assert result == '{"city": "Paris"}'

    def test_arguments_from_event(self) -> None:
        events = [
            {
                "name": "gen_ai.tool.input",
                "attributes": {"gen_ai.tool.call.arguments": '{"x": 1}'},
            }
        ]
        result = extract_tool_call_arguments({}, events)
        assert result == '{"x": 1}'

    def test_arguments_empty(self) -> None:
        assert extract_tool_call_arguments({}, []) == ""

    def test_result_from_attrs(self) -> None:
        result = extract_tool_call_result({"weave.tool.call.result": '"sunny"'}, [])
        assert result == '"sunny"'

    def test_result_from_event(self) -> None:
        events = [
            {
                "name": "gen_ai.tool.output",
                "attributes": {"gen_ai.tool.call.result": '"rainy"'},
            }
        ]
        result = extract_tool_call_result({}, events)
        assert result == '"rainy"'


# ============================================================================
# Reasoning content
# ============================================================================


class TestReasoningContent:
    def test_from_parts(self) -> None:
        raw = [{"parts": [{"type": "reasoning", "content": "Let me think..."}]}]
        assert extract_reasoning_content(raw) == "Let me think..."

    def test_no_reasoning(self) -> None:
        raw = [{"parts": [{"type": "text", "content": "Hello"}]}]
        assert extract_reasoning_content(raw) == ""

    def test_none(self) -> None:
        assert extract_reasoning_content(None) == ""

    def test_json_string(self) -> None:
        import json

        raw = json.dumps([{"parts": [{"type": "reasoning", "content": "hmm"}]}])
        assert extract_reasoning_content(raw) == "hmm"


# ============================================================================
# Full extract_genai_span
# ============================================================================


class TestExtractGenaiSpan:
    def test_basic_chat_span(self) -> None:
        span = _make_span(
            attrs={
                "gen_ai.operation.name": "chat",
                "gen_ai.provider.name": "openai",
                "gen_ai.request.model": "gpt-4o",
                "gen_ai.response.model": "gpt-4o-2024-05-13",
                "gen_ai.usage.input_tokens": 100,
                "gen_ai.usage.output_tokens": 50,
                "gen_ai.response.finish_reasons": ["stop"],
                "gen_ai.request.temperature": 0.7,
                "gen_ai.input.messages": [{"role": "user", "content": "Hello"}],
                "gen_ai.output.messages": [
                    {"role": "assistant", "content": "Hi there!"}
                ],
            },
            name="chat gpt-4o",
        )
        result = extract_genai_span(span, project_id="proj-1", wb_user_id="user-1")

        assert result.project_id == "proj-1"
        assert result.operation_name == "chat"
        assert result.provider_name == "openai"
        assert result.request_model == "gpt-4o"
        assert result.response_model == "gpt-4o-2024-05-13"
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.total_tokens == 150
        assert result.finish_reasons == ["stop"]
        assert result.request_temperature == 0.7
        assert len(result.input_messages) == 1
        assert result.input_messages[0].role == "user"
        assert result.input_messages[0].content == "Hello"
        assert len(result.output_messages) == 1
        assert result.output_messages[0].content == "Hi there!"
        assert result.wb_user_id == "user-1"
        assert result.status_code == "OK"

    def test_weave_keys_take_priority(self) -> None:
        span = _make_span(
            attrs={
                "weave.provider.name": "weave-provider",
                "gen_ai.provider.name": "genai-provider",
                "weave.agent.name": "weave-agent",
                "gen_ai.agent.name": "genai-agent",
            }
        )
        result = extract_genai_span(span, project_id="p1")
        assert result.provider_name == "weave-provider"
        assert result.agent_name == "weave-agent"

    def test_tool_span(self) -> None:
        span = _make_span(
            attrs={
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": "get_weather",
                "gen_ai.tool.type": "function",
                "gen_ai.tool.call.id": "call_123",
                "gen_ai.tool.call.arguments": '{"city": "Paris"}',
                "gen_ai.tool.call.result": '{"temp": 20}',
            },
            name="execute_tool get_weather",
        )
        result = extract_genai_span(span, project_id="p1")
        assert result.operation_name == "execute_tool"
        assert result.tool_name == "get_weather"
        assert result.tool_type == "function"
        assert result.tool_call_id == "call_123"
        assert result.tool_call_arguments == '{"city": "Paris"}'
        assert result.tool_call_result == '{"temp": 20}'

    def test_agent_span(self) -> None:
        span = _make_span(
            attrs={
                "gen_ai.operation.name": "invoke_agent",
                "gen_ai.agent.name": "travel-bot",
                "gen_ai.agent.id": "agent-001",
                "gen_ai.agent.version": "1.2.3",
                "gen_ai.conversation.id": "conv-abc",
            }
        )
        result = extract_genai_span(span, project_id="p1")
        assert result.operation_name == "invoke_agent"
        assert result.agent_name == "travel-bot"
        assert result.agent_id == "agent-001"
        assert result.agent_version == "1.2.3"
        assert result.conversation_id == "conv-abc"

    def test_custom_attrs_overflow(self) -> None:
        span = _make_span(
            attrs={
                "gen_ai.operation.name": "chat",
                "my.custom.string": "hello",
                "my.custom.int": 42,
                "my.custom.float": 3.14,
            }
        )
        result = extract_genai_span(span, project_id="p1")
        assert result.custom_attrs["my.custom.string"] == "hello"
        assert result.custom_attrs_int["my.custom.int"] == 42
        assert result.custom_attrs_float["my.custom.float"] == 3.14

    def test_weave_extensions(self) -> None:
        span = _make_span(
            attrs={
                "weave.compaction.summary": "Summarized 10 items",
                "weave.compaction.items_before": 10,
                "weave.compaction.items_after": 3,
                "weave.content_refs": ["ref1", "ref2"],
            }
        )
        result = extract_genai_span(span, project_id="p1")
        assert result.compaction_summary == "Summarized 10 items"
        assert result.compaction_items_before == 10
        assert result.compaction_items_after == 3
        assert result.content_refs == ["ref1", "ref2"]

    def test_error_span(self) -> None:
        span = _make_span(
            attrs={"error.type": "RateLimitError"},
        )
        span.status = Status(code=StatusCode.ERROR, message="rate limited")
        result = extract_genai_span(span, project_id="p1")
        assert result.status_code == "ERROR"
        assert result.status_message == "rate limited"
        assert result.error_type == "RateLimitError"

    def test_raw_dumps_populated(self) -> None:
        span = _make_span(attrs={"gen_ai.operation.name": "chat"})
        result = extract_genai_span(span, project_id="p1")
        assert result.raw_span_dump != ""
        assert result.attributes_dump != ""

    def test_message_normalization(self) -> None:
        span = _make_span(
            attrs={
                "gen_ai.input.messages": [
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Hi"},
                ],
                "gen_ai.output.messages": [
                    {"role": "assistant", "content": "Hello!", "finish_reason": "stop"},
                ],
            }
        )
        result = extract_genai_span(span, project_id="p1")
        assert len(result.input_messages) == 2
        assert result.input_messages[0].role == "system"
        assert result.input_messages[1].role == "user"
        assert result.output_messages[0].finish_reason == "stop"
