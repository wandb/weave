"""OTel attribute builders for the Weave Session SDK.

Each function returns a dict of GenAI semantic convention attributes
for a specific span type. These are pure functions that build attribute
dicts — no OTel SDK dependency required.
"""

from __future__ import annotations

import json
from typing import Any

from weave.session.session import Message, Reasoning, Usage


def _serialize_messages(messages: list[Message] | None) -> str | None:
    """Serialize a list of Message objects to JSON, or return None if empty."""
    if not messages:
        return None
    return json.dumps([m.model_dump(exclude_defaults=True) for m in messages])


def invoke_agent_attributes(
    *,
    agent_name: str,
    conversation_id: str = "",
    conversation_name: str = "",
    provider_name: str = "",
    model: str = "",
    input_messages: list[Message] | None = None,
    output_messages: list[Message] | None = None,
) -> dict[str, Any]:
    """Build OTel attributes for an invoke_agent span."""
    attrs: dict[str, Any] = {
        "gen_ai.operation.name": "invoke_agent",
        "gen_ai.agent.name": agent_name,
    }
    if conversation_id:
        attrs["gen_ai.conversation.id"] = conversation_id
    if conversation_name:
        attrs["gen_ai.conversation.name"] = conversation_name
    if provider_name:
        attrs["gen_ai.provider.name"] = provider_name
    if model:
        attrs["gen_ai.request.model"] = model

    serialized_in = _serialize_messages(input_messages)
    if serialized_in is not None:
        attrs["gen_ai.input.messages"] = serialized_in

    serialized_out = _serialize_messages(output_messages)
    if serialized_out is not None:
        attrs["gen_ai.output.messages"] = serialized_out

    return attrs


def llm_attributes(
    *,
    model: str,
    provider_name: str = "",
    conversation_id: str = "",
    input_messages: list[Message] | None = None,
    output_messages: list[Message] | None = None,
    system_instructions: list[str] | None = None,
    usage: Usage | None = None,
    reasoning: Reasoning | None = None,
    finish_reasons: list[str] | None = None,
    response_id: str = "",
) -> dict[str, Any]:
    """Build OTel attributes for an LLM call (chat operation) span."""
    attrs: dict[str, Any] = {
        "gen_ai.operation.name": "chat",
        "gen_ai.request.model": model,
    }
    if conversation_id:
        attrs["gen_ai.conversation.id"] = conversation_id
    if provider_name:
        attrs["gen_ai.provider.name"] = provider_name
    if response_id:
        attrs["gen_ai.response.id"] = response_id
    if finish_reasons:
        attrs["gen_ai.response.finish_reasons"] = finish_reasons
    if system_instructions:
        attrs["gen_ai.system_instructions"] = json.dumps(system_instructions)
    if usage is not None:
        if usage.input_tokens:
            attrs["gen_ai.usage.input_tokens"] = usage.input_tokens
        if usage.output_tokens:
            attrs["gen_ai.usage.output_tokens"] = usage.output_tokens
        if usage.reasoning_tokens:
            attrs["gen_ai.usage.reasoning_tokens"] = usage.reasoning_tokens

    serialized_in = _serialize_messages(input_messages)
    if serialized_in is not None:
        attrs["gen_ai.input.messages"] = serialized_in

    serialized_out = _serialize_messages(output_messages)
    if serialized_out is not None:
        attrs["gen_ai.output.messages"] = serialized_out

    return attrs


def execute_tool_attributes(
    *,
    tool_name: str,
    conversation_id: str = "",
    tool_call_arguments: str = "",
    tool_call_result: str = "",
    tool_call_id: str = "",
) -> dict[str, Any]:
    """Build OTel attributes for an execute_tool span."""
    attrs: dict[str, Any] = {
        "gen_ai.operation.name": "execute_tool",
        "gen_ai.tool.name": tool_name,
    }
    if conversation_id:
        attrs["gen_ai.conversation.id"] = conversation_id
    if tool_call_id:
        attrs["gen_ai.tool.call.id"] = tool_call_id
    if tool_call_arguments:
        attrs["gen_ai.tool.call.arguments"] = tool_call_arguments
    if tool_call_result:
        attrs["gen_ai.tool.call.result"] = tool_call_result

    return attrs
