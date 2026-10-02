"""Order sibling spans by recorded tool dependencies before clock time."""

import heapq

from weave.trace_server.agents.constants import OP_EXECUTE_TOOL, OP_INVOKE_AGENT
from weave.trace_server.agents.model_tool_calls import parse_content_parts
from weave.trace_server.agents.schema import NormalizedMessage
from weave.trace_server.agents.types import AgentSpanSchema


def causal_span_order(spans: list[AgentSpanSchema]) -> list[int]:
    """Return stable topological indexes, retaining input order on conflicting evidence."""
    executions: dict[tuple[str, str, str], list[int]] = {}
    producers: dict[tuple[str, str, str], list[int]] = {}
    for index, span in enumerate(spans):
        if span.operation_name in {OP_EXECUTE_TOOL, OP_INVOKE_AGENT}:
            if span.tool_call_id:
                key = (span.project_id, span.trace_id, span.tool_call_id)
                executions.setdefault(key, []).append(index)
            continue

        for call_id in _part_ids(span.output_messages, "assistant", "tool_call"):
            key = (span.project_id, span.trace_id, call_id)
            producers.setdefault(key, []).append(index)

    predecessors: list[set[int]] = [set() for _ in spans]
    for key, indexes in executions.items():
        origins = producers.get(key, [])
        if len(indexes) == 1 and len(origins) == 1:
            predecessors[indexes[0]].add(origins[0])

    for index, span in enumerate(spans):
        for call_id in _part_ids(span.input_messages, "tool", "tool_call_response"):
            key = (span.project_id, span.trace_id, call_id)
            origins = executions.get(key, producers.get(key, []))
            if len(origins) == 1 and origins[0] != index:
                predecessors[index].add(origins[0])

    successors: list[list[int]] = [[] for _ in spans]
    ready: list[int] = []
    for index, dependencies in enumerate(predecessors):
        if not dependencies:
            heapq.heappush(ready, index)
        for predecessor in dependencies:
            successors[predecessor].append(index)

    ordered: list[int] = []
    while ready:
        index = heapq.heappop(ready)
        ordered.append(index)
        for successor in successors[index]:
            predecessors[successor].remove(index)
            if not predecessors[successor]:
                heapq.heappush(ready, successor)

    if len(ordered) != len(spans):
        return list(range(len(spans)))

    return ordered


def _part_ids(messages: list[NormalizedMessage], role: str, kind: str) -> set[str]:
    ids: set[str] = set()
    for message in messages:
        if message.role != role:
            continue

        for part in parse_content_parts(message.content):
            call_id = part.get("id")
            if part.get("type") == kind and isinstance(call_id, str) and call_id:
                ids.add(call_id)

    return ids
