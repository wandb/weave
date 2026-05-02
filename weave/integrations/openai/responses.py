"""Manual-instrumentation adapters for OpenAI's Responses API.

When an agent uses the autopatched OpenAI integration, weave handles
message-shape conversion automatically. Manually-instrumented agents
(those building ``start_llm`` spans by hand around ``client.responses``
calls) need an explicit converter from OpenAI's wire format to the
weave Session SDK types — this module is that converter.

Right now this covers the *input* side (``input`` argument to
``client.responses.create``). The output side is ergonomic via
``Message.assistant(text=..., tool_calls=[...])`` from
``weave.session`` — pass the parsed text and tool calls directly.
"""

from __future__ import annotations

import json
from typing import Any

from weave.session.session import _parse_data_url
from weave.session.types import (
    MediaAttachment,
    Message,
    Reasoning,
    ToolCallPart,
    ToolCallResponsePart,
)

__all__ = ["input_to_weave", "reasoning_to_weave"]


_USER_LIKE_ROLES = {"user", "assistant", "system"}
_TEXT_BLOCK_TYPES = {"text", "input_text", "output_text"}
_IMAGE_BLOCK_TYPES = {"input_image", "image_url"}


def input_to_weave(
    items: list[dict[str, Any]],
) -> tuple[list[Message], list[MediaAttachment]]:
    """Convert OpenAI Responses API input items to weave types.

    Returns a pair ``(messages, media_attachments)`` ready to assign to
    ``LLM.input_messages`` and ``LLM.media_attachments``.

    Handles the shapes that appear in the ``input`` parameter to
    ``client.responses.create``:

    - ``{"role": "user"|"assistant"|"system", "content": <str|blocks>}`` —
      becomes a ``Message`` with flat text content. Image blocks within
      a user message produce ``MediaAttachment`` entries.
    - ``{"type": "function_call", "name", "arguments", "call_id"}`` —
      becomes an assistant ``Message`` with a ``ToolCallPart``.
    - ``{"type": "function_call_output", "output", "call_id"}`` —
      becomes a tool ``Message`` with a ``ToolCallResponsePart``.
    - ``{"type": "reasoning", ...}`` — skipped (forwarded via
      ``LLM.think`` / ``LLM.reasoning``, not part of the input replay).
    """
    messages: list[Message] = []
    attachments: list[MediaAttachment] = []
    seen_urls: set[str] = set()

    for item in items:
        item_type = item.get("type")
        role = item.get("role")

        if item_type == "function_call":
            messages.append(_function_call_message(item))
            continue
        if item_type == "function_call_output":
            messages.append(_function_call_output_message(item))
            continue
        if item_type == "reasoning":
            continue

        if role in _USER_LIKE_ROLES:
            content = item.get("content")
            text = _extract_text_content(content)
            if text:
                messages.append(Message(role=role, content=text))
            if role == "user":
                _collect_image_attachments(content, attachments, seen_urls)

    return messages, attachments


def _function_call_message(item: dict[str, Any]) -> Message:
    arguments = item.get("arguments", "")
    if not isinstance(arguments, str):
        arguments = json.dumps(arguments)
    return Message(
        role="assistant",
        parts=[
            ToolCallPart(
                id=str(item.get("call_id", "")),
                name=str(item.get("name", "")),
                arguments=arguments,
            )
        ],
    )


def _function_call_output_message(item: dict[str, Any]) -> Message:
    output = item.get("output")
    response = output if isinstance(output, str) else json.dumps(output)
    return Message(
        role="tool",
        parts=[
            ToolCallResponsePart(
                id=str(item.get("call_id", "")),
                response=response,
            )
        ],
    )


def _extract_text_content(content: Any) -> str:
    """Pull plain text from an OpenAI Responses-style content list or string."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") in _TEXT_BLOCK_TYPES:
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts)


def _collect_image_attachments(
    content: Any,
    attachments: list[MediaAttachment],
    seen_urls: set[str],
) -> None:
    """Walk a user-message content list and collect any image URLs."""
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") not in _IMAGE_BLOCK_TYPES:
            continue
        url = block.get("image_url")
        if isinstance(url, dict):
            url = url.get("url")
        if not isinstance(url, str) or url in seen_urls:
            continue
        seen_urls.add(url)
        attachments.append(_url_to_attachment(url))


def _url_to_attachment(url: str) -> MediaAttachment:
    if url.startswith("data:"):
        mime_type, payload = _parse_data_url(url)
        return MediaAttachment(
            kind="blob",
            modality="image",
            mime_type=mime_type,
            content=payload,
        )
    return MediaAttachment(
        kind="uri",
        modality="image",
        mime_type="",
        uri=url,
    )


def reasoning_to_weave(reasoning_part: dict[str, Any] | None) -> Reasoning | None:
    """Flatten an OpenAI Responses ``reasoning`` item to a ``Reasoning``.

    OpenAI's Responses API returns reasoning as ``{"summary":
    [{"text": "..."}, ...], ...}``; weave's ``Reasoning.content`` is a
    flat string. Joins each summary fragment's ``.text`` with newlines.
    Returns ``None`` for empty input so the caller can pass the result
    straight to ``LLM.record(reasoning=...)`` without a guard.
    """
    if not reasoning_part:
        return None
    summaries = reasoning_part.get("summary", [])
    if not isinstance(summaries, list):
        return None
    text = "\n".join(
        s.get("text", "") for s in summaries if isinstance(s, dict) and s.get("text")
    )
    return Reasoning(content=text) if text else None
