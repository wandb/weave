"""Adapters from Anthropic's wire format to the Weave Session SDK types.

Use these when manually instrumenting calls to ``client.messages.create``
(the autopatched Anthropic integration handles conversion automatically).

Public functions:

- ``traced_anthropic_messages_stream(client, ...)`` — async context
  manager that wraps a streaming ``client.messages.stream(...)`` call
  with a weave chat span. Opens the stream + ``start_llm`` together,
  yields the stream to the caller, and on close calls
  ``stream.get_final_message()`` + ``record_anthropic_message``.
- ``record_anthropic_message(llm, input_messages, system, response)`` —
  lower-level helper that populates an existing ``LLM`` span from a
  final ``Message``. Use when managing the span yourself.
- ``message_from_anthropic_input(messages)`` — convert an Anthropic
  ``messages=`` payload into a ``list[Message]`` ready to assign to
  ``LLM.input_messages``.
- ``usage_from_anthropic(message)`` — pull token counts off an
  Anthropic ``Message``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from weave.session.types import (
    Message,
    MessagePart,
    TextPart,
    ToolCallPart,
    ToolCallResponsePart,
    Usage,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from anthropic import AsyncAnthropic
    from anthropic.types import Message as AnthropicMessage

    from weave.session.session import LLM

__all__ = [
    "message_from_anthropic_input",
    "record_anthropic_message",
    "traced_anthropic_messages_stream",
    "usage_from_anthropic",
]


# Map Anthropic ``stop_reason`` values to the GenAI semconv finish_reasons
# vocabulary so cross-provider dashboards compare like-for-like.
_STOP_REASON_TO_FINISH = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
}


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


def message_from_anthropic_input(messages: list[dict[str, Any]]) -> list[Message]:
    """Convert an Anthropic ``messages=`` payload into weave ``Message``s.

    Handles the shapes that appear in the ``messages`` parameter to
    ``client.messages.create``:

    - ``{"role": "user"|"assistant", "content": "<str>"}`` becomes a flat
      ``Message``.
    - ``{"role": "assistant", "content": [<TextBlock|ToolUseBlock>...]}``
      becomes an assistant ``Message`` with ``TextPart``s and
      ``ToolCallPart``s combined in order.
    - ``{"role": "user", "content": [<ToolResultBlock|TextBlock>...]}``
      becomes a tool-result ``Message`` (when any ``tool_result`` block is
      present) carrying ``ToolCallResponsePart``s; or a flat-text user
      ``Message`` otherwise. Anthropic packages tool results inside a
      ``role="user"`` message; we split those into ``role="tool"`` so the
      weave Agents view renders them in the tool lane.
    """
    out: list[Message] = []
    for item in messages:
        role = item.get("role")
        content = item.get("content")
        if role == "user":
            out.extend(_user_messages_from_content(content))
        elif role == "assistant":
            out.append(_assistant_message_from_content(content))
    return out


def record_anthropic_message(
    llm: LLM,
    *,
    input_messages: list[dict[str, Any]],
    system: str = "",
    response: AnthropicMessage,
) -> None:
    """Populate an ``LLM`` span from a final Anthropic Messages ``Message``.

    Symmetric to ``record_openai_responses`` in the OpenAI adapter. The
    adapter owns the unpack from provider wire format to all ``gen_ai.*``
    attributes — call sites pass the inputs that went into the request
    plus the final response, and the LLM span gets every field set.
    """
    output_messages = _output_from_anthropic_message(response)
    finish_reason = _STOP_REASON_TO_FINISH.get(
        response.stop_reason or "", response.stop_reason or ""
    )
    # ``system_instructions`` is a direct field on ``LLM`` (Anthropic passes
    # the system prompt out-of-band; OpenAI inlines it as a system message,
    # so ``LLM.record`` does not expose it as a kwarg). Set it directly here.
    if system:
        llm.system_instructions = [system]
    llm.record(
        input_messages=message_from_anthropic_input(input_messages),
        output_messages=output_messages,
        usage=usage_from_anthropic(response),
        response_id=response.id,
        response_model=response.model,
        finish_reasons=[finish_reason] if finish_reason else [],
    )


@asynccontextmanager
async def traced_anthropic_messages_stream(
    *,
    client: AsyncAnthropic,
    messages: list[dict[str, Any]],
    model: str,
    system: str = "",
    **stream_kwargs: Any,
) -> AsyncIterator[Any]:
    """Wrap ``client.messages.stream(...)`` with a weave chat span.

    Opens ``start_llm`` and ``client.messages.stream(...)`` together,
    yields the stream context to the caller, and on close calls
    ``stream.get_final_message()`` + ``record_anthropic_message`` so the
    chat span gets every ``gen_ai.*`` attribute from one source of
    truth.

    ``model``, ``system``, and ``messages`` are passed to both the
    streaming API and the span recorder. Extra ``stream_kwargs``
    (``max_tokens``, ``tools``, …) are forwarded to
    ``client.messages.stream``.

    Example::

        async with traced_anthropic_messages_stream(
            client=self._client,
            model=self._model_name,
            system=self._instructions,
            messages=messages,
            max_tokens=self._max_tokens,
            tools=self._build_api_tools(tools),
        ) as stream:
            async for event in stream:
                ...
    """
    from weave.session.session import start_llm

    with start_llm(
        model=model,
        provider_name="anthropic",
        system_instructions=[system] if system else [],
    ) as llm:
        async with client.messages.stream(
            model=model,
            system=system,
            messages=messages,
            **stream_kwargs,
        ) as stream:
            yield stream
            response = await stream.get_final_message()
            record_anthropic_message(
                llm,
                input_messages=messages,
                system=system,
                response=response,
            )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _user_messages_from_content(content: Any) -> list[Message]:
    """Split a ``role="user"`` payload into user / tool messages.

    Anthropic combines real user text with tool_result blocks under a
    single ``role="user"`` envelope. Weave keeps them distinct so the
    UI can render the tool lane separately.
    """
    if isinstance(content, str):
        return [Message(role="user", content=content)]
    if not isinstance(content, list):
        return []

    tool_responses: list[ToolCallResponsePart] = []
    text_chunks: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "tool_result":
            tool_responses.append(
                ToolCallResponsePart(
                    id=str(block.get("tool_use_id", "")),
                    response=block.get("content", ""),
                )
            )
        elif block_type == "text":
            text = block.get("text")
            if isinstance(text, str) and text:
                text_chunks.append(text)

    messages: list[Message] = []
    if text_chunks:
        messages.append(Message(role="user", content="\n".join(text_chunks)))
    if tool_responses:
        parts: list[MessagePart] = list(tool_responses)
        messages.append(Message(role="tool", parts=parts))
    return messages


def _assistant_message_from_content(content: Any) -> Message:
    """Build an assistant ``Message`` from an Anthropic content payload."""
    if isinstance(content, str):
        return Message(role="assistant", content=content)
    if not isinstance(content, list):
        return Message(role="assistant", content="")

    parts: list[MessagePart] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text")
            if isinstance(text, str) and text:
                parts.append(TextPart(content=text))
        elif block_type == "tool_use":
            parts.append(
                ToolCallPart(
                    id=str(block.get("id", "")),
                    name=str(block.get("name", "")),
                    arguments=block.get("input", ""),
                )
            )
    if not parts:
        return Message(role="assistant", content="")
    return Message(role="assistant", parts=parts)


def _output_from_anthropic_message(message: AnthropicMessage) -> list[Message]:
    """Fold an Anthropic response's content blocks into one assistant ``Message``."""
    text_parts: list[str] = []
    tool_calls: list[ToolCallPart] = []
    for block in message.content:
        block_type = getattr(block, "type", "")
        if block_type == "text":
            text = getattr(block, "text", "")
            if isinstance(text, str) and text:
                text_parts.append(text)
        elif block_type == "tool_use":
            args = getattr(block, "input", "")
            tool_calls.append(
                ToolCallPart(
                    id=getattr(block, "id", ""),
                    name=getattr(block, "name", ""),
                    arguments=args,
                )
            )
    text = "\n".join(text_parts)
    if not text and not tool_calls:
        return []
    if not tool_calls:
        return [Message(role="assistant", content=text)]
    parts: list[MessagePart] = []
    if text:
        parts.append(TextPart(content=text))
    parts.extend(tool_calls)
    return [Message(role="assistant", parts=parts)]
