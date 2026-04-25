"""Tests for OTel GenAI attribute builders in session_otel.py."""

from __future__ import annotations

import json

from weave.session.session import Message, Reasoning, Usage
from weave.session.session_otel import (
    execute_tool_attributes,
    invoke_agent_attributes,
    llm_attributes,
)

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
        attrs = llm_attributes(
            model="gpt-4o", input_messages=[], output_messages=[]
        )
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
        attrs = llm_attributes(
            model="gpt-4o", finish_reasons=["stop", "length"]
        )
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
            tool_call_id="tc_1",
            tool_call_arguments='{"city": "Tokyo"}',
            tool_call_result='{"temp": "75F"}',
        )
        assert attrs["gen_ai.operation.name"] == "execute_tool"
        assert attrs["gen_ai.tool.name"] == "get_weather"
        assert attrs["gen_ai.tool.call.id"] == "tc_1"
        assert attrs["gen_ai.tool.call.arguments"] == '{"city": "Tokyo"}'
        assert attrs["gen_ai.tool.call.result"] == '{"temp": "75F"}'

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

    def test_no_otel_sdk_import_required(self) -> None:
        """The module should not import opentelemetry at all."""
        import weave.session.session_otel as mod

        source = open(mod.__file__, encoding="utf-8").read()
        assert "import opentelemetry" not in source
        assert "from opentelemetry" not in source
