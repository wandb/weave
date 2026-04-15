"""Build OTel GenAI semantic convention attributes for Session SDK spans.

Maps Session/Turn/Step/Tool data to OTel attribute dicts whose keys match
what ``weave.trace_server.opentelemetry.genai_extraction`` expects on the
server side.
"""

from __future__ import annotations

import json
from typing import Any

from weave.trace.session import Message, Reasoning, Usage


def _encode_messages(messages: list[Message]) -> str:
    """Encode a list of Message objects as a JSON string.

    Each message is serialized as a dict with role, content, and optional
    tool_call_id / tool_name fields (omitted when empty).
    The extractor's ``_normalize_raw_messages`` handles JSON-string input
    by parsing it first, then normalizing each ``{role, content, ...}`` dict.
    """
    encoded: list[dict[str, str]] = []
    for msg in messages:
        d: dict[str, str] = {"role": msg.role}
        if msg.content:
            d["content"] = msg.content
        if msg.tool_call_id:
            d["tool_call_id"] = msg.tool_call_id
        if msg.tool_name:
            d["tool_name"] = msg.tool_name
        encoded.append(d)
    return json.dumps(encoded)


def invoke_agent_attributes(
    *,
    agent_name: str,
    conversation_id: str = "",
    conversation_name: str = "",
    provider_name: str = "",
    input_messages: list[Message] | None = None,
    output_messages: list[Message] | None = None,
) -> dict[str, Any]:
    """Build OTel attributes for an invoke_agent (root turn) span.

    Attribute keys align with ``genai_extraction.extract_genai_fields``.
    """
    attrs: dict[str, Any] = {
        "gen_ai.operation.name": "invoke_agent",
        "gen_ai.agent.name": agent_name,
    }
    if provider_name:
        attrs["gen_ai.system"] = provider_name
    if conversation_id:
        attrs["gen_ai.conversation.id"] = conversation_id
    if conversation_name:
        attrs["gen_ai.conversation.name"] = conversation_name
    if input_messages:
        attrs["gen_ai.input.messages"] = _encode_messages(input_messages)
    if output_messages:
        attrs["gen_ai.output.messages"] = _encode_messages(output_messages)
    return attrs


def chat_attributes(
    *,
    model: str,
    provider_name: str = "",
    input_messages: list[Message] | None = None,
    output_messages: list[Message] | None = None,
    system_instructions: list[str] | None = None,
    usage: Usage | None = None,
    reasoning: Reasoning | None = None,
    finish_reasons: list[str] | None = None,
    response_model: str = "",
) -> dict[str, Any]:
    """Build OTel attributes for a chat (LLM call) span.

    Attribute keys align with ``genai_extraction.extract_genai_fields``.
    """
    attrs: dict[str, Any] = {
        "gen_ai.operation.name": "chat",
        "gen_ai.request.model": model,
    }
    if provider_name:
        attrs["gen_ai.system"] = provider_name
    if response_model:
        attrs["gen_ai.response.model"] = response_model
    if input_messages:
        attrs["gen_ai.input.messages"] = _encode_messages(input_messages)
    # Build the output messages list, prepending a reasoning entry if needed.
    output_encoded: list[dict[str, Any]] = []
    if reasoning and reasoning.content:
        output_encoded.append(
            {
                "role": "assistant",
                "parts": [{"type": "reasoning", "content": reasoning.content}],
            }
        )
    if output_messages:
        output_encoded.extend(json.loads(_encode_messages(output_messages)))
    if output_encoded:
        attrs["gen_ai.output.messages"] = json.dumps(output_encoded)
    if system_instructions:
        attrs["gen_ai.system_instructions"] = json.dumps(system_instructions)
    if usage:
        if usage.input_tokens:
            attrs["gen_ai.usage.input_tokens"] = usage.input_tokens
        if usage.output_tokens:
            attrs["gen_ai.usage.output_tokens"] = usage.output_tokens
        if usage.reasoning_tokens:
            attrs["gen_ai.usage.reasoning_tokens"] = usage.reasoning_tokens
    if finish_reasons:
        attrs["gen_ai.response.finish_reasons"] = list(finish_reasons)
    return attrs


def execute_tool_attributes(
    *,
    tool_name: str,
    tool_call_arguments: str = "",
    tool_call_result: str = "",
    tool_call_id: str = "",
) -> dict[str, Any]:
    """Build OTel attributes for an execute_tool span.

    Attribute keys align with ``genai_extraction.extract_genai_fields``.
    """
    attrs: dict[str, Any] = {
        "gen_ai.operation.name": "execute_tool",
        "gen_ai.tool.name": tool_name,
    }
    if tool_call_id:
        attrs["gen_ai.tool.call.id"] = tool_call_id
    if tool_call_arguments:
        attrs["gen_ai.tool.call.arguments"] = tool_call_arguments
    if tool_call_result:
        attrs["gen_ai.tool.call.result"] = tool_call_result
    return attrs
