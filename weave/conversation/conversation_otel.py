"""OTel attribute builders for the Weave Conversation SDK.

Each function returns a dict of GenAI semantic convention attributes
for a specific span type. These are pure functions that build attribute
dicts — no OTel SDK dependency required.

Messages are serialized in the GenAI parts model: each message is
``{role, parts: [...]}`` where each part is a TextPart, ReasoningPart,
ToolCallPart, ToolCallResponsePart, BlobPart, UriPart, or FilePart per
the semconv schemas at ``docs/gen-ai/gen-ai-input-messages.json`` and
``-output-messages.json``.

Two construction styles are supported:

- **Explicit parts:** callers populate ``Message.parts`` directly with
  typed part objects. The serializer dumps each part as-is.
- **Flat content (back-compat):** when ``Message.parts`` is empty, the
  serializer synthesizes a single TextPart from ``Message.content`` (or
  a ToolCallResponsePart for ``role:"tool"``).

- Media attachments on an LLM call are appended as parts to the most
  recent ``role:"user"`` input message.
- Reasoning content (``LLM.reasoning``) is emitted as a ``ReasoningPart``
  prepended to the most recent ``role:"assistant"`` output message; if
  no assistant message exists, a synthetic one is created. The
  auto-prepend is suppressed if any output message already carries an
  explicit ReasoningPart.
- ``system_instructions`` serialize to an array of ``TextPart`` entries.

The parts model is "Development" tier in the semconv (as of v1.40.0).
This SDK emits it unconditionally — it has no legacy users on the older
flat format, so the dual-mode opt-in flag isn't needed.
"""

from __future__ import annotations

import json
from typing import Any

from weave.conversation.types import MediaAttachment, Message, Reasoning, Usage


def _media_to_part(media: MediaAttachment) -> dict[str, Any]:
    """Build a UriPart pointing to the published weave:// content ref."""
    return {
        "type": "uri",
        "mime_type": media.mime_type,
        "modality": media.modality,
        "uri": media.ref,
    }


def _message_to_parts(
    msg: Message, *, extra: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Convert a Message to the GenAI parts-model dict shape.

    Two modes:

    - **Explicit parts** (``msg.parts`` non-empty): each part is dumped via
      Pydantic's ``model_dump(exclude_defaults=True)`` so empty optional
      fields don't end up in the wire format. Extras (typically media) are
      appended.
    - **Flat content** (back-compat): ``role:"tool"`` becomes a single
      ToolCallResponsePart; everything else produces a TextPart from
      ``msg.content`` when non-empty. Extras append after.
    """
    if msg.parts:
        parts: list[dict[str, Any]] = [
            p.model_dump(exclude_defaults=True) for p in msg.parts
        ]
        # exclude_defaults strips the discriminator "type" when it equals the
        # class default (every part type pins a Literal default). Restore it.
        for serialized, original in zip(parts, msg.parts, strict=True):
            serialized.setdefault("type", original.type)
        if extra:
            parts.extend(extra)
        return {"role": msg.role, "parts": parts}

    parts = []
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
        # Skip the auto-prepend if any output message already carries a
        # ReasoningPart — the caller is using the explicit parts API.
        already_has_reasoning_part = any(
            any(p.get("type") == "reasoning" for p in msg["parts"]) for msg in out
        )
        if not already_has_reasoning_part:
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
    system_instructions: list[str] | None = None,
    agent_id: str = "",
    agent_description: str = "",
    agent_version: str = "",
) -> dict[str, Any]:
    """Build OTel attributes for an invoke_agent span.

    ``system_instructions`` carries the agent's system prompt so the Agents
    tab can surface it on the agent-start marker. It is serialized to the same
    TextPart array as the chat span (per semconv); a chat span nested under the
    agent may repeat it for the specific LLM call.
    """
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
    if agent_id:
        attrs["gen_ai.agent.id"] = agent_id
    if agent_description:
        attrs["gen_ai.agent.description"] = agent_description
    if agent_version:
        attrs["gen_ai.agent.version"] = agent_version

    serialized_si = _serialize_system_instructions(system_instructions)
    if serialized_si is not None:
        attrs["gen_ai.system_instructions"] = serialized_si

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
    response_model: str = "",
    output_type: str = "",
    request_temperature: float | None = None,
    request_max_tokens: int | None = None,
    request_top_p: float | None = None,
    request_frequency_penalty: float | None = None,
    request_presence_penalty: float | None = None,
    request_seed: int | None = None,
    request_stop_sequences: list[str] | None = None,
    request_choice_count: int | None = None,
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
    if response_model:
        attrs["gen_ai.response.model"] = response_model
    if output_type:
        attrs["gen_ai.output.type"] = output_type
    if finish_reasons:
        attrs["gen_ai.response.finish_reasons"] = finish_reasons
    if request_temperature is not None:
        attrs["gen_ai.request.temperature"] = request_temperature
    if request_max_tokens is not None:
        attrs["gen_ai.request.max_tokens"] = request_max_tokens
    if request_top_p is not None:
        attrs["gen_ai.request.top_p"] = request_top_p
    if request_frequency_penalty is not None:
        attrs["gen_ai.request.frequency_penalty"] = request_frequency_penalty
    if request_presence_penalty is not None:
        attrs["gen_ai.request.presence_penalty"] = request_presence_penalty
    if request_seed is not None:
        attrs["gen_ai.request.seed"] = request_seed
    if request_stop_sequences:
        attrs["gen_ai.request.stop_sequences"] = request_stop_sequences
    if request_choice_count is not None:
        attrs["gen_ai.request.choice.count"] = request_choice_count
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
        if usage.cache_creation_input_tokens:
            attrs["gen_ai.usage.cache_creation.input_tokens"] = (
                usage.cache_creation_input_tokens
            )
        if usage.cache_read_input_tokens:
            attrs["gen_ai.usage.cache_read.input_tokens"] = (
                usage.cache_read_input_tokens
            )

    serialized_in = _serialize_input_messages(input_messages, media=media_attachments)
    if serialized_in is not None:
        attrs["gen_ai.input.messages"] = serialized_in

    serialized_out = _serialize_output_messages(
        output_messages, reasoning=reasoning, finish_reasons=finish_reasons
    )
    if serialized_out is not None:
        attrs["gen_ai.output.messages"] = serialized_out

    if media_attachments:
        # Coerce to plain ``str``: OTel attribute validation does an exact-type
        # check and rejects ``str`` subclasses (e.g. ``_CallableStr`` refs).
        attrs["weave.content_refs"] = [str(m.ref) for m in media_attachments]

    return attrs


def execute_tool_attributes(
    *,
    tool_name: str,
    conversation_id: str = "",
    tool_call_arguments: str = "",
    tool_call_result: str = "",
    tool_call_id: str = "",
    tool_type: str = "",
    tool_description: str = "",
    tool_definitions: str = "",
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
    if tool_type:
        attrs["gen_ai.tool.type"] = tool_type
    if tool_description:
        attrs["gen_ai.tool.description"] = tool_description
    if tool_definitions:
        attrs["gen_ai.tool.definitions"] = tool_definitions

    return attrs
