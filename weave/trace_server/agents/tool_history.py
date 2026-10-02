"""Recover paired tool evidence carried by a continuation's model input."""

import json

from weave.trace_server.agents.model_tool_calls import (
    model_tool_call_messages,
    parse_content_parts,
)
from weave.trace_server.agents.schema import NormalizedMessage
from weave.trace_server.agents.types import AgentChatMessage, AgentSpanSchema


def input_tool_history(
    span: AgentSpanSchema,
    *,
    agent_name: str | None,
    seen_call_ids: set[tuple[str, str, str]],
) -> list[AgentChatMessage]:
    """Retain matched requests and responses since the last recorded user message."""
    boundary: int | None = None
    for index, message in enumerate(span.input_messages):
        if message.role == "user":
            boundary = index

    if boundary is None:
        return []

    requests: dict[str, NormalizedMessage] = {}
    messages: list[AgentChatMessage] = []
    for message in span.input_messages[boundary + 1 :]:
        for part in parse_content_parts(message.content):
            call_id = part.get("id")
            if not isinstance(call_id, str) or not call_id:
                continue

            if message.role == "assistant" and part.get("type") == "tool_call":
                requests[call_id] = message.model_copy(
                    update={"content": json.dumps([part])}
                )
                continue

            if message.role != "tool":
                continue

            if part.get("type") != "tool_call_response":
                continue

            request = requests.pop(call_id, None)
            if request is None or "response" not in part:
                continue

            request_span = span.model_copy(update={"output_messages": [request]})
            projected = model_tool_call_messages(
                request_span, agent_name=agent_name, seen_call_ids=seen_call_ids
            )
            response = part["response"]
            result = response if isinstance(response, str) else json.dumps(response)
            for projected_message in projected:
                if projected_message.tool_call is not None:
                    projected_message.tool_call.tool_result = result
                projected_message.started_at = None
                messages.append(projected_message)

    return messages
