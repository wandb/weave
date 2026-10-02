"""Order each tool execution directly after the model span that requested it.

Some agents run tools in a different process from the model loop, and that
process stamps `execute_tool` spans with its own clock, off by seconds to
minutes. Sorting siblings by `started_at` then trusts two clocks that disagree,
so an execution can land after the model call that already consumed its result.
A model span's output names each `tool_call_id` it requests, which links the
request to its execution without trusting either clock.
"""

from typing import NamedTuple

from weave.trace_server.agents.constants import TOOL_EXECUTION_OPS
from weave.trace_server.agents.model_tool_calls import parse_content_parts
from weave.trace_server.agents.types import AgentSpanSchema


class ToolCallKey(NamedTuple):
    trace_id: str
    call_id: str


def causal_span_order(spans: list[AgentSpanSchema]) -> list[int]:
    """Return indexes that place each tool execution right after its requester."""
    # Collect every model span that requested each call id. More than one
    # requester makes the id ambiguous.
    call_key_to_requester_indexes: dict[ToolCallKey, set[int]] = {}
    for index, span in enumerate(spans):
        if span.operation_name in TOOL_EXECUTION_OPS:
            continue

        for call_id in _requested_call_ids(span):
            key = ToolCallKey(span.trace_id, call_id)
            call_key_to_requester_indexes.setdefault(key, set()).add(index)

    # An execution sorts at its unique requester's position; an unmatched or
    # ambiguous id keeps the execution at its own clock position.
    anchors: list[int] = []
    for index, span in enumerate(spans):
        anchor = index
        if span.operation_name in TOOL_EXECUTION_OPS and span.tool_call_id:
            key = ToolCallKey(span.trace_id, span.tool_call_id)
            requester_indexes = call_key_to_requester_indexes.get(key, set())
            if len(requester_indexes) == 1:
                anchor = next(iter(requester_indexes))
        anchors.append(anchor)

    # Spans sharing an anchor sort as the requester first (`anchor == index`),
    # then the executions it requested in their original clock order.
    order = sorted(
        range(len(spans)),
        key=lambda index: (anchors[index], anchors[index] != index, index),
    )

    return order


def _requested_call_ids(span: AgentSpanSchema) -> set[str]:
    ids: set[str] = set()
    for message in span.output_messages:
        if message.role != "assistant":
            continue

        for part in parse_content_parts(message.content):
            call_id = part.get("id")
            if part.get("type") == "tool_call" and isinstance(call_id, str) and call_id:
                ids.add(call_id)

    return ids
