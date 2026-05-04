"""Data types for the Weave Session SDK.

Lives in its own module to break the import cycle between session.py
(span classes) and session_otel.py (attribute builders). Both modules
import from here.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _to_json_string(value: Any) -> str:
    """JSON-encode a value for a string-typed payload field.

    Strings pass through unchanged. ``None`` becomes the empty string. Any
    other JSON-serializable value (dict, list, int, float, bool) is dumped
    via ``json.dumps`` with ``default=str`` for non-JSON natives.

    Used by ``ToolCallPart.arguments`` and ``ToolCallResponsePart.response``
    so callers can pass structured data without manually pre-encoding —
    the underlying GenAI semconv requires a string, but the model layer
    is more ergonomic when it accepts native types.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _parse_data_url(url: str) -> tuple[str, str]:
    """Split a ``data:`` URL into ``(mime_type, payload)``.

    Returns the raw payload after the comma — base64-encoded content is
    NOT decoded; it's passed through to ``MediaAttachment.content`` as-is
    so the wire format matches what the producer originally embedded.
    Returns ``("", "")`` for non-data URLs.
    """
    if not url.startswith("data:"):
        return ("", "")
    header, _, payload = url[len("data:") :].partition(",")
    mime_type = header.partition(";")[0]
    return (mime_type, payload)


# Type alias for fields that store a string per semconv but accept any
# JSON-serializable value at construction. Stored value is always ``str``
# after validation; the union is for caller ergonomics.
JSONStringInput = str | dict[str, Any] | list[Any] | int | float | bool | None


# ---------------------------------------------------------------------------
# Message parts (GenAI semantic convention v1.40.0+ "Development tier")
# ---------------------------------------------------------------------------
#
# A Message can either be constructed with a flat ``content`` string (the
# original API, kept for back-compat and ergonomics) or with an explicit
# ``parts`` list. When ``parts`` is non-empty it is the canonical
# representation; otherwise the serializer synthesizes a single TextPart or
# ToolCallResponsePart from the flat fields.
#
# Part types match the semconv schemas at:
#   docs/gen-ai/gen-ai-input-messages.json
#   docs/gen-ai/gen-ai-output-messages.json


class TextPart(BaseModel):
    """Plain-text content part."""

    type: Literal["text"] = "text"
    content: str = ""


class ReasoningPart(BaseModel):
    """Reasoning / chain-of-thought content part."""

    type: Literal["reasoning"] = "reasoning"
    content: str = ""


class ToolCallPart(BaseModel):
    """An assistant's request to invoke a tool.

    ``arguments`` is stored as a JSON-encoded string per the GenAI
    semconv. For ergonomics, you may pass a dict / list / scalar at
    construction and the SDK will JSON-encode it. When you already have
    a JSON string from the model, pass it through as-is.
    """

    model_config = ConfigDict(validate_assignment=True)

    type: Literal["tool_call"] = "tool_call"
    id: str = ""
    name: str = ""
    arguments: JSONStringInput = ""

    @field_validator("arguments", mode="before")
    @classmethod
    def _serialize_arguments(cls, v: Any) -> str:
        return _to_json_string(v)


class ToolCallResponsePart(BaseModel):
    """The result of executing a previously-requested tool call.

    ``response`` is stored as a string per semconv. Non-string values
    passed at construction or assignment are JSON-encoded by the SDK.
    """

    model_config = ConfigDict(validate_assignment=True)

    type: Literal["tool_call_response"] = "tool_call_response"
    id: str = ""
    response: JSONStringInput = ""

    @field_validator("response", mode="before")
    @classmethod
    def _serialize_response(cls, v: Any) -> str:
        return _to_json_string(v)


class BlobPart(BaseModel):
    """Inline binary content (e.g. base64-encoded image / audio)."""

    type: Literal["blob"] = "blob"
    mime_type: str = ""
    modality: str = ""
    content: str = ""


class UriPart(BaseModel):
    """Reference to media content by URI."""

    type: Literal["uri"] = "uri"
    mime_type: str = ""
    modality: str = ""
    uri: str = ""


class FilePart(BaseModel):
    """Reference to media content by provider-side file id."""

    type: Literal["file"] = "file"
    mime_type: str = ""
    modality: str = ""
    file_id: str = ""


MessagePart = Annotated[
    TextPart
    | ReasoningPart
    | ToolCallPart
    | ToolCallResponsePart
    | BlobPart
    | UriPart
    | FilePart,
    Field(discriminator="type"),
]


class Message(BaseModel):
    """A single message in a conversation.

    Two construction styles are supported:

    1. Flat (back-compat, ergonomic for plain text):
       ``Message(role="assistant", content="Hi there")``

    2. Explicit parts (richer — supports tool calls, mixed reasoning+text,
       inline media):
       ``Message(role="assistant", parts=[TextPart(content="Let me check"),
       ToolCallPart(id="c1", name="get_weather", arguments='{...}')])``

    When ``parts`` is non-empty it is the canonical representation. When
    empty, the serializer synthesizes a single TextPart (or
    ToolCallResponsePart for ``role="tool"``) from the flat fields.
    """

    role: Literal["user", "assistant", "system", "tool"]
    content: str = ""
    tool_call_id: str = ""
    tool_name: str = ""
    parts: list[MessagePart] = Field(default_factory=list)

    @classmethod
    def user(cls, text: str) -> Message:
        """Build a user message from plain text."""
        return cls(role="user", content=text)

    @classmethod
    def system(cls, text: str) -> Message:
        """Build a system message from plain text."""
        return cls(role="system", content=text)

    @classmethod
    def assistant(
        cls,
        text: str = "",
        *,
        tool_calls: list[ToolCallPart] | None = None,
    ) -> Message:
        """Build an assistant message with optional text and tool calls.

        Use plain text for simple replies; pass ``tool_calls`` when the
        assistant requests one or more tools. When both are present the
        text is emitted as a leading ``TextPart`` followed by each
        ``ToolCallPart`` so the chat view renders them inline.
        """
        if not tool_calls:
            return cls(role="assistant", content=text)
        parts: list[MessagePart] = []
        if text:
            parts.append(TextPart(content=text))
        parts.extend(tool_calls)
        return cls(role="assistant", parts=parts)

    @classmethod
    def tool_result(cls, call_id: str, output: Any) -> Message:
        """Build a tool-result message for a previously-requested tool call.

        ``output`` may be a string, dict, list, scalar, or ``None`` — the
        underlying ``ToolCallResponsePart`` JSON-encodes non-strings.
        """
        return cls(
            role="tool",
            parts=[ToolCallResponsePart(id=call_id, response=output)],
        )

    @classmethod
    def from_openai_responses_input(
        cls, items: list[dict[str, Any]]
    ) -> tuple[list[Message], list[MediaAttachment]]:
        """Convert OpenAI Responses API input items to weave types.

        Returns a pair ``(messages, media_attachments)`` ready to assign
        to ``LLM.input_messages`` and ``LLM.media_attachments``. Use this
        when manually instrumenting a ``client.responses.create`` call.

        Handles the shapes that appear in the ``input`` parameter to
        ``client.responses.create``:

        - ``{"role": "user"|"assistant"|"system", "content": <str|blocks>}``
          becomes a ``Message`` with flat text content. User messages are
          always emitted (even if text is empty) so image-only inputs
          have a slot for ``_serialize_input_messages`` to bind
          attachments to. Image blocks within a user message produce
          ``MediaAttachment`` entries.
        - ``{"type": "function_call", "name", "arguments", "call_id"}``
          becomes a ``ToolCallPart``. Consecutive ``function_call`` items
          (parallel tool calls in one assistant turn) are coalesced into
          a single assistant ``Message`` with multiple ``ToolCallPart``s,
          matching ``Message.assistant(tool_calls=[...])``.
        - ``{"type": "function_call_output", "output", "call_id"}``
          becomes a tool ``Message`` with a ``ToolCallResponsePart``.
        - ``{"type": "reasoning", ...}`` is skipped (forwarded via
          ``LLM.think`` / ``LLM.reasoning``, not part of input replay).
        """
        messages: list[Message] = []
        attachments: list[MediaAttachment] = []
        seen_urls: set[str] = set()
        pending_tool_calls: list[ToolCallPart] = []

        def flush_pending_tool_calls() -> None:
            if pending_tool_calls:
                messages.append(cls.assistant(tool_calls=list(pending_tool_calls)))
                pending_tool_calls.clear()

        for item in items:
            item_type = item.get("type")
            role = item.get("role")

            if item_type == "function_call":
                pending_tool_calls.append(_oai_to_tool_call_part(item))
                continue

            flush_pending_tool_calls()

            if item_type == "function_call_output":
                messages.append(_oai_function_call_output_message(item))
                continue
            if item_type == "reasoning":
                continue

            if role in _OAI_USER_LIKE_ROLES:
                content = item.get("content")
                text = _oai_extract_text_content(content)
                if role == "user":
                    messages.append(cls(role=role, content=text))
                    _oai_collect_image_attachments(content, attachments, seen_urls)
                elif text:
                    messages.append(cls(role=role, content=text))

        flush_pending_tool_calls()

        return messages, attachments


class Usage(BaseModel):
    """Token usage for an LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @classmethod
    def from_openai_responses(cls, response: Any) -> Usage:
        """Extract usage from an OpenAI Responses API ``Response``.

        ``response.usage`` may be ``None`` for partial / streamed responses
        that have not yet emitted a final usage block; callers get an empty
        ``Usage`` in that case so they can still pass the result through to
        ``LLM.record(usage=...)`` unconditionally. The nested
        ``input_tokens_details`` and ``output_tokens_details`` objects are
        also defended against ``None`` to match the streaming-friendly
        handling in ``weave.integrations.openai.openai_sdk``.
        """
        usage = response.usage
        if usage is None:
            return cls()
        out_details = usage.output_tokens_details
        in_details = usage.input_tokens_details
        return cls(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            reasoning_tokens=(out_details and out_details.reasoning_tokens) or 0,
            cache_read_input_tokens=(in_details and in_details.cached_tokens) or 0,
        )

    @classmethod
    def from_anthropic(cls, message: Any) -> Usage:
        """Extract usage from an Anthropic Messages API ``Message``.

        Anthropic's ``Usage`` types the cache fields as ``Optional[int]``;
        ``None`` is equivalent to zero for our purposes.
        """
        usage = message.usage
        return cls(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_creation_input_tokens=usage.cache_creation_input_tokens or 0,
            cache_read_input_tokens=usage.cache_read_input_tokens or 0,
        )


class Reasoning(BaseModel):
    """Reasoning/chain-of-thought content from an LLM call."""

    content: str = ""

    @classmethod
    def from_openai_responses(cls, part: dict[str, Any] | None) -> Reasoning | None:
        """Flatten an OpenAI Responses ``reasoning`` item to a ``Reasoning``.

        OpenAI's Responses API returns reasoning as
        ``{"summary": [{"text": "..."}, ...], ...}``; ``Reasoning.content``
        is a flat string. Returns ``None`` for empty input so the caller
        can pass the result straight to ``LLM.record(reasoning=...)``.
        """
        if not part:
            return None
        summaries = part.get("summary", [])
        if not isinstance(summaries, list):
            return None
        text = "\n".join(
            s.get("text", "")
            for s in summaries
            if isinstance(s, dict) and s.get("text")
        )
        return cls(content=text) if text else None


class MediaAttachment(BaseModel):
    """A media attachment on an LLM call."""

    kind: Literal["blob", "uri", "file"]
    modality: str = ""
    mime_type: str = ""
    content: bytes | str = ""
    uri: str = ""
    file_id: str = ""


class LogResult(BaseModel):
    """Result of a batch log_* call."""

    session_id: str = ""
    trace_ids: list[str] = Field(default_factory=list)
    root_span_ids: list[str] = Field(default_factory=list)
    span_count: int = 0


# ---------------------------------------------------------------------------
# OpenAI Responses API input-item helpers
# ---------------------------------------------------------------------------
#
# These back ``Message.from_openai_responses_input`` and live here, alongside
# the type definitions, so the conversion implementation does not require an
# import from the integrations layer (which would be a cycle).


_OAI_USER_LIKE_ROLES = {"user", "assistant", "system"}
_OAI_TEXT_BLOCK_TYPES = {"text", "input_text", "output_text"}
_OAI_IMAGE_BLOCK_TYPES = {"input_image", "image_url"}


def _oai_to_tool_call_part(item: dict[str, Any]) -> ToolCallPart:
    arguments = item.get("arguments", "")
    if not isinstance(arguments, str):
        arguments = json.dumps(arguments)
    return ToolCallPart(
        id=str(item.get("call_id", "")),
        name=str(item.get("name", "")),
        arguments=arguments,
    )


def _oai_function_call_output_message(item: dict[str, Any]) -> Message:
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


def _oai_extract_text_content(content: Any) -> str:
    """Pull plain text from an OpenAI Responses-style content list or string."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") in _OAI_TEXT_BLOCK_TYPES:
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts)


def _oai_collect_image_attachments(
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
        if block.get("type") not in _OAI_IMAGE_BLOCK_TYPES:
            continue
        url = block.get("image_url")
        if isinstance(url, dict):
            url = url.get("url")
        if not isinstance(url, str) or url in seen_urls:
            continue
        seen_urls.add(url)
        attachments.append(_oai_url_to_attachment(url))


def _oai_url_to_attachment(url: str) -> MediaAttachment:
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
