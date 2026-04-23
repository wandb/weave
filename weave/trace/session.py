"""Weave Session SDK v3 — structured logging for agent conversations.

Provides Python classes and functions for logging agent conversations
to Weave's Agents tab. All data flows through OpenTelemetry — the SDK
creates OTel spans with GenAI semantic convention attributes.

This module contains the complete v3 API surface. OTel span emission
is not yet implemented — classes are functional stubs that track state
locally.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, PrivateAttr


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


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


class LogResult(BaseModel):
    """Result of a batch log_* call."""

    session_id: str = ""
    trace_ids: list[str] = Field(default_factory=list)
    root_span_ids: list[str] = Field(default_factory=list)
    span_count: int = 0


# ---------------------------------------------------------------------------
# Batch types
# ---------------------------------------------------------------------------


class ChatSpan(BaseModel):
    """Batch helper for describing a chat (LLM call) span."""

    model: str = ""
    provider_name: str = ""
    input_messages: list[dict[str, str]] = Field(default_factory=list)
    output_messages: list[dict[str, str]] = Field(default_factory=list)
    system_instructions: list[str] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    reasoning_content: str = ""
    finish_reasons: list[str] = Field(default_factory=list)


class ToolSpan(BaseModel):
    """Batch helper for describing a tool execution span."""

    name: str = ""
    arguments: str = ""
    result: str = ""
    tool_call_id: str = ""
