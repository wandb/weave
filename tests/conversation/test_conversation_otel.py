"""Tests for OTel GenAI attribute builders and span emission in conversation_otel.py."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import NoOpTracerProvider, StatusCode

from weave.conversation.adapters.openai import (
    message_from_openai_responses_input,
    reasoning_from_openai_responses,
    usage_from_openai_responses,
)
from weave.conversation.conversation import (
    LLM,
    BlobPart,
    Conversation,
    LogResult,
    MediaAttachment,
    Message,
    Reasoning,
    ReasoningPart,
    SubAgent,
    TextPart,
    Tool,
    ToolCallPart,
    ToolCallResponsePart,
    Turn,
    UriPart,
    Usage,
    log_conversation,
    log_turn,
    start_conversation,
    start_llm,
    start_tool,
    start_turn,
)
from weave.conversation.conversation_otel import (
    execute_tool_attributes,
    invoke_agent_attributes,
    llm_attributes,
)


def _emit_llm_with(
    otel_spans: InMemorySpanExporter,
    *,
    model: str = "gpt-4o",
    provider_name: str = "openai",
    input_messages: list[Message] | None = None,
    output_messages: list[Message] | None = None,
    media_attachments: list[MediaAttachment] | None = None,
    usage: Usage | None = None,
    reasoning: Reasoning | str | None = None,
    response_id: str | None = None,
    finish_reasons: list[str] | None = None,
    # response_model and output_type are intentionally omitted; tests that
    # need them set the field directly on the LLM span before recording.
) -> dict[str, Any]:
    """Build a conversation+turn+LLM span with the given fields and return the
    chat span's emitted OTel attributes.

    Used by interface-level tests to assert on what callers actually see
    on the wire — ``gen_ai.input.messages``, ``gen_ai.usage.*``, etc. —
    rather than on intermediate Pydantic shape. Clears the exporter
    first so the helper is safe to call multiple times in a single test.
    """
    otel_spans.clear()
    with (
        start_conversation(agent_name="bot", conversation_id="convo-llm-chain") as s,
        s.start_turn(),
    ):
        with start_llm(model=model, provider_name=provider_name) as llm:
            llm.record(
                input_messages=input_messages,
                output_messages=output_messages,
                media_attachments=media_attachments,
                usage=usage,
                reasoning=reasoning,
                response_id=response_id,
                finish_reasons=finish_reasons,
            )
    chat_spans = [
        sp for sp in otel_spans.get_finished_spans() if sp.name == f"chat {model}"
    ]
    assert len(chat_spans) == 1, f"expected 1 chat span, got {len(chat_spans)}"
    return dict(chat_spans[0].attributes or {})


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

    def test_system_instructions_serialized(self) -> None:
        attrs = invoke_agent_attributes(
            agent_name="bot", system_instructions=["Be helpful", "Be concise"]
        )
        # Same TextPart array shape as the chat span (per semconv).
        assert json.loads(attrs["gen_ai.system_instructions"]) == [
            {"type": "text", "content": "Be helpful"},
            {"type": "text", "content": "Be concise"},
        ]

    def test_empty_system_instructions_omitted(self) -> None:
        attrs = invoke_agent_attributes(agent_name="bot", system_instructions=[])
        assert "gen_ai.system_instructions" not in attrs

    def test_none_system_instructions_omitted(self) -> None:
        attrs = invoke_agent_attributes(agent_name="bot", system_instructions=None)
        assert "gen_ai.system_instructions" not in attrs

    def test_input_messages_serialized(self) -> None:
        msgs = [Message(role="user", content="Hello")]
        attrs = invoke_agent_attributes(agent_name="bot", input_messages=msgs)
        raw = json.loads(attrs["gen_ai.input.messages"])
        assert raw == [
            {"role": "user", "parts": [{"type": "text", "content": "Hello"}]}
        ]

    def test_output_messages_serialized(self) -> None:
        msgs = [Message(role="assistant", content="Hi there!")]
        attrs = invoke_agent_attributes(agent_name="bot", output_messages=msgs)
        raw = json.loads(attrs["gen_ai.output.messages"])
        assert raw == [
            {"role": "assistant", "parts": [{"type": "text", "content": "Hi there!"}]}
        ]

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

    def test_message_shape_is_role_plus_parts(self) -> None:
        """A serialized message has only 'role' and 'parts' at the top level."""
        msgs = [Message(role="user", content="hi")]
        attrs = invoke_agent_attributes(agent_name="bot", input_messages=msgs)
        raw = json.loads(attrs["gen_ai.input.messages"])
        assert set(raw[0].keys()) == {"role", "parts"}

    def test_multiple_messages(self) -> None:
        msgs = [
            Message(role="user", content="Hi"),
            Message(role="assistant", content="Hello!"),
        ]
        attrs = invoke_agent_attributes(agent_name="bot", input_messages=msgs)
        raw = json.loads(attrs["gen_ai.input.messages"])
        assert raw == [
            {"role": "user", "parts": [{"type": "text", "content": "Hi"}]},
            {"role": "assistant", "parts": [{"type": "text", "content": "Hello!"}]},
        ]

    def test_tool_message_serializes_to_tool_call_response_part(self) -> None:
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
        # Per semconv, role:tool messages carry a single ToolCallResponsePart.
        # tool_name has no field on ToolCallResponsePart and is intentionally dropped.
        assert raw == [
            {
                "role": "tool",
                "parts": [
                    {"type": "tool_call_response", "response": "result", "id": "tc_1"}
                ],
            }
        ]

    def test_tool_message_without_id_omits_id(self) -> None:
        msgs = [Message(role="tool", content="ok")]
        attrs = invoke_agent_attributes(agent_name="bot", input_messages=msgs)
        raw = json.loads(attrs["gen_ai.input.messages"])
        assert raw[0]["parts"] == [{"type": "tool_call_response", "response": "ok"}]

    def test_message_with_empty_content_emits_empty_parts(self) -> None:
        msgs = [Message(role="assistant")]
        attrs = invoke_agent_attributes(agent_name="bot", output_messages=msgs)
        raw = json.loads(attrs["gen_ai.output.messages"])
        assert raw == [{"role": "assistant", "parts": []}]


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
        # system_instructions: array of TextParts per semconv
        assert json.loads(attrs["gen_ai.system_instructions"]) == [
            {"type": "text", "content": "Be helpful"},
            {"type": "text", "content": "Be concise"},
        ]
        # input messages: parts model
        assert json.loads(attrs["gen_ai.input.messages"]) == [
            {"role": "user", "parts": [{"type": "text", "content": "Hello"}]}
        ]
        # output messages: parts model + finish_reason on the last message
        assert json.loads(attrs["gen_ai.output.messages"]) == [
            {
                "role": "assistant",
                "parts": [{"type": "text", "content": "Hi!"}],
                "finish_reason": "stop",
            }
        ]

    def test_conversation_id(self) -> None:
        attrs = llm_attributes(model="gpt-4o", conversation_id="convo-abc")
        assert attrs["gen_ai.conversation.id"] == "convo-abc"

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

    def test_reasoning_prepended_to_last_assistant_message(self) -> None:
        """Reasoning becomes a ReasoningPart on the last assistant output message."""
        attrs = llm_attributes(
            model="gpt-4o",
            reasoning=Reasoning(content="thinking..."),
            output_messages=[
                Message(role="assistant", content="answer"),
            ],
        )
        raw = json.loads(attrs["gen_ai.output.messages"])
        assert raw == [
            {
                "role": "assistant",
                "parts": [
                    {"type": "reasoning", "content": "thinking..."},
                    {"type": "text", "content": "answer"},
                ],
            }
        ]
        # reasoning must NOT be a separate top-level attribute
        assert "gen_ai.reasoning" not in attrs
        assert "gen_ai.reasoning.content" not in attrs

    def test_reasoning_creates_synthetic_assistant_when_no_output_messages(
        self,
    ) -> None:
        """With reasoning but no output messages, a synthetic assistant message
        is created to carry the ReasoningPart.
        """
        attrs = llm_attributes(
            model="gpt-4o", reasoning=Reasoning(content="just thinking")
        )
        raw = json.loads(attrs["gen_ai.output.messages"])
        assert raw == [
            {
                "role": "assistant",
                "parts": [{"type": "reasoning", "content": "just thinking"}],
            }
        ]

    def test_empty_reasoning_does_not_emit_output_messages(self) -> None:
        attrs = llm_attributes(model="gpt-4o", reasoning=Reasoning(content=""))
        assert "gen_ai.output.messages" not in attrs

    def test_finish_reason_attached_to_last_output_message(self) -> None:
        attrs = llm_attributes(
            model="gpt-4o",
            output_messages=[
                Message(role="assistant", content="first"),
                Message(role="assistant", content="last"),
            ],
            finish_reasons=["length"],
        )
        raw = json.loads(attrs["gen_ai.output.messages"])
        assert "finish_reason" not in raw[0]
        assert raw[1]["finish_reason"] == "length"

    def test_attach_media_serialized_as_uri_part(self) -> None:
        ref = "weave:///test/project/object/img:v1"
        attrs = llm_attributes(
            model="gpt-4o",
            input_messages=[Message(role="user", content="what is this?")],
            media_attachments=[
                MediaAttachment(ref=ref, modality="image", mime_type="image/png")
            ],
        )
        raw = json.loads(attrs["gen_ai.input.messages"])
        assert raw == [
            {
                "role": "user",
                "parts": [
                    {"type": "text", "content": "what is this?"},
                    {
                        "type": "uri",
                        "mime_type": "image/png",
                        "modality": "image",
                        "uri": ref,
                    },
                ],
            }
        ]

    def test_content_refs_emitted(self) -> None:
        ref = "weave:///test/project/object/img:v1"
        attrs = llm_attributes(
            model="gpt-4o",
            input_messages=[Message(role="user", content="describe")],
            media_attachments=[
                MediaAttachment(ref=ref, modality="image", mime_type="image/jpeg")
            ],
        )
        assert attrs["weave.content_refs"] == [ref]

    def test_media_attached_to_last_user_message(self) -> None:
        """When multiple user messages exist, media goes on the most recent one."""
        ref = "weave:///test/project/object/img:v1"
        attrs = llm_attributes(
            model="gpt-4o",
            input_messages=[
                Message(role="user", content="first"),
                Message(role="assistant", content="ok"),
                Message(role="user", content="last"),
            ],
            media_attachments=[
                MediaAttachment(ref=ref, modality="image", mime_type="image/png")
            ],
        )
        raw = json.loads(attrs["gen_ai.input.messages"])
        # First user has no media
        assert raw[0]["parts"] == [{"type": "text", "content": "first"}]
        # Assistant in middle has no media
        assert raw[1]["parts"] == [{"type": "text", "content": "ok"}]
        # Last user has the media part appended
        assert any(p["type"] == "uri" for p in raw[2]["parts"])

    def test_media_with_no_input_messages_omits_messages(self) -> None:
        """Media without any input messages produces no input.messages attr.

        We don't synthesize a user message just to carry orphan media — the
        SDK's contract is that media decorates a user message, and a
        media-only LLM call is degenerate.
        """
        ref = "weave:///test/project/object/img:v1"
        attrs = llm_attributes(
            model="gpt-4o",
            media_attachments=[
                MediaAttachment(ref=ref, modality="image", mime_type="image/png")
            ],
        )
        assert "gen_ai.input.messages" not in attrs
        assert attrs["weave.content_refs"] == [ref]

    def test_multiple_media_all_on_last_user_message(self) -> None:
        ref1 = "weave:///test/project/object/img1:v1"
        ref2 = "weave:///test/project/object/img2:v1"
        attrs = llm_attributes(
            model="gpt-4o",
            input_messages=[Message(role="user", content="hi")],
            media_attachments=[
                MediaAttachment(ref=ref1, modality="image", mime_type="image/png"),
                MediaAttachment(ref=ref2, modality="image", mime_type="image/png"),
            ],
        )
        raw = json.loads(attrs["gen_ai.input.messages"])
        assert len(raw[0]["parts"]) == 3  # text + 2 media
        assert raw[0]["parts"][1]["uri"] == ref1
        assert raw[0]["parts"][2]["uri"] == ref2
        assert attrs["weave.content_refs"] == [ref1, ref2]

    def test_system_instructions_serialized_as_text_parts(self) -> None:
        attrs = llm_attributes(
            model="gpt-4o", system_instructions=["Be helpful", "Be brief"]
        )
        raw = json.loads(attrs["gen_ai.system_instructions"])
        assert raw == [
            {"type": "text", "content": "Be helpful"},
            {"type": "text", "content": "Be brief"},
        ]

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
        attrs = execute_tool_attributes(tool_name="search", conversation_id="convo-abc")
        assert attrs["gen_ai.conversation.id"] == "convo-abc"

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

    def test_tool_metadata_emitted(self) -> None:
        attrs = execute_tool_attributes(
            tool_name="search",
            tool_type="function",
            tool_description="Search the web for a query",
            tool_definitions='[{"name":"search","parameters":{}}]',
        )
        assert attrs["gen_ai.tool.type"] == "function"
        assert attrs["gen_ai.tool.description"] == "Search the web for a query"
        assert attrs["gen_ai.tool.definitions"] == '[{"name":"search","parameters":{}}]'

    def test_empty_tool_metadata_omitted(self) -> None:
        attrs = execute_tool_attributes(
            tool_name="search",
            tool_type="",
            tool_description="",
            tool_definitions="",
        )
        assert "gen_ai.tool.type" not in attrs
        assert "gen_ai.tool.description" not in attrs
        assert "gen_ai.tool.definitions" not in attrs


class TestInvokeAgentAgentMetadata:
    def test_agent_metadata_emitted(self) -> None:
        attrs = invoke_agent_attributes(
            agent_name="bot",
            agent_id="agent-001",
            agent_description="Travel assistant",
            agent_version="1.2.3",
        )
        assert attrs["gen_ai.agent.id"] == "agent-001"
        assert attrs["gen_ai.agent.description"] == "Travel assistant"
        assert attrs["gen_ai.agent.version"] == "1.2.3"

    def test_empty_agent_metadata_omitted(self) -> None:
        attrs = invoke_agent_attributes(
            agent_name="bot",
            agent_id="",
            agent_description="",
            agent_version="",
        )
        assert "gen_ai.agent.id" not in attrs
        assert "gen_ai.agent.description" not in attrs
        assert "gen_ai.agent.version" not in attrs


class TestLLMRequestParams:
    def test_request_params_emitted(self) -> None:
        attrs = llm_attributes(
            model="gpt-4o",
            request_temperature=0.7,
            request_max_tokens=2048,
            request_top_p=0.95,
            request_frequency_penalty=0.1,
            request_presence_penalty=0.2,
            request_seed=42,
            request_stop_sequences=["\n\n", "END"],
            request_choice_count=3,
        )
        assert attrs["gen_ai.request.temperature"] == 0.7
        assert attrs["gen_ai.request.max_tokens"] == 2048
        assert attrs["gen_ai.request.top_p"] == 0.95
        assert attrs["gen_ai.request.frequency_penalty"] == 0.1
        assert attrs["gen_ai.request.presence_penalty"] == 0.2
        assert attrs["gen_ai.request.seed"] == 42
        assert attrs["gen_ai.request.stop_sequences"] == ["\n\n", "END"]
        assert attrs["gen_ai.request.choice.count"] == 3

    def test_zero_temperature_is_emitted(self) -> None:
        """0.0 is a meaningful value (greedy sampling); only None is omitted."""
        attrs = llm_attributes(model="gpt-4o", request_temperature=0.0)
        assert attrs["gen_ai.request.temperature"] == 0.0

    def test_none_request_params_omitted(self) -> None:
        attrs = llm_attributes(
            model="gpt-4o",
            request_temperature=None,
            request_max_tokens=None,
            request_top_p=None,
            request_frequency_penalty=None,
            request_presence_penalty=None,
            request_seed=None,
            request_stop_sequences=None,
            request_choice_count=None,
        )
        assert "gen_ai.request.temperature" not in attrs
        assert "gen_ai.request.max_tokens" not in attrs
        assert "gen_ai.request.top_p" not in attrs
        assert "gen_ai.request.frequency_penalty" not in attrs
        assert "gen_ai.request.presence_penalty" not in attrs
        assert "gen_ai.request.seed" not in attrs
        assert "gen_ai.request.stop_sequences" not in attrs
        assert "gen_ai.request.choice.count" not in attrs

    def test_empty_stop_sequences_omitted(self) -> None:
        attrs = llm_attributes(model="gpt-4o", request_stop_sequences=[])
        assert "gen_ai.request.stop_sequences" not in attrs


class TestLLMResponseAndOutputType:
    def test_response_model_emitted(self) -> None:
        attrs = llm_attributes(model="gpt-4o", response_model="gpt-4o-2024-05-13")
        assert attrs["gen_ai.response.model"] == "gpt-4o-2024-05-13"

    def test_empty_response_model_omitted(self) -> None:
        attrs = llm_attributes(model="gpt-4o", response_model="")
        assert "gen_ai.response.model" not in attrs

    def test_output_type_emitted(self) -> None:
        attrs = llm_attributes(model="gpt-4o", output_type="json")
        assert attrs["gen_ai.output.type"] == "json"

    def test_empty_output_type_omitted(self) -> None:
        attrs = llm_attributes(model="gpt-4o", output_type="")
        assert "gen_ai.output.type" not in attrs


class TestUsageCacheTokens:
    def test_cache_tokens_emitted(self) -> None:
        usage = Usage(
            input_tokens=10,
            output_tokens=5,
            cache_creation_input_tokens=200,
            cache_read_input_tokens=50,
        )
        attrs = llm_attributes(model="gpt-4o", usage=usage)
        assert attrs["gen_ai.usage.cache_creation.input_tokens"] == 200
        assert attrs["gen_ai.usage.cache_read.input_tokens"] == 50

    def test_zero_cache_tokens_omitted(self) -> None:
        usage = Usage(
            input_tokens=10,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        )
        attrs = llm_attributes(model="gpt-4o", usage=usage)
        assert "gen_ai.usage.cache_creation.input_tokens" not in attrs
        assert "gen_ai.usage.cache_read.input_tokens" not in attrs


# ---------------------------------------------------------------------------
# Explicit Message.parts (native parts API)
# ---------------------------------------------------------------------------


class TestExplicitMessageParts:
    def test_text_part_serializes(self) -> None:
        msg = Message(role="user", parts=[TextPart(content="hello")])
        attrs = invoke_agent_attributes(agent_name="bot", input_messages=[msg])
        raw = json.loads(attrs["gen_ai.input.messages"])
        assert raw == [
            {"role": "user", "parts": [{"type": "text", "content": "hello"}]}
        ]

    def test_tool_call_part_serializes(self) -> None:
        msg = Message(
            role="assistant",
            parts=[
                TextPart(content="Let me check."),
                ToolCallPart(id="c1", name="get_weather", arguments='{"city":"Paris"}'),
            ],
        )
        attrs = invoke_agent_attributes(agent_name="bot", output_messages=[msg])
        raw = json.loads(attrs["gen_ai.output.messages"])
        assert raw == [
            {
                "role": "assistant",
                "parts": [
                    {"type": "text", "content": "Let me check."},
                    {
                        "type": "tool_call",
                        "id": "c1",
                        "name": "get_weather",
                        "arguments": '{"city":"Paris"}',
                    },
                ],
            }
        ]

    def test_tool_call_response_part_serializes(self) -> None:
        msg = Message(
            role="tool",
            parts=[ToolCallResponsePart(id="c1", response='{"temp":75}')],
        )
        attrs = invoke_agent_attributes(agent_name="bot", input_messages=[msg])
        raw = json.loads(attrs["gen_ai.input.messages"])
        assert raw == [
            {
                "role": "tool",
                "parts": [
                    {
                        "type": "tool_call_response",
                        "id": "c1",
                        "response": '{"temp":75}',
                    }
                ],
            }
        ]

    def test_reasoning_part_in_explicit_parts_skips_auto_prepend(self) -> None:
        """When the caller embeds a ReasoningPart, the auto-prepend is suppressed."""
        msg = Message(
            role="assistant",
            parts=[
                ReasoningPart(content="user wants weather"),
                TextPart(content="The weather is 75F"),
            ],
        )
        attrs = llm_attributes(
            model="gpt-4o",
            output_messages=[msg],
            reasoning=Reasoning(content="this would normally be auto-prepended"),
        )
        raw = json.loads(attrs["gen_ai.output.messages"])
        # Only the explicit ReasoningPart appears — no double-add.
        reasoning_parts = [p for p in raw[0]["parts"] if p["type"] == "reasoning"]
        assert len(reasoning_parts) == 1
        assert reasoning_parts[0]["content"] == "user wants weather"

    def test_explicit_parts_take_precedence_over_flat_content(self) -> None:
        """When parts is set, content is ignored."""
        msg = Message(
            role="assistant",
            content="ignored flat content",
            parts=[TextPart(content="canonical text")],
        )
        attrs = invoke_agent_attributes(agent_name="bot", output_messages=[msg])
        raw = json.loads(attrs["gen_ai.output.messages"])
        texts = [p for p in raw[0]["parts"] if p["type"] == "text"]
        assert texts == [{"type": "text", "content": "canonical text"}]

    def test_blob_uri_file_parts_serialize(self) -> None:
        msg = Message(
            role="user",
            parts=[
                BlobPart(mime_type="image/png", modality="image", content="aGVsbG8="),
                UriPart(
                    mime_type="image/jpeg",
                    modality="image",
                    uri="https://example.com/img.jpg",
                ),
            ],
        )
        attrs = invoke_agent_attributes(agent_name="bot", input_messages=[msg])
        raw = json.loads(attrs["gen_ai.input.messages"])
        types_seen = [p["type"] for p in raw[0]["parts"]]
        assert types_seen == ["blob", "uri"]
        assert raw[0]["parts"][0]["content"] == "aGVsbG8="
        assert raw[0]["parts"][1]["uri"] == "https://example.com/img.jpg"

    def test_media_attachments_appended_to_explicit_parts(self) -> None:
        """media_attachments still extend the last user message even with explicit parts."""
        ref = "weave:///test/project/object/img:v1"
        msg = Message(role="user", parts=[TextPart(content="see this")])
        media = [MediaAttachment(ref=ref, modality="image", mime_type="image/png")]
        attrs = llm_attributes(
            model="gpt-4o", input_messages=[msg], media_attachments=media
        )
        raw = json.loads(attrs["gen_ai.input.messages"])
        types_seen = [p["type"] for p in raw[0]["parts"]]
        assert types_seen == ["text", "uri"]

    def test_back_compat_flat_content_still_works(self) -> None:
        """Existing API users (content-only) keep producing the same output."""
        msg = Message(role="assistant", content="hello")
        attrs = invoke_agent_attributes(agent_name="bot", output_messages=[msg])
        raw = json.loads(attrs["gen_ai.output.messages"])
        assert raw == [
            {"role": "assistant", "parts": [{"type": "text", "content": "hello"}]}
        ]

    def test_back_compat_tool_role_with_flat_content(self) -> None:
        msg = Message(role="tool", content='{"temp":75}', tool_call_id="c1")
        attrs = invoke_agent_attributes(agent_name="bot", input_messages=[msg])
        raw = json.loads(attrs["gen_ai.input.messages"])
        assert raw == [
            {
                "role": "tool",
                "parts": [
                    {
                        "type": "tool_call_response",
                        "response": '{"temp":75}',
                        "id": "c1",
                    }
                ],
            }
        ]

    def test_finish_reason_attached_with_explicit_parts(self) -> None:
        msg = Message(role="assistant", parts=[TextPart(content="done")])
        attrs = llm_attributes(
            model="gpt-4o", output_messages=[msg], finish_reasons=["stop"]
        )
        raw = json.loads(attrs["gen_ai.output.messages"])
        assert raw[0]["finish_reason"] == "stop"


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
        with Conversation(
            agent_name="weather-bot",
            conversation_id="convo-1",
            conversation_name="Weather Chat",
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
        assert attrs["gen_ai.conversation.id"] == "convo-1"
        assert attrs["gen_ai.conversation.name"] == "Weather Chat"

    def test_turn_system_instructions_emitted_on_span(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(agent_name="weather-bot", conversation_id="convo-si") as s:
            with s.start_turn(user_message="hi") as turn:
                turn.system_instructions = ["You are a weather bot"]

        spans = otel_spans.get_finished_spans()
        turn_spans = [sp for sp in spans if sp.name == "invoke_agent weather-bot"]
        assert len(turn_spans) == 1
        attrs = dict(turn_spans[0].attributes or {})
        assert json.loads(attrs["gen_ai.system_instructions"]) == [
            {"type": "text", "content": "You are a weather bot"},
        ]

    def test_turn_system_instructions_omitted_when_content_excluded(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(
            agent_name="bot", conversation_id="convo-si2", include_content=False
        ) as s:
            with s.start_turn() as turn:
                turn.system_instructions = ["secret prompt"]

        spans = otel_spans.get_finished_spans()
        turn_spans = [sp for sp in spans if sp.name == "invoke_agent bot"]
        assert len(turn_spans) == 1
        attrs = dict(turn_spans[0].attributes or {})
        assert "gen_ai.system_instructions" not in attrs

    def test_start_turn_system_instructions_param_emitted_on_span(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(
            agent_name="weather-bot", conversation_id="convo-si-param"
        ) as s:
            with s.start_turn(system_instructions=["You are a weather bot"]):
                pass

        spans = otel_spans.get_finished_spans()
        turn_spans = [sp for sp in spans if sp.name == "invoke_agent weather-bot"]
        assert len(turn_spans) == 1
        attrs = dict(turn_spans[0].attributes or {})
        assert json.loads(attrs["gen_ai.system_instructions"]) == [
            {"type": "text", "content": "You are a weather bot"},
        ]

    def test_module_start_turn_system_instructions_param(self) -> None:
        # weave.start_turn(...) wires the field onto the returned Turn whether
        # or not a conversation is active (delegates to Conversation.start_turn when one is).
        turn = start_turn(system_instructions=["You are a weather bot"])
        assert turn.system_instructions == ["You are a weather bot"]

    def test_llm_creates_chat_span(self, otel_spans: InMemorySpanExporter) -> None:
        with Conversation(agent_name="bot", conversation_id="convo-llm") as s:
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
        assert attrs["gen_ai.conversation.id"] == "convo-llm"
        assert attrs["gen_ai.usage.input_tokens"] == 100
        assert attrs["gen_ai.usage.output_tokens"] == 50

    def test_tool_creates_execute_tool_span(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(agent_name="bot", conversation_id="convo-tool") as s:
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
        assert attrs["gen_ai.conversation.id"] == "convo-tool"
        assert attrs["gen_ai.tool.call.id"] == "tc_1"
        assert attrs["gen_ai.tool.call.arguments"] == '{"city":"Tokyo"}'
        assert attrs["gen_ai.tool.call.result"] == "75F"

    def test_subagent_creates_nested_invoke_agent_span(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(agent_name="orchestrator") as s:
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

    def test_subagent_system_instructions_via_factory(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(agent_name="orchestrator") as s:
            with s.start_turn() as turn:
                with turn.subagent(
                    name="research-bot",
                    system_instructions=["You research things"],
                ):
                    pass

        spans = otel_spans.get_finished_spans()
        sa_spans = [sp for sp in spans if sp.name == "invoke_agent research-bot"]
        assert len(sa_spans) == 1
        attrs = dict(sa_spans[0].attributes or {})
        assert json.loads(attrs["gen_ai.system_instructions"]) == [
            {"type": "text", "content": "You research things"},
        ]

    def test_parent_child_hierarchy(self, otel_spans: InMemorySpanExporter) -> None:
        """LLM and Tool are both children of Turn (flat model)."""
        with Conversation(agent_name="bot") as s:
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
        with Conversation(agent_name="bot") as s:
            with s.start_turn() as turn:
                with turn.llm(model="gpt-4o") as llm:
                    llm.output("Hello")
                with turn.tool(name="search") as tool:
                    tool.result = "done"
        # Should not raise — just silently use no-op spans

    def test_include_content_false_omits_messages(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with Conversation(agent_name="bot", include_content=False) as s:
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

    def test_start_tool_creates_child_of_turn(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with start_conversation(agent_name="bot", conversation_id="convo-st") as s:
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
        assert attrs["gen_ai.conversation.id"] == "convo-st"
        assert attrs["gen_ai.tool.call.id"] == "tc_1"

    def test_two_turns_have_different_trace_ids(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with start_conversation(agent_name="bot") as s:
            with s.start_turn(user_message="first") as t1:
                pass
            with s.start_turn(user_message="second") as t2:
                pass

        spans = otel_spans.get_finished_spans()
        assert len(spans) == 2
        trace_ids = {sp.context.trace_id for sp in spans}
        assert len(trace_ids) == 2, "Each turn should have a distinct trace_id"


# ---------------------------------------------------------------------------
# Error recording
# ---------------------------------------------------------------------------


class TestErrorRecording:
    def test_llm_records_exception(self, otel_spans: InMemorySpanExporter) -> None:
        with start_conversation(agent_name="bot") as conversation:
            with conversation.start_turn() as turn:
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
        with start_conversation(agent_name="bot") as conversation:
            with conversation.start_turn() as turn:
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
        with start_conversation(agent_name="bot") as conversation:
            try:
                with conversation.start_turn() as turn:
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
        with start_conversation(agent_name="bot") as conversation:
            with conversation.start_turn() as turn:
                try:
                    with turn.subagent(name="sub") as sa:
                        raise RuntimeError("sub broke")
                except RuntimeError:
                    pass
        spans = otel_spans.get_finished_spans()
        sa_spans = [s for s in spans if s.attributes.get("gen_ai.agent.name") == "sub"]
        assert len(sa_spans) == 1
        assert sa_spans[0].status.status_code == StatusCode.ERROR


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
            with start_conversation(agent_name="bot") as s:
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
            with start_conversation(agent_name="bot", continue_parent_trace=True) as s:
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
        with start_conversation(agent_name="bot") as s:
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
        with start_conversation(agent_name="bot") as s:
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


# ---------------------------------------------------------------------------
# log_turn
# ---------------------------------------------------------------------------


def _ts(seconds_offset: float) -> datetime:
    """Helper for fixed-base test timestamps."""
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return base + timedelta(seconds=seconds_offset)


class TestLogTurn:
    def test_emits_turn_span_with_correct_timestamps(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        result = log_turn(
            conversation_id="convo-1",
            agent_name="weather-bot",
            conversation_name="Weather Chat",
            messages=[Message(role="user", content="What's the weather?")],
            started_at=_ts(0),
            ended_at=_ts(3),
        )

        spans = otel_spans.get_finished_spans()
        assert len(spans) == 1
        sp = spans[0]
        assert sp.name == "invoke_agent weather-bot"
        attrs = dict(sp.attributes or {})
        assert attrs["gen_ai.operation.name"] == "invoke_agent"
        assert attrs["gen_ai.agent.name"] == "weather-bot"
        assert attrs["gen_ai.conversation.id"] == "convo-1"
        assert attrs["gen_ai.conversation.name"] == "Weather Chat"
        assert sp.start_time == int(_ts(0).timestamp() * 1_000_000_000)
        assert sp.end_time == int(_ts(3).timestamp() * 1_000_000_000)

        assert isinstance(result, LogResult)
        assert result.conversation_id == "convo-1"
        assert len(result.trace_ids) == 1
        assert len(result.root_span_ids) == 1
        assert result.span_count == 1
        # IDs are W3C Trace Context lowercase hex
        assert len(result.trace_ids[0]) == 32
        assert len(result.root_span_ids[0]) == 16

    def test_with_llm_and_tool_children(self, otel_spans: InMemorySpanExporter) -> None:
        result = log_turn(
            conversation_id="convo-2",
            agent_name="bot",
            messages=[Message(role="user", content="Search for X")],
            spans=[
                LLM(
                    model="gpt-4o",
                    input_messages=[Message(role="user", content="Search for X")],
                    output_messages=[Message(role="assistant", content="Searching...")],
                    usage=Usage(input_tokens=10, output_tokens=5),
                    started_at=_ts(0),
                    ended_at=_ts(1),
                ),
                Tool(
                    name="search",
                    arguments='{"q":"X"}',
                    result="found",
                    tool_call_id="tc_1",
                    started_at=_ts(1),
                    ended_at=_ts(2),
                ),
            ],
            started_at=_ts(0),
            ended_at=_ts(3),
        )

        spans = otel_spans.get_finished_spans()
        assert len(spans) == 3
        turn_spans = [sp for sp in spans if sp.name == "invoke_agent bot"]
        llm_spans = [sp for sp in spans if sp.name == "chat gpt-4o"]
        tool_spans = [sp for sp in spans if sp.name == "execute_tool search"]
        assert len(turn_spans) == 1
        assert len(llm_spans) == 1
        assert len(tool_spans) == 1

        turn_span = turn_spans[0]
        # Children share the turn's trace_id and have it as parent
        assert llm_spans[0].context.trace_id == turn_span.context.trace_id
        assert tool_spans[0].context.trace_id == turn_span.context.trace_id
        assert llm_spans[0].parent.span_id == turn_span.context.span_id
        assert tool_spans[0].parent.span_id == turn_span.context.span_id

        # Children have explicit timestamps
        assert llm_spans[0].start_time == int(_ts(0).timestamp() * 1_000_000_000)
        assert llm_spans[0].end_time == int(_ts(1).timestamp() * 1_000_000_000)
        assert tool_spans[0].start_time == int(_ts(1).timestamp() * 1_000_000_000)
        assert tool_spans[0].end_time == int(_ts(2).timestamp() * 1_000_000_000)

        assert result.span_count == 3

    def test_with_subagent_child(self, otel_spans: InMemorySpanExporter) -> None:
        log_turn(
            conversation_id="convo-3",
            agent_name="orchestrator",
            spans=[
                SubAgent(
                    name="research-bot",
                    model="gpt-4o-mini",
                    started_at=_ts(0),
                    ended_at=_ts(2),
                ),
            ],
            started_at=_ts(0),
            ended_at=_ts(3),
        )

        spans = otel_spans.get_finished_spans()
        sa_spans = [sp for sp in spans if sp.name == "invoke_agent research-bot"]
        turn_spans = [sp for sp in spans if sp.name == "invoke_agent orchestrator"]
        assert len(sa_spans) == 1
        assert len(turn_spans) == 1
        assert sa_spans[0].parent.span_id == turn_spans[0].context.span_id

    def test_agent_identity_fields_emitted(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        log_turn(
            conversation_id="convo-ident",
            agent_name="bot",
            agent_id="agent-7",
            agent_description="A helpful bot",
            agent_version="v3",
            started_at=_ts(0),
            ended_at=_ts(1),
        )
        spans = otel_spans.get_finished_spans()
        turn_spans = [sp for sp in spans if sp.name == "invoke_agent bot"]
        assert len(turn_spans) == 1
        attrs = dict(turn_spans[0].attributes or {})
        assert attrs["gen_ai.agent.id"] == "agent-7"
        assert attrs["gen_ai.agent.description"] == "A helpful bot"
        assert attrs["gen_ai.agent.version"] == "v3"

    def test_subagent_system_instructions_emitted(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        log_turn(
            conversation_id="convo-sa-si",
            agent_name="orchestrator",
            spans=[
                SubAgent(
                    name="research-bot",
                    system_instructions=["You research things"],
                    started_at=_ts(0),
                    ended_at=_ts(1),
                ),
            ],
            started_at=_ts(0),
            ended_at=_ts(2),
        )
        spans = otel_spans.get_finished_spans()
        sa_spans = [sp for sp in spans if sp.name == "invoke_agent research-bot"]
        assert len(sa_spans) == 1
        attrs = dict(sa_spans[0].attributes or {})
        assert json.loads(attrs["gen_ai.system_instructions"]) == [
            {"type": "text", "content": "You research things"},
        ]

    def test_subagent_system_instructions_omitted_when_content_excluded(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        log_turn(
            conversation_id="convo-sa-si2",
            agent_name="orchestrator",
            include_content=False,
            spans=[
                SubAgent(
                    name="research-bot",
                    system_instructions=["secret prompt"],
                    started_at=_ts(0),
                    ended_at=_ts(1),
                ),
            ],
            started_at=_ts(0),
            ended_at=_ts(2),
        )
        spans = otel_spans.get_finished_spans()
        sa_spans = [sp for sp in spans if sp.name == "invoke_agent research-bot"]
        assert len(sa_spans) == 1
        attrs = dict(sa_spans[0].attributes or {})
        assert "gen_ai.system_instructions" not in attrs

    def test_continue_parent_trace_nests_under_outer_span(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        tracer = otel_trace.get_tracer("test.outer")
        with tracer.start_as_current_span("outer-request") as outer:
            outer_trace_id = outer.get_span_context().trace_id
            outer_span_id = outer.get_span_context().span_id
            log_turn(
                conversation_id="convo-4",
                agent_name="bot",
                started_at=_ts(0),
                ended_at=_ts(1),
                continue_parent_trace=True,
            )

        spans = otel_spans.get_finished_spans()
        turn_spans = [sp for sp in spans if sp.name == "invoke_agent bot"]
        assert len(turn_spans) == 1
        assert turn_spans[0].context.trace_id == outer_trace_id
        assert turn_spans[0].parent.span_id == outer_span_id

    def test_default_starts_new_trace_under_outer_span(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        tracer = otel_trace.get_tracer("test.outer")
        with tracer.start_as_current_span("outer-request") as outer:
            outer_trace_id = outer.get_span_context().trace_id
            log_turn(
                conversation_id="convo-5",
                agent_name="bot",
                started_at=_ts(0),
                ended_at=_ts(1),
            )

        spans = otel_spans.get_finished_spans()
        turn_spans = [sp for sp in spans if sp.name == "invoke_agent bot"]
        assert turn_spans[0].context.trace_id != outer_trace_id

    def test_include_content_false_suppresses_messages(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        log_turn(
            conversation_id="convo-6",
            agent_name="bot",
            messages=[Message(role="user", content="secret")],
            spans=[
                LLM(
                    model="gpt-4o",
                    input_messages=[Message(role="user", content="secret")],
                    output_messages=[
                        Message(role="assistant", content="secret response")
                    ],
                    system_instructions=["be helpful"],
                    started_at=_ts(0),
                    ended_at=_ts(1),
                ),
                Tool(
                    name="search",
                    arguments='{"q":"secret"}',
                    result="secret result",
                    started_at=_ts(1),
                    ended_at=_ts(2),
                ),
            ],
            started_at=_ts(0),
            ended_at=_ts(3),
            include_content=False,
        )

        spans = otel_spans.get_finished_spans()
        for sp in spans:
            attrs = dict(sp.attributes or {})
            assert "gen_ai.input.messages" not in attrs
            assert "gen_ai.output.messages" not in attrs
            assert "gen_ai.system_instructions" not in attrs
            assert "gen_ai.tool.call.arguments" not in attrs
            assert "gen_ai.tool.call.result" not in attrs

    def test_system_instructions_emitted_on_turn_span(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        log_turn(
            conversation_id="convo-si-batch",
            agent_name="bot",
            system_instructions=["You are a weather bot"],
            started_at=_ts(0),
            ended_at=_ts(1),
        )

        spans = otel_spans.get_finished_spans()
        turn_spans = [sp for sp in spans if sp.name == "invoke_agent bot"]
        assert len(turn_spans) == 1
        attrs = dict(turn_spans[0].attributes or {})
        assert json.loads(attrs["gen_ai.system_instructions"]) == [
            {"type": "text", "content": "You are a weather bot"},
        ]

    def test_no_spans_just_emits_turn(self, otel_spans: InMemorySpanExporter) -> None:
        result = log_turn(
            conversation_id="convo-7",
            agent_name="bot",
            started_at=_ts(0),
            ended_at=_ts(1),
        )
        spans = otel_spans.get_finished_spans()
        assert len(spans) == 1
        assert result.span_count == 1

    def test_falls_back_to_child_timestamps(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        # Turn timestamps not provided — should derive from children
        log_turn(
            conversation_id="convo-8",
            agent_name="bot",
            spans=[
                LLM(model="gpt-4o", started_at=_ts(0), ended_at=_ts(1)),
                Tool(name="search", started_at=_ts(2), ended_at=_ts(3)),
            ],
        )
        spans = otel_spans.get_finished_spans()
        turn_span = next(sp for sp in spans if sp.name == "invoke_agent bot")
        # Earliest child start, latest child end
        assert turn_span.start_time == int(_ts(0).timestamp() * 1_000_000_000)
        assert turn_span.end_time == int(_ts(3).timestamp() * 1_000_000_000)

    def test_returns_log_result_with_correctly_formatted_ids(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        result = log_turn(
            conversation_id="convo-9",
            agent_name="bot",
            started_at=_ts(0),
            ended_at=_ts(1),
        )
        # W3C Trace Context: trace_id is 32 hex, span_id is 16 hex, lowercase.
        assert all(c in "0123456789abcdef" for c in result.trace_ids[0])
        assert all(c in "0123456789abcdef" for c in result.root_span_ids[0])


class TestLogTurnNoOtel:
    def test_returns_log_result_when_otel_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Simulate OTel not installed.
        import weave.conversation.conversation as conversation_mod

        monkeypatch.setattr(conversation_mod, "_OTEL_AVAILABLE", False)
        result = log_turn(
            conversation_id="convo-noop",
            agent_name="bot",
            started_at=_ts(0),
            ended_at=_ts(1),
        )
        assert isinstance(result, LogResult)
        assert result.conversation_id == "convo-noop"
        assert result.trace_ids == []
        assert result.root_span_ids == []
        assert result.span_count == 0


# ---------------------------------------------------------------------------
# log_conversation
# ---------------------------------------------------------------------------


class TestLogConversation:
    def test_emits_one_trace_per_turn(self, otel_spans: InMemorySpanExporter) -> None:
        result = log_conversation(
            conversation_id="convo-multi",
            agent_name="bot",
            turns=[
                Turn(
                    agent_name="bot",
                    messages=[Message(role="user", content="first")],
                    started_at=_ts(0),
                    ended_at=_ts(1),
                ),
                Turn(
                    agent_name="bot",
                    messages=[Message(role="user", content="second")],
                    started_at=_ts(2),
                    ended_at=_ts(3),
                ),
            ],
        )
        spans = otel_spans.get_finished_spans()
        turn_spans = [sp for sp in spans if sp.name == "invoke_agent bot"]
        assert len(turn_spans) == 2
        # Distinct trace IDs for the two turns
        assert turn_spans[0].context.trace_id != turn_spans[1].context.trace_id

        assert len(result.trace_ids) == 2
        assert len(result.root_span_ids) == 2
        assert result.span_count == 2
        assert result.conversation_id == "convo-multi"

    def test_auto_generates_conversation_id_when_empty(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        result = log_conversation(
            turns=[
                Turn(agent_name="bot", started_at=_ts(0), ended_at=_ts(1)),
            ],
        )
        # Conversation ID is a UUID4 string when auto-generated
        assert result.conversation_id != ""
        assert len(result.conversation_id) == 36

    def test_continue_parent_trace_keeps_all_under_outer(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        tracer = otel_trace.get_tracer("test.outer")
        with tracer.start_as_current_span("outer-request") as outer:
            outer_trace_id = outer.get_span_context().trace_id
            log_conversation(
                conversation_id="convo-nested",
                turns=[
                    Turn(agent_name="bot", started_at=_ts(0), ended_at=_ts(1)),
                    Turn(agent_name="bot", started_at=_ts(2), ended_at=_ts(3)),
                ],
                continue_parent_trace=True,
            )
        spans = otel_spans.get_finished_spans()
        turn_spans = [sp for sp in spans if sp.name == "invoke_agent bot"]
        assert len(turn_spans) == 2
        for sp in turn_spans:
            assert sp.context.trace_id == outer_trace_id

    def test_propagates_children_from_each_turn(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        log_conversation(
            conversation_id="convo-children",
            turns=[
                Turn(
                    agent_name="bot",
                    started_at=_ts(0),
                    ended_at=_ts(2),
                    spans=[
                        LLM(model="gpt-4o", started_at=_ts(0), ended_at=_ts(1)),
                        Tool(name="search", started_at=_ts(1), ended_at=_ts(2)),
                    ],
                ),
                Turn(
                    agent_name="bot",
                    started_at=_ts(3),
                    ended_at=_ts(4),
                    spans=[LLM(model="gpt-4o", started_at=_ts(3), ended_at=_ts(4))],
                ),
            ],
        )
        spans = otel_spans.get_finished_spans()
        # 2 turns + 2 LLMs + 1 tool = 5
        assert len(spans) == 5

    def test_forwards_all_turn_fields(self, otel_spans: InMemorySpanExporter) -> None:
        # log_conversation emits the Turn it is handed, so every field survives —
        # not just the subset log_turn historically accepted as kwargs.
        log_conversation(
            conversation_id="convo-fields",
            turns=[
                Turn(
                    agent_name="bot",
                    agent_id="agent-123",
                    agent_description="A helpful bot",
                    agent_version="v2",
                    system_instructions=["You are a weather bot"],
                    started_at=_ts(0),
                    ended_at=_ts(1),
                ),
            ],
        )
        spans = otel_spans.get_finished_spans()
        turn_spans = [sp for sp in spans if sp.name == "invoke_agent bot"]
        assert len(turn_spans) == 1
        attrs = dict(turn_spans[0].attributes or {})
        assert json.loads(attrs["gen_ai.system_instructions"]) == [
            {"type": "text", "content": "You are a weather bot"},
        ]
        assert attrs["gen_ai.agent.id"] == "agent-123"
        assert attrs["gen_ai.agent.description"] == "A helpful bot"
        assert attrs["gen_ai.agent.version"] == "v2"

    def test_does_not_mutate_caller_turn(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        # log_conversation applies conversation-level defaults /
        # continue_parent_trace to a model_copy of each Turn, not the caller's
        # instance. Locks in the "without mutating the caller's object" contract
        # that model_copy exists to guarantee — a future _emit_turn edit that
        # mutated in place would break this.
        turn = Turn(started_at=_ts(0), ended_at=_ts(1))  # no agent_name / model
        log_conversation(
            conversation_id="convo-no-mutate",
            agent_name="conversation-bot",
            model="gpt-4o",
            continue_parent_trace=True,
            turns=[turn],
        )
        assert turn.agent_name == ""
        assert turn.model == ""
        assert turn.continue_parent_trace is False

    def test_empty_turns_returns_empty_log_result(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        result = log_conversation(turns=[], conversation_id="convo-empty")
        assert result.conversation_id == "convo-empty"
        assert result.trace_ids == []
        assert result.root_span_ids == []
        assert result.span_count == 0
        assert otel_spans.get_finished_spans() == ()


# ---------------------------------------------------------------------------
# Ergonomic helpers — accept structured payloads at the SDK boundary
# ---------------------------------------------------------------------------


class TestToolStructuredPayloads:
    """Tool.arguments / Tool.result accept any JSON-serializable value.

    Storage type is a permissive union so callers can do
    ``t.result = some_dict`` without manually JSON-encoding. The OTel
    string attributes still receive a JSON-encoded representation.
    """

    @pytest.mark.parametrize(
        ("field", "value", "expected_json", "expected_raw"),
        [
            # dict result → JSON-encoded at emission
            ("result", {"hits": 3, "top": "weave"}, {"hits": 3, "top": "weave"}, None),
            # list arguments → JSON-encoded at emission
            ("arguments", [1, 2, 3], [1, 2, 3], None),
            # string passes through unchanged (no double-encoding)
            ("result", "already a string", None, "already a string"),
            # None → attribute is omitted entirely
            ("result", None, None, ...),
        ],
        ids=["dict_result", "list_arguments", "string_passthrough", "none_omitted"],
    )
    def test_payload_emitted_as_json_string(
        self,
        otel_spans: InMemorySpanExporter,
        field: str,
        value: object,
        expected_json: object,
        expected_raw: object,
    ) -> None:
        attr_key = f"gen_ai.tool.call.{field}"
        kwargs: dict = {"name": "tool", "tool_call_id": "tc"}
        if field == "arguments":
            kwargs["arguments"] = value
        with (
            start_conversation(
                agent_name="bot", conversation_id="convo-tool-payload"
            ) as s,
            s.start_turn(),
        ):
            with start_tool(**kwargs) as t:
                if field == "result":
                    t.result = value
        tool_spans = [
            sp
            for sp in otel_spans.get_finished_spans()
            if sp.name == "execute_tool tool"
        ]
        assert len(tool_spans) == 1
        attrs = dict(tool_spans[0].attributes or {})
        if expected_raw is ...:
            assert attr_key not in attrs
        elif expected_raw is not None:
            assert attrs[attr_key] == expected_raw
        else:
            assert json.loads(attrs[attr_key]) == expected_json


class TestToolCallPartCoercion:
    """ToolCallPart / ToolCallResponsePart accept structured inputs and
    JSON-encode at construction or assignment.

    The end-to-end coercion path (input dict → emitted attribute string)
    is covered by ``TestToolStructuredPayloads``; this class pins down
    construction-time behavior that the OTel test does not exercise:
    edge inputs (None, list) and post-construction assignment.
    """

    @pytest.mark.parametrize(
        ("part_cls", "field", "value", "expected"),
        [
            (ToolCallPart, "arguments", None, ""),
            (ToolCallPart, "arguments", [1, 2], "[1, 2]"),
            (ToolCallResponsePart, "response", None, ""),
            (ToolCallResponsePart, "response", {"ok": True}, '{"ok": true}'),
        ],
        ids=["args_none", "args_list", "resp_none", "resp_dict"],
    )
    def test_edge_inputs_coerce_to_string(
        self, part_cls: type, field: str, value: object, expected: str
    ) -> None:
        kwargs: dict[str, object] = {"id": "c", field: value}
        if part_cls is ToolCallPart:
            kwargs["name"] = "x"
        part = part_cls(**kwargs)
        assert getattr(part, field) == expected

    def test_post_construction_assignment_coerces(self) -> None:
        """validate_assignment=True ensures setattr also runs the validator."""
        part = ToolCallPart(id="c", name="x", arguments="")
        part.arguments = {"k": "v"}
        assert json.loads(part.arguments) == {"k": "v"}


class TestMessageBuilders:
    """High-level Message constructors for the common message shapes."""

    @pytest.mark.parametrize(
        ("builder", "role"),
        [
            (Message.user, "user"),
            (Message.system, "system"),
            (Message.assistant, "assistant"),
        ],
    )
    def test_text_only_constructor(self, builder, role: str) -> None:
        m = builder("hello")
        assert m.role == role
        assert m.content == "hello"
        assert m.parts == []

    def test_assistant_with_tool_calls_promotes_to_parts(self) -> None:
        """When tool_calls are provided, the message uses the parts API."""
        tc = ToolCallPart(id="c1", name="search", arguments={"q": "weave"})
        m = Message.assistant(text="let me check", tool_calls=[tc])
        assert m.role == "assistant"
        assert m.content == ""
        assert len(m.parts) == 2
        assert isinstance(m.parts[0], TextPart)
        assert m.parts[0].content == "let me check"
        assert isinstance(m.parts[1], ToolCallPart)

    def test_assistant_tool_calls_only_skips_text_part(self) -> None:
        """No leading TextPart when text is empty."""
        tc = ToolCallPart(id="c1", name="x", arguments={})
        m = Message.assistant(tool_calls=[tc])
        assert len(m.parts) == 1
        assert isinstance(m.parts[0], ToolCallPart)

    @pytest.mark.parametrize(
        ("output", "expected_response"),
        [({"answer": 42}, '{"answer": 42}'), ("ok", "ok")],
        ids=["dict", "string"],
    )
    def test_tool_result(self, output: object, expected_response: str) -> None:
        m = Message.tool_result("c1", output)
        assert m.role == "tool"
        assert len(m.parts) == 1
        part = m.parts[0]
        assert isinstance(part, ToolCallResponsePart)
        assert part.id == "c1"
        assert part.response == expected_response


class TestAttachMediaUrl:
    """LLM.attach_media_url handles data: and plain URLs uniformly."""

    _FAKE_REF = "weave:///e/p/object/c:v1"

    @pytest.fixture(autouse=True)
    def _mock_publish(self) -> None:
        with patch(
            "weave.conversation.conversation._publish_media_content",
            return_value=self._FAKE_REF,
        ):
            yield  # type: ignore[misc]

    @pytest.mark.parametrize(
        ("url", "expected_mime"),
        [
            ("data:image/png;base64,iVBORw0KGgo=", "image/png"),
            ("https://example.com/cat.png", ""),
        ],
        ids=["data_url", "plain_url"],
    )
    def test_url_produces_weave_ref(
        self,
        url: str,
        expected_mime: str,
    ) -> None:
        llm = LLM()
        llm.attach_media_url(url, modality="image")
        llm._await_uploads()
        (att,) = llm.media_attachments
        assert att.ref.startswith("weave:///")
        assert att.mime_type == expected_mime
        assert att.modality == "image"

    def test_data_url_modality_inferred_from_mime(self) -> None:
        """Modality auto-fills from mime_type when not provided."""
        llm = LLM()
        llm.attach_media_url("data:image/jpeg;base64,XXX")
        att = llm.media_attachments[0]
        assert att.modality == "image"
        assert att.mime_type == "image/jpeg"
        llm._await_uploads()

    def test_empty_url_ignored(self) -> None:
        llm = LLM()
        llm.attach_media_url("")
        assert llm.media_attachments == []

    def test_chainable(self) -> None:
        """Returns self so callers can chain."""
        llm = LLM()
        result = llm.attach_media_url("https://e.com/a.png", modality="image")
        assert result is llm
        llm._await_uploads()


class TestLLMRecord:
    """LLM.record(...) collapses N attribute assignments into one call."""

    def test_partial_record_preserves_existing(self) -> None:
        """Fields not passed (None) keep their existing values."""
        llm = LLM(model="m", provider_name="p")
        llm.response_id = "preset"
        llm.usage = Usage(input_tokens=42)
        llm.record(output_messages=[Message.assistant("hi")])
        assert llm.response_id == "preset"
        assert llm.usage.input_tokens == 42
        assert llm.output_messages == [Message.assistant("hi")]

    @pytest.mark.parametrize(
        "reasoning",
        ["flat", Reasoning(content="explicit")],
        ids=["string", "instance"],
    )
    def test_reasoning_accepts_string_or_instance(self, reasoning: object) -> None:
        llm = LLM()
        llm.record(reasoning=reasoning)
        assert isinstance(llm.reasoning, Reasoning)
        expected = reasoning if isinstance(reasoning, str) else reasoning.content
        assert llm.reasoning.content == expected

    def test_returns_self_for_chaining(self) -> None:
        llm = LLM()
        assert llm.record(response_id="x") is llm

    def test_recorded_fields_emitted_on_span(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        """End-to-end: record() values flow through to the OTel attrs."""
        attrs = _emit_llm_with(
            otel_spans,
            input_messages=[Message.user("hi")],
            output_messages=[Message.assistant("hello")],
            usage=Usage(input_tokens=3, output_tokens=2),
            reasoning="thinking...",
            response_id="r1",
            finish_reasons=["stop"],
        )
        assert attrs["gen_ai.usage.input_tokens"] == 3
        assert attrs["gen_ai.usage.output_tokens"] == 2
        assert attrs["gen_ai.response.id"] == "r1"
        assert attrs["gen_ai.response.finish_reasons"] == ("stop",)
        # Reasoning is folded into output messages as a ReasoningPart
        # prepended to the assistant message; the original text content
        # remains as a TextPart afterwards.
        out_msgs = json.loads(attrs["gen_ai.output.messages"])
        assert out_msgs[-1]["parts"] == [
            {"type": "reasoning", "content": "thinking..."},
            {"type": "text", "content": "hello"},
        ]


class TestTurnRecord:
    """Turn.record(...) collapses N attribute assignments into one call."""

    def test_partial_record_preserves_existing(self) -> None:
        """Fields not passed (None) keep their existing values."""
        turn = Turn(agent_name="bot")
        turn.agent_id = "preset"
        turn.record(system_instructions=["You are a bot"])
        assert turn.agent_id == "preset"
        assert turn.agent_name == "bot"
        assert turn.system_instructions == ["You are a bot"]

    def test_sets_all_fields(self) -> None:
        turn = Turn()
        turn.record(
            messages=[Message.user("hi")],
            system_instructions=["sys"],
            agent_name="bot",
            model="gpt-4o",
            agent_id="id-1",
            agent_description="desc",
            agent_version="v1",
        )
        assert turn.messages == [Message.user("hi")]
        assert turn.system_instructions == ["sys"]
        assert turn.agent_name == "bot"
        assert turn.model == "gpt-4o"
        assert turn.agent_id == "id-1"
        assert turn.agent_description == "desc"
        assert turn.agent_version == "v1"

    def test_returns_self_for_chaining(self) -> None:
        turn = Turn()
        assert turn.record(agent_id="x") is turn

    def test_recorded_fields_emitted_on_span(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        """End-to-end: record() values flow through to the OTel attrs."""
        with Conversation(conversation_id="convo-turn-record") as s:
            with s.start_turn(agent_name="weather-bot") as turn:
                turn.record(
                    system_instructions=["You are a weather bot"],
                    agent_id="agent-9",
                    agent_description="A helpful bot",
                    agent_version="v4",
                )

        spans = otel_spans.get_finished_spans()
        turn_spans = [sp for sp in spans if sp.name == "invoke_agent weather-bot"]
        assert len(turn_spans) == 1
        attrs = dict(turn_spans[0].attributes or {})
        assert json.loads(attrs["gen_ai.system_instructions"]) == [
            {"type": "text", "content": "You are a weather bot"},
        ]
        assert attrs["gen_ai.agent.id"] == "agent-9"
        assert attrs["gen_ai.agent.description"] == "A helpful bot"
        assert attrs["gen_ai.agent.version"] == "v4"


class TestSubAgentRecord:
    """SubAgent.record(...) collapses N attribute assignments into one call."""

    def test_partial_record_preserves_existing(self) -> None:
        """Fields not passed (None) keep their existing values."""
        sa = SubAgent(name="research-bot")
        sa.agent_id = "preset"
        sa.record(system_instructions=["You research things"])
        assert sa.agent_id == "preset"
        assert sa.name == "research-bot"
        assert sa.system_instructions == ["You research things"]

    def test_sets_all_fields(self) -> None:
        sa = SubAgent()
        sa.record(
            name="research-bot",
            model="gpt-4o-mini",
            system_instructions=["sys"],
            agent_id="id-1",
            agent_description="desc",
            agent_version="v1",
        )
        assert sa.name == "research-bot"
        assert sa.model == "gpt-4o-mini"
        assert sa.system_instructions == ["sys"]
        assert sa.agent_id == "id-1"
        assert sa.agent_description == "desc"
        assert sa.agent_version == "v1"

    def test_returns_self_for_chaining(self) -> None:
        sa = SubAgent()
        assert sa.record(agent_id="x") is sa

    def test_recorded_fields_emitted_on_span(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        """End-to-end: record() values flow through to the OTel attrs."""
        with Conversation(agent_name="orchestrator") as s:
            with s.start_turn() as turn:
                with turn.subagent(name="research-bot") as sa:
                    sa.record(
                        system_instructions=["You research things"],
                        agent_id="agent-9",
                        agent_description="A research bot",
                        agent_version="v4",
                    )

        spans = otel_spans.get_finished_spans()
        sa_spans = [sp for sp in spans if sp.name == "invoke_agent research-bot"]
        assert len(sa_spans) == 1
        attrs = dict(sa_spans[0].attributes or {})
        assert json.loads(attrs["gen_ai.system_instructions"]) == [
            {"type": "text", "content": "You research things"},
        ]
        assert attrs["gen_ai.agent.id"] == "agent-9"
        assert attrs["gen_ai.agent.description"] == "A research bot"
        assert attrs["gen_ai.agent.version"] == "v4"


class TestUsageFromOpenAIResponses:
    """``usage_from_openai_responses`` populates ``gen_ai.usage.*`` on the chat span.

    Streaming / partial OpenAI responses can have ``response.usage`` be
    ``None``, or have ``input_tokens_details`` / ``output_tokens_details``
    objects be ``None`` even when ``usage`` itself is present. The
    extractor must tolerate all three.
    """

    @staticmethod
    def _resp(usage: Any) -> Any:
        return type("R", (), {"usage": usage})()

    @staticmethod
    def _usage(**fields: Any) -> Any:
        return type("U", (), fields)()

    @staticmethod
    def _details(**fields: Any) -> Any:
        return type("D", (), fields)()

    def test_response_usage_none_emits_no_usage_attrs(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        """When usage is missing entirely, no gen_ai.usage.* attrs land
        (zeros are stripped by ``llm_attributes``).
        """
        attrs = _emit_llm_with(
            otel_spans, usage=usage_from_openai_responses(self._resp(None))
        )
        assert "gen_ai.usage.input_tokens" not in attrs
        assert "gen_ai.usage.output_tokens" not in attrs
        assert "gen_ai.usage.reasoning_tokens" not in attrs
        assert "gen_ai.usage.cache_read.input_tokens" not in attrs

    def test_full_usage_lands_on_span(self, otel_spans: InMemorySpanExporter) -> None:
        usage = self._usage(
            input_tokens=10,
            output_tokens=20,
            output_tokens_details=self._details(reasoning_tokens=5),
            input_tokens_details=self._details(cached_tokens=3),
        )
        attrs = _emit_llm_with(
            otel_spans, usage=usage_from_openai_responses(self._resp(usage))
        )
        assert attrs["gen_ai.usage.input_tokens"] == 10
        assert attrs["gen_ai.usage.output_tokens"] == 20
        assert attrs["gen_ai.usage.reasoning_tokens"] == 5
        assert attrs["gen_ai.usage.cache_read.input_tokens"] == 3

    @pytest.mark.parametrize(
        (
            "has_output_details",
            "has_input_details",
            "expected_reasoning",
            "expected_cache",
        ),
        [
            (False, False, None, None),
            (False, True, None, 3),
            (True, False, 5, None),
        ],
        ids=["both_none", "output_none", "input_none"],
    )
    def test_none_details_objects_default_to_zero_and_omit_attr(
        self,
        otel_spans: InMemorySpanExporter,
        has_output_details: bool,
        has_input_details: bool,
        expected_reasoning: int | None,
        expected_cache: int | None,
    ) -> None:
        """Streaming partials can have detail objects = None. Extractor
        substitutes 0; ``llm_attributes`` then omits zero-valued attrs.
        """
        out_d = self._details(reasoning_tokens=5) if has_output_details else None
        in_d = self._details(cached_tokens=3) if has_input_details else None
        usage = self._usage(
            input_tokens=10,
            output_tokens=20,
            output_tokens_details=out_d,
            input_tokens_details=in_d,
        )
        attrs = _emit_llm_with(
            otel_spans, usage=usage_from_openai_responses(self._resp(usage))
        )
        assert attrs["gen_ai.usage.input_tokens"] == 10
        assert attrs["gen_ai.usage.output_tokens"] == 20
        if expected_reasoning is None:
            assert "gen_ai.usage.reasoning_tokens" not in attrs
        else:
            assert attrs["gen_ai.usage.reasoning_tokens"] == expected_reasoning
        if expected_cache is None:
            assert "gen_ai.usage.cache_read.input_tokens" not in attrs
        else:
            assert attrs["gen_ai.usage.cache_read.input_tokens"] == expected_cache


class TestMessageFromOpenAIResponsesInput:
    """OpenAI Responses ``input=`` payloads round-trip to ``gen_ai.input.messages``.

    Anchored at the OTel attribute boundary — the high-value contract is
    that a given ``client.responses.create(input=...)`` produces a
    specific JSON shape on the emitted chat span, not that the
    intermediate ``Message`` list has any particular length.
    """

    @staticmethod
    def _input_messages_attr(
        otel_spans: InMemorySpanExporter, items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        msgs, media = message_from_openai_responses_input(items)
        attrs = _emit_llm_with(otel_spans, input_messages=msgs, media_attachments=media)
        return json.loads(attrs["gen_ai.input.messages"])

    def test_text_user_message(self, otel_spans: InMemorySpanExporter) -> None:
        out = self._input_messages_attr(
            otel_spans, [{"role": "user", "content": "hello"}]
        )
        assert out == [
            {"role": "user", "parts": [{"type": "text", "content": "hello"}]}
        ]

    def test_user_message_text_blocks_join_with_newline(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        out = self._input_messages_attr(
            otel_spans,
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "look at"},
                        {"type": "input_text", "text": "this"},
                    ],
                }
            ],
        )
        assert out == [
            {"role": "user", "parts": [{"type": "text", "content": "look at\nthis"}]}
        ]

    @pytest.mark.parametrize(
        "arguments",
        ['{"city": "Tokyo"}', {"city": "Tokyo"}],
        ids=["string", "dict"],
    )
    def test_function_call_emits_assistant_tool_call_part(
        self, otel_spans: InMemorySpanExporter, arguments: object
    ) -> None:
        out = self._input_messages_attr(
            otel_spans,
            [
                {
                    "type": "function_call",
                    "name": "get_weather",
                    "arguments": arguments,
                    "call_id": "c1",
                }
            ],
        )
        assert len(out) == 1
        assert out[0]["role"] == "assistant"
        (part,) = out[0]["parts"]
        assert part["type"] == "tool_call"
        assert part["id"] == "c1"
        assert part["name"] == "get_weather"
        assert json.loads(part["arguments"]) == {"city": "Tokyo"}

    def test_parallel_function_calls_coalesce_to_one_assistant_message(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        out = self._input_messages_attr(
            otel_spans,
            [
                {"role": "user", "content": "weather and time?"},
                {
                    "type": "function_call",
                    "name": "get_weather",
                    "arguments": '{"city":"Tokyo"}',
                    "call_id": "c1",
                },
                {
                    "type": "function_call",
                    "name": "get_time",
                    "arguments": '{"city":"Tokyo"}',
                    "call_id": "c2",
                },
                {
                    "type": "function_call_output",
                    "output": '{"temp":"75F"}',
                    "call_id": "c1",
                },
            ],
        )
        assert [m["role"] for m in out] == ["user", "assistant", "tool"]
        assistant_parts = out[1]["parts"]
        assert [p["type"] for p in assistant_parts] == ["tool_call", "tool_call"]
        assert [p["name"] for p in assistant_parts] == ["get_weather", "get_time"]
        assert [p["id"] for p in assistant_parts] == ["c1", "c2"]

    @pytest.mark.parametrize(
        "output",
        ['{"temp": 75}', {"temp": 75}],
        ids=["string", "dict"],
    )
    def test_function_call_output_emits_tool_message(
        self, otel_spans: InMemorySpanExporter, output: object
    ) -> None:
        out = self._input_messages_attr(
            otel_spans,
            [{"type": "function_call_output", "output": output, "call_id": "c1"}],
        )
        assert len(out) == 1
        assert out[0]["role"] == "tool"
        (part,) = out[0]["parts"]
        assert part["type"] == "tool_call_response"
        assert part["id"] == "c1"
        assert json.loads(part["response"]) == {"temp": 75}

    def test_reasoning_items_skipped(self, otel_spans: InMemorySpanExporter) -> None:
        out = self._input_messages_attr(
            otel_spans,
            [
                {"type": "reasoning", "summary": [{"text": "hmm"}]},
                {"role": "user", "content": "go"},
            ],
        )
        assert [m["role"] for m in out] == ["user"]

    @pytest.mark.parametrize(
        "block",
        [
            {"type": "input_image", "image_url": "data:image/png;base64,iVBORw0KGgo="},
            {"type": "image_url", "image_url": {"url": "https://e.com/cat.png"}},
        ],
        ids=["data_url", "plain_url"],
    )
    def test_image_only_user_message_attaches_media(
        self,
        otel_spans: InMemorySpanExporter,
        block: dict,
    ) -> None:
        """Image-only user messages must keep a Message slot so the
        attachment binds to the right user turn on the wire.
        """
        with patch(
            "weave.conversation.adapters.openai._publish_media_content",
            return_value="weave:///e/p/object/img:v1",
        ):
            out = self._input_messages_attr(
                otel_spans, [{"role": "user", "content": [block]}]
            )
        assert len(out) == 1
        assert out[0]["role"] == "user"
        part = out[0]["parts"][0]
        assert part["type"] == "uri"
        assert part["uri"].startswith("weave:///")

    def test_duplicate_image_urls_deduplicated(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        with patch(
            "weave.conversation.adapters.openai._publish_media_content",
            return_value="weave:///e/p/object/img:v1",
        ):
            out = self._input_messages_attr(
                otel_spans,
                [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_image", "image_url": "https://e.com/a.png"},
                            {"type": "input_image", "image_url": "https://e.com/a.png"},
                        ],
                    }
                ],
            )
        assert out == [
            {
                "role": "user",
                "parts": [
                    {
                        "type": "uri",
                        "mime_type": "",
                        "modality": "image",
                        "uri": "weave:///e/p/object/img:v1",
                    }
                ],
            }
        ]

    def test_assistant_output_text_blocks_flatten(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        out = self._input_messages_attr(
            otel_spans,
            [
                {
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "hello"}],
                }
            ],
        )
        assert out == [
            {"role": "assistant", "parts": [{"type": "text", "content": "hello"}]}
        ]

    def test_full_conversation_round_trip(
        self, otel_spans: InMemorySpanExporter
    ) -> None:
        """User → assistant tool call → tool result → assistant text."""
        out = self._input_messages_attr(
            otel_spans,
            [
                {"role": "user", "content": "what's the weather in Tokyo?"},
                {
                    "type": "function_call",
                    "name": "get_weather",
                    "arguments": '{"city":"Tokyo"}',
                    "call_id": "c1",
                },
                {
                    "type": "function_call_output",
                    "output": '{"temp":"75F"}',
                    "call_id": "c1",
                },
                {
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "It's 75F."}],
                },
            ],
        )
        assert [m["role"] for m in out] == ["user", "assistant", "tool", "assistant"]


class TestReasoningFromOpenAIResponses:
    """reasoning_from_openai_responses flattens OpenAI's reasoning summary."""

    def test_summary_fragments_joined_with_newlines(self) -> None:
        result = reasoning_from_openai_responses(
            {"summary": [{"text": "first"}, {"text": "second"}]}
        )
        assert result is not None
        assert result.content == "first\nsecond"

    @pytest.mark.parametrize(
        "part",
        [
            {"summary": []},
            None,
            {"summary": [{"text": ""}, {}]},
            {"summary": "not a list"},
        ],
        ids=["empty_summary", "none_input", "only_empty_text", "non_list_summary"],
    )
    def test_returns_none(self, part: object) -> None:
        """Empty / malformed inputs collapse to None so callers can pipe through."""
        assert reasoning_from_openai_responses(part) is None  # type: ignore[arg-type]

    def test_skips_non_dict_summary_items(self) -> None:
        result = reasoning_from_openai_responses(
            {"summary": [{"text": "kept"}, "not a dict", {"text": "also kept"}]}
        )
        assert result is not None
        assert result.content == "kept\nalso kept"
