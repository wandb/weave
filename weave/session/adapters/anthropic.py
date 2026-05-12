"""Adapters from Anthropic's wire format to the Weave Session SDK types.

Used internally by the autopatched Anthropic integration to populate
``LLM`` spans from request / response data; also exposed publicly for
agents that prefer to instrument manually.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from weave.session.types import Message, ToolCallPart, ToolCallResponsePart, Usage

if TYPE_CHECKING:
    from anthropic.types import Message as AnthropicMessage

__all__ = [
    "finish_reasons_from_anthropic",
    "input_messages_from_anthropic",
    "output_messages_from_anthropic",
    "usage_from_anthropic",
]


def usage_from_anthropic(message: AnthropicMessage) -> Usage:
    """Extract usage from an Anthropic Messages API ``Message``.

    Anthropic types the cache fields as ``Optional[int]``; ``None`` is
    equivalent to zero for our purposes.
    """
    usage = message.usage
    return Usage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_creation_input_tokens=usage.cache_creation_input_tokens or 0,
        cache_read_input_tokens=usage.cache_read_input_tokens or 0,
    )


def input_messages_from_anthropic(
    messages: list[dict[str, Any]],
) -> list[Message]:
    """Convert the ``messages=`` list passed to ``client.messages.create``.

    Anthropic's request shape is ``[{"role": "user"|"assistant", "content":
    <str|blocks>}, ...]``. String content is taken as-is; structured
    content blocks are walked for ``text`` (text payloads),
    ``tool_use`` (assistant tool-call invocations), and ``tool_result``
    (user-message-encoded tool responses). Returned messages preserve
    role and contain either flat text or structured ``parts``.
    """
    out: list[Message] = []
    for item in messages:
        role = item.get("role")
        content = item.get("content")
        if isinstance(content, str):
            out.append(Message(role=str(role or "user"), content=content))
            continue
        if not isinstance(content, list):
            continue
        text_parts: list[str] = []
        tool_calls: list[ToolCallPart] = []
        tool_responses: list[ToolCallResponsePart] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                text = block.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
            elif block_type == "tool_use":
                tool_calls.append(
                    ToolCallPart(
                        id=str(block.get("id", "")),
                        name=str(block.get("name", "")),
                        arguments=block.get("input", "") or "",
                    )
                )
            elif block_type == "tool_result":
                tool_responses.append(
                    ToolCallResponsePart(
                        id=str(block.get("tool_use_id", "")),
                        response=block.get("content", "") or "",
                    )
                )
        text = "\n".join(text_parts)
        if role == "assistant" and (text or tool_calls):
            out.append(Message.assistant(text, tool_calls=tool_calls or None))
        elif tool_responses:
            out.append(Message(role="tool", parts=list(tool_responses)))
        elif role:
            out.append(Message(role=str(role), content=text))
    return out


def output_messages_from_anthropic(
    message: AnthropicMessage,
) -> list[Message]:
    """Assemble the assistant ``Message`` from an Anthropic Messages
    ``Message`` response.

    Walks ``message.content`` for ``TextBlock`` and ``ToolUseBlock``
    entries, coalescing both into one ``Message.assistant(text,
    tool_calls=...)``. Returns ``[]`` when no text and no tool calls
    (e.g. an empty response) so callers can pipe through to
    ``LLM.record(output_messages=...)`` unconditionally.
    """
    text_parts: list[str] = []
    tool_calls: list[ToolCallPart] = []
    for block in message.content or []:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            text = getattr(block, "text", "")
            if text:
                text_parts.append(text)
        elif block_type == "tool_use":
            tool_calls.append(
                ToolCallPart(
                    id=getattr(block, "id", "") or "",
                    name=getattr(block, "name", "") or "",
                    arguments=getattr(block, "input", "") or "",
                )
            )
    text = "\n".join(text_parts)
    if not text and not tool_calls:
        return []
    return [Message.assistant(text, tool_calls=tool_calls or None)]


_STOP_REASON_TO_FINISH = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
    "pause_turn": "pause_turn",
    "refusal": "content_filter",
}


def finish_reasons_from_anthropic(message: AnthropicMessage) -> list[str]:
    """Map Anthropic's ``stop_reason`` to OTel ``gen_ai.response.finish_reasons``.

    Anthropic reports a single stop reason (``end_turn``,
    ``max_tokens``, ``tool_use``, etc.); OTel uses a small fixed
    vocabulary. Unknown reasons pass through unchanged so we don't
    drop signal during SDK upgrades that introduce new values.
    """
    stop = message.stop_reason
    if not stop:
        return []
    return [_STOP_REASON_TO_FINISH.get(stop, stop)]
