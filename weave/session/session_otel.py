"""OTel attribute builders for the Weave Session SDK.

Each function returns a dict of GenAI semantic convention attributes
for a specific span type. These are pure functions that build attribute
dicts — no OTel SDK dependency required.

Messages are serialized in the GenAI parts model: each message is
``{role, parts: [...]}`` where each part is a TextPart, BlobPart, UriPart,
FilePart, ReasoningPart, or ToolCallResponsePart per the semconv schemas
at ``docs/gen-ai/gen-ai-input-messages.json`` and ``-output-messages.json``.

- Media attachments on an LLM call are appended as parts to the most
  recent ``role:"user"`` input message.
- Reasoning content is emitted as a ``ReasoningPart`` prepended to the
  most recent ``role:"assistant"`` output message; if there is no
  assistant message, a synthetic one is created to carry it.
- ``role:"tool"`` messages serialize to a single ``ToolCallResponsePart``.
- ``system_instructions`` serialize to an array of ``TextPart`` entries.

The parts model is "Development" tier in the semconv (as of v1.40.0).
This SDK emits it unconditionally — it has no legacy users on the older
flat format, so the dual-mode opt-in flag isn't needed.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from weave.session.types import MediaAttachment, Message, Reasoning, Usage


def _media_to_part(media: MediaAttachment) -> dict[str, Any]:
    """Build a BlobPart, UriPart, or FilePart per GenAI semconv.

    Bytes content is base64-encoded; str content is assumed to already be
    base64-encoded by the caller (matches the semconv field which is a
    string of base64 data).
    """
    if media.kind == "blob":
        encoded = (
            base64.b64encode(media.content).decode("ascii")
            if isinstance(media.content, bytes)
            else media.content
        )
        return {
            "type": "blob",
            "mime_type": media.mime_type,
            "modality": media.modality,
            "content": encoded,
        }
    if media.kind == "uri":
        return {
            "type": "uri",
            "mime_type": media.mime_type,
            "modality": media.modality,
            "uri": media.uri,
        }
    return {
        "type": "file",
        "mime_type": media.mime_type,
        "modality": media.modality,
        "file_id": media.file_id,
    }


def _message_to_parts(
    msg: Message, *, extra: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Convert a Message to the GenAI parts-model dict shape.

    role:"tool" messages become a single ToolCallResponsePart.
    All other roles produce a TextPart when they have content.
    Extra parts (typically media) are appended after the text part.
    """
    parts: list[dict[str, Any]] = []
    if msg.role == "tool":
        part: dict[str, Any] = {"type": "tool_call_response", "response": msg.content}
        if msg.tool_call_id:
            part["id"] = msg.tool_call_id
        parts.append(part)
    elif msg.content:
        parts.append({"type": "text", "content": msg.content})
    if extra:
        parts.extend(extra)
    return {"role": msg.role, "parts": parts}


def _serialize_input_messages(
    messages: list[Message] | None,
    *,
    media: list[MediaAttachment] | None = None,
) -> str | None:
    """Serialize input messages, attaching media to the last user message."""
    if not messages:
        return None
    media_parts = [_media_to_part(m) for m in (media or [])]
    last_user = -1
    for i, m in enumerate(messages):
        if m.role == "user":
            last_user = i
    out = [
        _message_to_parts(
            m,
            extra=media_parts if (i == last_user and media_parts) else None,
        )
        for i, m in enumerate(messages)
    ]
    return json.dumps(out)


def _serialize_output_messages(
    messages: list[Message] | None,
    *,
    reasoning: Reasoning | None = None,
    finish_reasons: list[str] | None = None,
) -> str | None:
    """Serialize output messages.

    Reasoning, when present, is prepended as a ReasoningPart to the most
    recent assistant message; a synthetic assistant message is created if
    no output messages exist. ``finish_reasons[0]`` is attached to the
    last output message per semconv (one finish_reason per message).
    """
    has_reasoning = reasoning is not None and bool(reasoning.content)
    if not messages and not has_reasoning:
        return None
    out: list[dict[str, Any]] = [_message_to_parts(m) for m in (messages or [])]
    if has_reasoning:
        assert reasoning is not None  # narrow for mypy
        rpart = {"type": "reasoning", "content": reasoning.content}
        if out:
            last_asst = -1
            for i, m in enumerate(messages or []):
                if m.role == "assistant":
                    last_asst = i
            target = out[last_asst] if last_asst >= 0 else out[-1]
            target["parts"].insert(0, rpart)
        else:
            out.append({"role": "assistant", "parts": [rpart]})
    if out and finish_reasons:
        out[-1]["finish_reason"] = finish_reasons[0]
    return json.dumps(out)


def _serialize_system_instructions(
    instructions: list[str] | None,
) -> str | None:
    """Serialize system instructions as a JSON array of TextParts per semconv."""
    if not instructions:
        return None
    return json.dumps([{"type": "text", "content": s} for s in instructions])


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

    serialized_in = _serialize_input_messages(input_messages)
    if serialized_in is not None:
        attrs["gen_ai.input.messages"] = serialized_in

    serialized_out = _serialize_output_messages(output_messages)
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
    media_attachments: list[MediaAttachment] | None = None,
    system_instructions: list[str] | None = None,
    usage: Usage | None = None,
    reasoning: Reasoning | None = None,
    finish_reasons: list[str] | None = None,
    response_id: str = "",
) -> dict[str, Any]:
    """Build OTel attributes for an LLM call (chat operation) span.

    Reasoning is folded into ``gen_ai.output.messages`` as a ReasoningPart
    on the last assistant message. Media is folded into
    ``gen_ai.input.messages`` as Blob/Uri/FilePart entries on the last
    user message.
    """
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
    serialized_si = _serialize_system_instructions(system_instructions)
    if serialized_si is not None:
        attrs["gen_ai.system_instructions"] = serialized_si
    if usage is not None:
        if usage.input_tokens:
            attrs["gen_ai.usage.input_tokens"] = usage.input_tokens
        if usage.output_tokens:
            attrs["gen_ai.usage.output_tokens"] = usage.output_tokens
        if usage.reasoning_tokens:
            attrs["gen_ai.usage.reasoning_tokens"] = usage.reasoning_tokens

    serialized_in = _serialize_input_messages(input_messages, media=media_attachments)
    if serialized_in is not None:
        attrs["gen_ai.input.messages"] = serialized_in

    serialized_out = _serialize_output_messages(
        output_messages, reasoning=reasoning, finish_reasons=finish_reasons
    )
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
