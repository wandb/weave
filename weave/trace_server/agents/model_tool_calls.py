"""Preserve model-requested calls when execution spans are absent."""

from __future__ import annotations

import json

from weave.trace_server.agents.types import (
    AgentChatMessage,
    AgentChatToolCall,
    AgentSpanSchema,
)


def model_tool_call_messages(
    span: AgentSpanSchema,
    *,
    agent_name: str | None,
    seen_call_ids: set[tuple[str, str]],
) -> list[AgentChatMessage]:
    """Project observed requests without claiming execution or success."""
    messages: list[AgentChatMessage] = []

    for message in span.output_messages:
        if message.role != "assistant":
            continue

        for part in parse_content_parts(message.content):
            if part.get("type") != "tool_call":
                continue

            name = part.get("name")
            if not isinstance(name, str) or not name:
                continue

            call_id = part.get("id")
            if isinstance(call_id, str) and call_id:
                key = (span.trace_id, call_id)
                if key in seen_call_ids:
                    continue

                seen_call_ids.add(key)

            arguments = part.get("arguments")
            if arguments is not None and not isinstance(arguments, str):
                arguments = json.dumps(arguments)

            messages.append(
                AgentChatMessage(
                    type="tool_call",
                    span_id=span.span_id,
                    agent_name=agent_name,
                    agent_version=span.agent_version,
                    started_at=span.ended_at or span.started_at,
                    tool_call=AgentChatToolCall(
                        tool_name=name,
                        tool_arguments=arguments,
                    ),
                )
            )

    return messages


def parse_content_parts(content: str) -> list[dict[str, object]]:
    """Read normalized message parts, ignoring plain text and malformed JSON."""
    if not content.lstrip().startswith("["):
        return []

    try:
        parsed: object = json.loads(content)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    parts = [part for part in parsed if isinstance(part, dict)]

    return parts
