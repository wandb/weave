"""Data types for the Weave Session SDK.

Lives in its own module to break the import cycle between session.py
(span classes) and session_otel.py (attribute builders). Both modules
import from here.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

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

    ``arguments`` is a JSON-encoded string per semconv (the model emits
    JSON; we don't re-encode at the SDK layer).
    """

    type: Literal["tool_call"] = "tool_call"
    id: str = ""
    name: str = ""
    arguments: str = ""


class ToolCallResponsePart(BaseModel):
    """The result of executing a previously-requested tool call."""

    type: Literal["tool_call_response"] = "tool_call_response"
    id: str = ""
    response: str = ""


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
