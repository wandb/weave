"""Preserve model-requested calls when execution spans are absent."""

from __future__ import annotations

import json
from collections.abc import Iterator

from weave.trace_server.agents.schema import NormalizedMessage
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


def model_output_segments(
    span: AgentSpanSchema,
    *,
    agent_name: str | None,
    seen_call_ids: set[tuple[str, str]],
) -> Iterator[tuple[list[NormalizedMessage], AgentChatMessage | None]]:
    """Split output at unmatched requests while retaining source order."""
    pending: list[NormalizedMessage] = []
    for message in span.output_messages:
        parts = parse_content_parts(message.content)
        if message.role != "assistant" or not parts:
            pending.append(message)
            continue

        content_parts: list[dict[str, object]] = []
        for part in parts:
            if part.get("type") != "tool_call":
                content_parts.append(part)
                continue

            request_span = span.model_copy(
                update={
                    "output_messages": [
                        message.model_copy(update={"content": json.dumps([part])})
                    ]
                }
            )
            requests = model_tool_call_messages(
                request_span, agent_name=agent_name, seen_call_ids=seen_call_ids
            )
            if not requests:
                content_parts.append(part)
                continue

            if content_parts:
                pending.append(
                    message.model_copy(update={"content": json.dumps(content_parts)})
                )
                content_parts = []
            yield pending, requests[0]
            pending = []

        if content_parts:
            pending.append(
                message.model_copy(update={"content": json.dumps(content_parts)})
            )

    yield pending, None


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
