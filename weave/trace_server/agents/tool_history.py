"""Attach tool results that a continuation's model input replays."""

import json

from weave.trace_server.agents.model_tool_calls import SeenCalls, parse_content_parts
from weave.trace_server.agents.types import AgentSpanSchema


def attach_input_tool_results(span: AgentSpanSchema, seen_call_ids: SeenCalls) -> None:
    """Fill results on already-emitted model requests from responses in `span` input."""
    # Match on part type, not role: some SDKs send tool responses as role=user.
    for message in span.input_messages:
        for part in parse_content_parts(message.content):
            if part.get("type") != "tool_call_response":
                continue

            if "response" not in part:
                continue

            call_id = part.get("id")
            if not isinstance(call_id, str):
                continue

            key = (span.trace_id, call_id)
            # TODO: a call seen only in model input (its requesting span was not
            # captured) is not projected; revisit if production traces carry it.
            if key not in seen_call_ids:
                continue

            # Execution spans map to None and keep their own recorded result.
            recorded = seen_call_ids[key]
            if recorded is None:
                continue

            if recorded.tool_result is not None:
                continue

            response = part["response"]
            recorded.tool_result = (
                response if isinstance(response, str) else json.dumps(response)
            )
