"""OTel attribute builders for the Weave Session SDK.

Each function returns a dict of GenAI semantic convention attributes
for a specific span type. These are stubs — they return empty dicts.
The follow-up PR will populate them with real attribute mappings.
"""

from __future__ import annotations

from typing import Any

from weave.session.session import Message, Reasoning, Usage


def invoke_agent_attributes(
    *,
    agent_name: str,
    conversation_id: str = "",
    conversation_name: str = "",
    provider_name: str = "",
    model: str = "",
    input_messages: list[Message] | None = None,
    output_messages: list[Message] | None = None,
) -> dict[str, Any]:
    """Build OTel attributes for an invoke_agent span. Stub."""
    return {}


def llm_attributes(
    *,
    model: str,
    provider_name: str = "",
    input_messages: list[Message] | None = None,
    output_messages: list[Message] | None = None,
    system_instructions: list[str] | None = None,
    usage: Usage | None = None,
    reasoning: Reasoning | None = None,
    finish_reasons: list[str] | None = None,
    response_id: str = "",
) -> dict[str, Any]:
    """Build OTel attributes for an LLM call (chat operation) span. Stub."""
    return {}


def execute_tool_attributes(
    *,
    tool_name: str,
    tool_call_arguments: str = "",
    tool_call_result: str = "",
    tool_call_id: str = "",
) -> dict[str, Any]:
    """Build OTel attributes for an execute_tool span. Stub."""
    return {}
