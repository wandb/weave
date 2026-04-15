"""Tests for weave.trace.session_otel attribute builders.

Verifies that the OTel attribute dicts produced by the builder functions
contain the exact keys that ``genai_extraction.py`` looks for on the server.
"""

from __future__ import annotations

import json

from weave.trace.session import Message, Reasoning, Usage
from weave.trace.session_otel import (
    _encode_messages,
    chat_attributes,
    execute_tool_attributes,
    invoke_agent_attributes,
)

# ---------------------------------------------------------------------------
# Message encoding
# ---------------------------------------------------------------------------


class TestEncodeMessages:
    def test_basic_message(self) -> None:
        msgs = [Message(role="user", content="Hello")]
        result = json.loads(_encode_messages(msgs))
        assert result == [{"role": "user", "content": "Hello"}]

    def test_empty_optional_fields_omitted(self) -> None:
        """Empty content / tool fields should NOT appear in the encoded dict."""
        msgs = [Message(role="user")]
        result = json.loads(_encode_messages(msgs))
        assert result == [{"role": "user"}]
        assert "content" not in result[0]
        assert "tool_call_id" not in result[0]
        assert "tool_name" not in result[0]

    def test_tool_message_includes_tool_fields(self) -> None:
        msgs = [
            Message(
                role="tool",
                content="42",
                tool_call_id="call_abc",
                tool_name="calculator",
            )
        ]
        result = json.loads(_encode_messages(msgs))
        assert result == [
            {
                "role": "tool",
                "content": "42",
                "tool_call_id": "call_abc",
                "tool_name": "calculator",
            }
        ]

    def test_multiple_messages(self) -> None:
        msgs = [
            Message(role="user", content="Hi"),
            Message(role="assistant", content="Hello!"),
        ]
        result = json.loads(_encode_messages(msgs))
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"

    def test_empty_list(self) -> None:
        result = json.loads(_encode_messages([]))
        assert result == []


# ---------------------------------------------------------------------------
# invoke_agent_attributes
# ---------------------------------------------------------------------------


class TestInvokeAgentAttributes:
    def test_required_keys(self) -> None:
        attrs = invoke_agent_attributes(agent_name="TestBot")
        assert attrs["gen_ai.operation.name"] == "invoke_agent"
        assert attrs["gen_ai.agent.name"] == "TestBot"

    def test_optional_fields_omitted_when_empty(self) -> None:
        attrs = invoke_agent_attributes(agent_name="Bot")
        assert "gen_ai.system" not in attrs
        assert "gen_ai.conversation.id" not in attrs
        assert "gen_ai.conversation.name" not in attrs
        assert "gen_ai.input.messages" not in attrs
        assert "gen_ai.output.messages" not in attrs

    def test_all_fields(self) -> None:
        attrs = invoke_agent_attributes(
            agent_name="Bot",
            conversation_id="conv-123",
            conversation_name="My Chat",
            provider_name="openai",
            input_messages=[Message(role="user", content="Hi")],
            output_messages=[Message(role="assistant", content="Hey")],
        )
        assert attrs["gen_ai.system"] == "openai"
        assert attrs["gen_ai.conversation.id"] == "conv-123"
        assert attrs["gen_ai.conversation.name"] == "My Chat"
        # Messages are JSON strings
        assert isinstance(attrs["gen_ai.input.messages"], str)
        parsed_in = json.loads(attrs["gen_ai.input.messages"])
        assert parsed_in[0]["role"] == "user"
        parsed_out = json.loads(attrs["gen_ai.output.messages"])
        assert parsed_out[0]["role"] == "assistant"


# ---------------------------------------------------------------------------
# chat_attributes
# ---------------------------------------------------------------------------


class TestChatAttributes:
    def test_required_keys(self) -> None:
        attrs = chat_attributes(model="gpt-4o")
        assert attrs["gen_ai.operation.name"] == "chat"
        assert attrs["gen_ai.request.model"] == "gpt-4o"

    def test_optional_fields_omitted_when_empty(self) -> None:
        attrs = chat_attributes(model="gpt-4o")
        assert "gen_ai.system" not in attrs
        assert "gen_ai.response.model" not in attrs
        assert "gen_ai.input.messages" not in attrs
        assert "gen_ai.output.messages" not in attrs
        assert "gen_ai.system_instructions" not in attrs
        assert "gen_ai.usage.input_tokens" not in attrs
        assert "gen_ai.usage.output_tokens" not in attrs
        assert "gen_ai.usage.reasoning_tokens" not in attrs
        assert "gen_ai.response.finish_reasons" not in attrs

    def test_with_usage(self) -> None:
        usage = Usage(input_tokens=100, output_tokens=50, reasoning_tokens=10)
        attrs = chat_attributes(model="gpt-4o", usage=usage)
        assert attrs["gen_ai.usage.input_tokens"] == 100
        assert attrs["gen_ai.usage.output_tokens"] == 50
        assert attrs["gen_ai.usage.reasoning_tokens"] == 10

    def test_zero_usage_omitted(self) -> None:
        """Zero token counts should not be set (cleaner attributes)."""
        usage = Usage(input_tokens=0, output_tokens=0, reasoning_tokens=0)
        attrs = chat_attributes(model="gpt-4o", usage=usage)
        assert "gen_ai.usage.input_tokens" not in attrs
        assert "gen_ai.usage.output_tokens" not in attrs
        assert "gen_ai.usage.reasoning_tokens" not in attrs

    def test_system_instructions_encoded_as_json_array(self) -> None:
        attrs = chat_attributes(
            model="gpt-4o",
            system_instructions=["You are a helpful assistant.", "Be concise."],
        )
        raw = attrs["gen_ai.system_instructions"]
        assert isinstance(raw, str)
        parsed = json.loads(raw)
        assert parsed == ["You are a helpful assistant.", "Be concise."]

    def test_finish_reasons_as_tuple(self) -> None:
        attrs = chat_attributes(model="gpt-4o", finish_reasons=["stop"])
        assert attrs["gen_ai.response.finish_reasons"] == ["stop"]

    def test_finish_reasons_multiple(self) -> None:
        attrs = chat_attributes(model="gpt-4o", finish_reasons=["stop", "length"])
        assert attrs["gen_ai.response.finish_reasons"] == ["stop", "length"]

    def test_messages(self) -> None:
        attrs = chat_attributes(
            model="gpt-4o",
            input_messages=[Message(role="user", content="Hello")],
            output_messages=[Message(role="assistant", content="Hi!")],
        )
        in_msgs = json.loads(attrs["gen_ai.input.messages"])
        out_msgs = json.loads(attrs["gen_ai.output.messages"])
        assert in_msgs[0]["content"] == "Hello"
        assert out_msgs[0]["content"] == "Hi!"

    def test_response_model(self) -> None:
        attrs = chat_attributes(model="gpt-4o", response_model="gpt-4o-2024-05-13")
        assert attrs["gen_ai.response.model"] == "gpt-4o-2024-05-13"

    def test_provider(self) -> None:
        attrs = chat_attributes(model="gpt-4o", provider_name="openai")
        assert attrs["gen_ai.system"] == "openai"

    def test_reasoning_content_prepended_to_output_messages(self) -> None:
        reasoning = Reasoning(content="Let me think step by step...")
        attrs = chat_attributes(
            model="o3",
            output_messages=[Message(role="assistant", content="The answer is 42.")],
            reasoning=reasoning,
        )
        out_msgs = json.loads(attrs["gen_ai.output.messages"])
        assert len(out_msgs) == 2
        # First entry is the reasoning part
        assert out_msgs[0]["role"] == "assistant"
        assert out_msgs[0]["parts"] == [
            {"type": "reasoning", "content": "Let me think step by step..."}
        ]
        # Second entry is the normal output message
        assert out_msgs[1] == {"role": "assistant", "content": "The answer is 42."}

    def test_reasoning_without_output_messages(self) -> None:
        reasoning = Reasoning(content="Thinking...")
        attrs = chat_attributes(model="o3", reasoning=reasoning)
        out_msgs = json.loads(attrs["gen_ai.output.messages"])
        assert len(out_msgs) == 1
        assert out_msgs[0]["parts"][0]["type"] == "reasoning"

    def test_empty_reasoning_content_omitted(self) -> None:
        reasoning = Reasoning(content="")
        attrs = chat_attributes(model="o3", reasoning=reasoning)
        assert "gen_ai.output.messages" not in attrs

    def test_none_reasoning_content_omitted(self) -> None:
        reasoning = Reasoning()
        attrs = chat_attributes(model="o3", reasoning=reasoning)
        assert "gen_ai.output.messages" not in attrs


# ---------------------------------------------------------------------------
# execute_tool_attributes
# ---------------------------------------------------------------------------


class TestExecuteToolAttributes:
    def test_required_keys(self) -> None:
        attrs = execute_tool_attributes(tool_name="calculator")
        assert attrs["gen_ai.operation.name"] == "execute_tool"
        assert attrs["gen_ai.tool.name"] == "calculator"

    def test_optional_fields_omitted_when_empty(self) -> None:
        attrs = execute_tool_attributes(tool_name="calc")
        assert "gen_ai.tool.call.id" not in attrs
        assert "gen_ai.tool.call.arguments" not in attrs
        assert "gen_ai.tool.call.result" not in attrs

    def test_all_fields(self) -> None:
        attrs = execute_tool_attributes(
            tool_name="search",
            tool_call_id="call_xyz",
            tool_call_arguments='{"query": "weather"}',
            tool_call_result='{"temp": 72}',
        )
        assert attrs["gen_ai.tool.name"] == "search"
        assert attrs["gen_ai.tool.call.id"] == "call_xyz"
        assert attrs["gen_ai.tool.call.arguments"] == '{"query": "weather"}'
        assert attrs["gen_ai.tool.call.result"] == '{"temp": 72}'


# ---------------------------------------------------------------------------
# Round-trip: attributes -> extractor
# ---------------------------------------------------------------------------


class TestRoundTripWithExtractor:
    """Verify our attributes can be parsed back by the server extractor functions."""

    def test_invoke_agent_round_trip(self) -> None:
        from weave.trace_server.opentelemetry.genai_extraction import (
            extract_agent_name,
            extract_conversation_id,
            extract_conversation_name,
            extract_operation_name,
        )

        attrs = invoke_agent_attributes(
            agent_name="WeatherBot",
            conversation_id="sess-1",
            conversation_name="Weather Chat",
        )
        assert extract_operation_name(attrs, "test") == "invoke_agent"
        assert extract_agent_name(attrs, "test") == "WeatherBot"
        assert extract_conversation_id(attrs) == "sess-1"
        assert extract_conversation_name(attrs) == "Weather Chat"

    def test_chat_round_trip(self) -> None:
        from weave.trace_server.opentelemetry.genai_extraction import (
            extract_finish_reasons,
            extract_input_tokens,
            extract_operation_name,
            extract_output_tokens,
            extract_provider,
            extract_reasoning_tokens,
        )

        usage = Usage(input_tokens=100, output_tokens=50, reasoning_tokens=10)
        attrs = chat_attributes(
            model="gpt-4o",
            provider_name="openai",
            usage=usage,
            finish_reasons=["stop"],
        )
        assert extract_operation_name(attrs, "test") == "chat"
        assert extract_provider(attrs, "test") == "openai"
        assert extract_input_tokens(attrs) == 100
        assert extract_output_tokens(attrs) == 50
        assert extract_reasoning_tokens(attrs) == 10
        assert extract_finish_reasons(attrs) == ["stop"]
        assert attrs["gen_ai.request.model"] == "gpt-4o"

    def test_chat_messages_round_trip(self) -> None:
        from weave.trace_server.opentelemetry.genai_extraction import (
            extract_input_messages,
            extract_output_messages,
        )

        attrs = chat_attributes(
            model="gpt-4o",
            input_messages=[
                Message(role="user", content="What's the weather?"),
            ],
            output_messages=[
                Message(role="assistant", content="It's sunny!"),
            ],
        )
        in_msgs = extract_input_messages(attrs, [])
        assert len(in_msgs) == 1
        assert in_msgs[0].role == "user"
        assert in_msgs[0].content == "What's the weather?"

        out_msgs = extract_output_messages(attrs, [])
        assert len(out_msgs) == 1
        assert out_msgs[0].role == "assistant"
        assert out_msgs[0].content == "It's sunny!"

    def test_chat_system_instructions_round_trip(self) -> None:
        from weave.trace_server.opentelemetry.genai_extraction import (
            _normalize_system_instructions,
        )
        from weave.trace_server.opentelemetry.helpers import get_attribute

        attrs = chat_attributes(
            model="gpt-4o",
            system_instructions=["Be helpful", "Be concise"],
        )
        raw = get_attribute(attrs, "gen_ai.system_instructions")
        result = _normalize_system_instructions(raw)
        assert result == ["Be helpful", "Be concise"]

    def test_chat_reasoning_content_round_trip(self) -> None:
        from weave.trace_server.opentelemetry.genai_extraction import (
            extract_reasoning_content,
        )

        reasoning = Reasoning(content="Step 1: analyze. Step 2: conclude.")
        attrs = chat_attributes(
            model="o3",
            output_messages=[Message(role="assistant", content="Done.")],
            reasoning=reasoning,
        )
        raw_output = attrs["gen_ai.output.messages"]
        result = extract_reasoning_content(raw_output)
        assert result == "Step 1: analyze. Step 2: conclude."

    def test_execute_tool_round_trip(self) -> None:
        from weave.trace_server.opentelemetry.genai_extraction import (
            extract_operation_name,
            extract_tool_call_arguments,
            extract_tool_call_result,
        )

        attrs = execute_tool_attributes(
            tool_name="calculator",
            tool_call_id="call_1",
            tool_call_arguments='{"expr": "2+2"}',
            tool_call_result="4",
        )
        assert extract_operation_name(attrs, "test") == "execute_tool"
        assert attrs["gen_ai.tool.name"] == "calculator"
        assert attrs["gen_ai.tool.call.id"] == "call_1"
        assert extract_tool_call_arguments(attrs, []) == '{"expr": "2+2"}'
        assert extract_tool_call_result(attrs, []) == "4"
