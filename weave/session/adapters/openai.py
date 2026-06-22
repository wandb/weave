"""Adapters from OpenAI's wire format to the Weave Session SDK types.

Use these when manually instrumenting calls to ``client.responses.create``
(the autopatched OpenAI integration handles conversion automatically).

Public functions:

- ``message_from_openai_responses_input(items)`` — convert the ``input=``
  list passed to ``client.responses.create`` into ``(messages, attachments)``
  ready to assign to ``LLM.input_messages`` / ``LLM.media_attachments``.
- ``reasoning_from_openai_responses(part)`` — flatten a Responses
  ``reasoning`` item into a ``Reasoning`` (or ``None`` if empty).
- ``usage_from_openai_responses(response)`` — pull token counts off a
  Responses ``Response``. Tolerates missing ``usage`` and missing
  ``input_tokens_details`` / ``output_tokens_details`` (both can be
  ``None`` for streamed / partial responses).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from weave.session.session import _publish_media_content
from weave.session.types import (
    MediaAttachment,
    Message,
    Reasoning,
    ToolCallPart,
    ToolCallResponsePart,
    Usage,
    _parse_data_url,
)

if TYPE_CHECKING:
    from openai.types.responses import Response

__all__ = [
    "message_from_openai_responses_input",
    "reasoning_from_openai_responses",
    "usage_from_openai_responses",
]


_USER_LIKE_ROLES = {"user", "assistant", "system"}
_TEXT_BLOCK_TYPES = {"text", "input_text", "output_text"}
_IMAGE_BLOCK_TYPES = {"input_image", "image_url"}


def message_from_openai_responses_input(
    items: list[dict[str, Any]],
) -> tuple[list[Message], list[MediaAttachment]]:
    """Convert OpenAI Responses API input items to weave types.

    Returns a pair ``(messages, media_attachments)`` ready to assign to
    ``LLM.input_messages`` and ``LLM.media_attachments``.

    Handles the shapes that appear in the ``input`` parameter to
    ``client.responses.create``:

    - ``{"role": "user"|"assistant"|"system", "content": <str|blocks>}``
      becomes a ``Message`` with flat text content. User messages are
      always emitted (even if text is empty) so image-only inputs have
      a slot for ``_serialize_input_messages`` to bind attachments to.
      Image blocks within a user message produce ``MediaAttachment``
      entries.
    - ``{"type": "function_call", "name", "arguments", "call_id"}``
      becomes a ``ToolCallPart``. Consecutive ``function_call`` items
      (parallel tool calls in one assistant turn) are coalesced into a
      single assistant ``Message`` with multiple ``ToolCallPart``s,
      matching ``Message.assistant(tool_calls=[...])``.
    - ``{"type": "function_call_output", "output", "call_id"}`` becomes
      a tool ``Message`` with a ``ToolCallResponsePart``.
    - ``{"type": "reasoning", ...}`` is skipped (forwarded via
      ``LLM.think`` / ``LLM.reasoning``, not part of input replay).
    """
    messages: list[Message] = []
    attachments: list[MediaAttachment] = []
    seen_urls: set[str] = set()
    pending_tool_calls: list[ToolCallPart] = []

    def flush_pending_tool_calls() -> None:
        if pending_tool_calls:
            messages.append(Message.assistant(tool_calls=list(pending_tool_calls)))
            pending_tool_calls.clear()

    for item in items:
        item_type = item.get("type")
        role = item.get("role")

        if item_type == "function_call":
            pending_tool_calls.append(_to_tool_call_part(item))
            continue

        flush_pending_tool_calls()

        if item_type == "function_call_output":
            messages.append(_function_call_output_message(item))
            continue
        if item_type == "reasoning":
            continue

        if role in _USER_LIKE_ROLES:
            content = item.get("content")
            text = _extract_text_content(content)
            if role == "user":
                messages.append(Message(role=role, content=text))
                _collect_image_attachments(content, attachments, seen_urls)
            elif text:
                messages.append(Message(role=role, content=text))

    flush_pending_tool_calls()

    return messages, attachments


def reasoning_from_openai_responses(part: dict[str, Any] | None) -> Reasoning | None:
    """Flatten an OpenAI Responses ``reasoning`` item to a ``Reasoning``.

    OpenAI returns reasoning as ``{"summary": [{"text": "..."}, ...]}``;
    ``Reasoning.content`` is a flat string. Returns ``None`` for empty
    input so callers can pipe the result through to
    ``LLM.record(reasoning=...)`` unconditionally.
    """
    if not part:
        return None
    summaries = part.get("summary", [])
    if not isinstance(summaries, list):
        return None
    text = "\n".join(
        s.get("text", "") for s in summaries if isinstance(s, dict) and s.get("text")
    )
    return Reasoning(content=text) if text else None


def usage_from_openai_responses(response: Response) -> Usage:
    """Extract usage from an OpenAI Responses API ``Response``.

    ``response.usage`` may be ``None`` for partial / streamed responses
    that have not yet emitted a final usage block; an empty ``Usage``
    is returned in that case so callers can pass the result through to
    ``LLM.record(usage=...)`` unconditionally. The nested
    ``input_tokens_details`` and ``output_tokens_details`` are also
    defended against ``None``, matching the streaming-friendly handling
    in ``weave.integrations.openai.openai_sdk``.
    """
    usage = response.usage
    if usage is None:
        return Usage()
    out_details = usage.output_tokens_details
    in_details = usage.input_tokens_details
    return Usage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        reasoning_tokens=(out_details and out_details.reasoning_tokens) or 0,
        cache_read_input_tokens=(in_details and in_details.cached_tokens) or 0,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_tool_call_part(item: dict[str, Any]) -> ToolCallPart:
    return ToolCallPart(
        id=str(item.get("call_id", "")),
        name=str(item.get("name", "")),
        arguments=item.get("arguments", ""),
    )


def _function_call_output_message(item: dict[str, Any]) -> Message:
    return Message(
        role="tool",
        parts=[
            ToolCallResponsePart(
                id=str(item.get("call_id", "")),
                response=item.get("output", ""),
            )
        ],
    )


def _extract_text_content(content: Any) -> str:
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
        ref_uri = _publish_media_content(
            content=payload, uri="", file_id="", mime_type=mime_type
        )
        return MediaAttachment(ref=ref_uri, modality="image", mime_type=mime_type)
    ref_uri = _publish_media_content(content="", uri=url, file_id="", mime_type="")
    return MediaAttachment(ref=ref_uri, modality="image", mime_type="")
