"""Order each tool execution directly after the model span that requested it."""

from weave.trace_server.agents.constants import TOOL_EXECUTION_OPS
from weave.trace_server.agents.model_tool_calls import parse_content_parts
from weave.trace_server.agents.types import AgentSpanSchema


def causal_span_order(spans: list[AgentSpanSchema]) -> list[int]:
    """Return clock order with each execution moved behind its unique requester."""
    requesters: dict[tuple[str, str], set[int]] = {}
    for index, span in enumerate(spans):
        if span.operation_name in TOOL_EXECUTION_OPS:
            continue

        for call_id in _requested_call_ids(span):
            requesters.setdefault((span.trace_id, call_id), set()).add(index)

    # Producer clocks can disagree, so an execution sorts by its requester's
    # position; ambiguous or unmatched ids keep the execution's own position.
    anchors: list[int] = []
    for index, span in enumerate(spans):
        anchor = index
        if span.operation_name in TOOL_EXECUTION_OPS and span.tool_call_id:
            origins = requesters.get((span.trace_id, span.tool_call_id), set())
            if len(origins) == 1:
                anchor = next(iter(origins))
        anchors.append(anchor)

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
