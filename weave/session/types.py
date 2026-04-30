"""Data types for the Weave Session SDK.

Lives in its own module to break the import cycle between session.py
(span classes) and session_otel.py (attribute builders). Both modules
import from here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single message in a conversation."""

    role: Literal["user", "assistant", "system", "tool"]
    content: str = ""
    tool_call_id: str = ""
    tool_name: str = ""


class Usage(BaseModel):
    """Token usage for an LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0


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
