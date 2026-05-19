"""Adapters from OpenAI's wire format to the Weave Session SDK types.

Use these when manually instrumenting calls to ``client.responses.create``
(the autopatched OpenAI integration handles conversion automatically).

Public functions:

- ``traced_openai_responses_stream(client, ...)`` — async context manager
  that wraps a streaming ``client.responses.stream(...)`` call with a
  weave chat span. Opens the stream + ``start_llm`` together, yields the
  stream to the caller, and on close calls
  ``stream.get_final_response()`` + ``record_openai_responses`` so the
  span gets every ``gen_ai.*`` attribute populated from one source of
  truth. Use this when you want one-line span emission around a stream.
- ``record_openai_responses(llm, input_items, response)`` — lower-level
  helper that populates an existing ``LLM`` span from a final Responses
  ``Response``. Use when you need to manage the span yourself.
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

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from weave.session.types import (
    MediaAttachment,
    Message,
    MessagePart,
    Reasoning,
    TextPart,
    ToolCallPart,
    ToolCallResponsePart,
    Usage,
    _parse_data_url,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from openai import AsyncOpenAI
    from openai.types.responses import Response

    from weave.session.session import LLM

__all__ = [
    "message_from_openai_responses_input",
    "reasoning_from_openai_responses",
    "record_openai_responses",
    "traced_openai_responses_stream",
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


def record_openai_responses(
    llm: LLM,
    *,
    input_items: list[dict[str, Any]],
    response: Response,
) -> None:
    """Populate an ``LLM`` span from a final OpenAI Responses ``Response``.

    Single source of truth for the OpenAI → Weave mapping. Mirrors what
    ``opentelemetry-instrumentation-openai-v2`` does in its stream
    cleanup: accumulate chunks internally during streaming, then unpack
    the final assembled object once at the end.

    Sets ``input_messages`` / ``media_attachments`` from ``input_items``;
    derives ``output_messages`` + ``reasoning`` from the response output
    items; and writes ``usage`` / ``response_id`` / ``response_model`` /
    ``finish_reasons`` from the response envelope.
    """
    input_messages, media_attachments = message_from_openai_responses_input(input_items)
    output_messages, reasoning = _output_from_openai_responses(response)
    llm.record(
        input_messages=input_messages,
        media_attachments=media_attachments,
        output_messages=output_messages,
        usage=usage_from_openai_responses(response),
        reasoning=reasoning,
        response_id=response.id,
        response_model=response.model,
        finish_reasons=_finish_reasons_from_openai_response(response),
    )


@asynccontextmanager
async def traced_openai_responses_stream(
    *,
    client: AsyncOpenAI,
    input: list[dict[str, Any]],
    model: str,
    instructions: str = "",
    **stream_kwargs: Any,
) -> AsyncIterator[Any]:
    """Wrap ``client.responses.stream(...)`` with a weave chat span.

    Opens ``start_llm`` and ``client.responses.stream(...)`` together,
    yields the stream context to the caller, and on close calls
    ``stream.get_final_response()`` + ``record_openai_responses`` so the
    chat span gets every ``gen_ai.*`` attribute from one source of
    truth. Use this when you want one-line span emission around a
    streaming call.

    ``model``, ``instructions``, and ``input`` are passed both to the
    streaming API and to the span recorder. Extra ``stream_kwargs``
    (``tools``, ``reasoning``, ``parallel_tool_calls``, …) are forwarded
    to ``client.responses.stream``.

    Example::

        async with traced_openai_responses_stream(
            client=self.client,
            model=self._model_name,
            instructions=self._instructions,
            input=messages,
            tools=self._build_api_tools(tools),
            reasoning=Reasoning(effort="medium", summary="auto"),
            parallel_tool_calls=True,
        ) as stream:
            async for event in stream:
                ...
    """
    # Local import — avoids a hard ``weave.session.session`` dependency at
    # module-import time and matches the pattern used by other adapters
    # that need access to span constructors only when invoked.
    from weave.session.session import start_llm

    with start_llm(
        model=model,
        provider_name="openai",
        system_instructions=[instructions] if instructions else [],
    ) as llm:
        async with client.responses.stream(
            model=model,
            instructions=instructions,
            input=input,
            **stream_kwargs,
        ) as stream:
            yield stream
            response = await stream.get_final_response()
            record_openai_responses(llm, input_items=input, response=response)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Map OpenAI Responses ``incomplete_details.reason`` values to the GenAI
# semconv ``gen_ai.response.finish_reasons`` vocabulary so dashboards built
# against the standard can compare across providers.
_RESPONSE_INCOMPLETE_TO_FINISH = {
    "max_output_tokens": "length",
    "content_filter": "content_filter",
}


def _finish_reasons_from_openai_response(response: Response) -> list[str]:
    """Map a Responses API ``status`` / ``incomplete_details`` to finish_reasons."""
    if response.status == "completed":
        return ["stop"]
    if response.status == "incomplete":
        details = response.incomplete_details
        reason = details.reason if details and details.reason else ""
        return [_RESPONSE_INCOMPLETE_TO_FINISH.get(reason, reason or "incomplete")]
    if response.status in {"failed", "cancelled"}:
        return [response.status]
    return []


def _output_from_openai_responses(
    response: Response,
) -> tuple[list[Message], Reasoning | None]:
    """Extract ``(output_messages, reasoning)`` from a Responses ``Response``.

    Folds text + tool calls from ``response.output`` into a single
    assistant ``Message`` (matching ``Message.assistant(text, tool_calls=...)``)
    so the chat view renders them inline. Any ``reasoning`` items in the
    output are flattened via ``reasoning_from_openai_responses``.
    """
    text_parts: list[str] = []
    tool_calls: list[ToolCallPart] = []
    reasoning: Reasoning | None = None
    for item in response.output:
        item_type = getattr(item, "type", "")
        if item_type == "message":
            for block in getattr(item, "content", []):
                text = getattr(block, "text", None)
                if isinstance(text, str) and text:
                    text_parts.append(text)
        elif item_type == "reasoning":
            reasoning = reasoning_from_openai_responses(
                item.model_dump(exclude_none=True)
            )
        elif item_type == "function_call":
            tool_calls.append(
                ToolCallPart(
                    id=getattr(item, "call_id", ""),
                    name=getattr(item, "name", ""),
                    arguments=getattr(item, "arguments", ""),
                )
            )
    text = "\n".join(text_parts)
    if not text and not tool_calls:
        return [], reasoning
    if not tool_calls:
        return [Message(role="assistant", content=text)], reasoning
    parts: list[MessagePart] = []
    if text:
        parts.append(TextPart(content=text))
    parts.extend(tool_calls)
    return [Message(role="assistant", parts=parts)], reasoning


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
