"""Data types for the Weave Conversation SDK.

Lives in its own module to break the import cycle between conversation.py
(span classes) and conversation_otel.py (attribute builders). Both modules
import from here.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _to_json_string(value: Any) -> str:
    """JSON-encode a value for a string-typed payload field.

    Strings pass through unchanged. ``None`` becomes the empty string. Any
    other JSON-serializable value (dict, list, int, float, bool) is dumped
    via ``json.dumps`` with ``default=str`` for non-JSON natives.

    Used by the ``JSONString`` annotated alias so fields whose wire format
    is a JSON-encoded string can accept native Python values at the
    construction / assignment boundary while declaring their stored type
    honestly as ``str``.
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


# Annotated string type for fields whose wire format is a JSON-encoded
# string. Pyright sees the field type as ``str``; pydantic accepts any
# JSON-serializable input and coerces via ``_to_json_string`` before
# validation. Use this anywhere the GenAI semconv (or any other wire
# spec) requires a string but the in-memory ergonomic input is structured
# data. Same pattern as ``CallsFilterLike`` in ``weave/trace/casting.py``.
JSONString = Annotated[str, BeforeValidator(_to_json_string)]


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

    ``arguments`` is a string on the wire (per GenAI semconv). The
    ``JSONString`` annotation lets callers pass a dict / list / scalar
    at construction or assignment and the SDK JSON-encodes it; an
    already-encoded string passes through unchanged.
    """

    model_config = ConfigDict(validate_assignment=True)

    type: Literal["tool_call"] = "tool_call"
    id: str = ""
    name: str = ""
    arguments: JSONString = ""


class ToolCallResponsePart(BaseModel):
    """The result of executing a previously-requested tool call.

    ``response`` is a string on the wire. Same ``JSONString`` ergonomics
    as ``ToolCallPart.arguments``.
    """

    model_config = ConfigDict(validate_assignment=True)

    type: Literal["tool_call_response"] = "tool_call_response"
    id: str = ""
    response: JSONString = ""


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


class Usage(BaseModel):
    """Token usage for an LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


class Reasoning(BaseModel):
    """Reasoning/chain-of-thought content from an LLM call."""

    content: str = ""


class MediaAttachment(BaseModel):
    """A media attachment on an LLM call.

    Always holds a ``weave://`` content ref URI.  Raw bytes, data-URLs,
    and plain HTTP URIs are converted to a published ``Content`` object
    by ``LLM.attach_media`` before being stored here.
    """

    ref: str
    modality: str = ""
    mime_type: str = ""


class LogResult(BaseModel):
    """Result of a batch log_* call."""

    conversation_id: str = ""
    trace_ids: list[str] = Field(default_factory=list)
    root_span_ids: list[str] = Field(default_factory=list)
    span_count: int = 0
