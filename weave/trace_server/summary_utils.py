from __future__ import annotations

import dataclasses
from collections import deque
from collections.abc import Iterable
from typing import Any

import ddtrace

from weave.utils.dict_utils import sum_dict_leaves

SERVER_SIDE_ROLLUP_ATTR = "server-side-rollup"


@dataclasses.dataclass(frozen=True)
class SummaryCall:
    id: str
    parent_id: str | None
    summary: dict[str, Any] | None
    attributes: dict[str, Any] | None = None


def wants_server_side_rollup(attributes: dict[str, Any] | None) -> bool:
    """Returns True if the call opted into server-side summary rollup."""
    if not attributes:
        return False
    weave_attrs = attributes.get("weave")
    if not isinstance(weave_attrs, dict):
        return False
    return bool(weave_attrs.get(SERVER_SIDE_ROLLUP_ATTR))


@ddtrace.tracer.wrap(name="summary_utils.aggregate_summary_with_descendants")
def aggregate_summary_with_descendants(
    calls: Iterable[SummaryCall],
) -> dict[str, dict[str, Any]]:
    """Bottom-up rollup of call summaries into their parents.

    Matches the client-side ``sum_dict_leaves`` semantics: numeric leaves are
    summed, non-numeric leaves are collected into lists, and nested dicts are
    merged recursively. Only calls that opted into server-side rollup
    (``attributes["weave"]["server-side-rollup"] is True``) receive a
    rolled-up result; other calls' summaries are returned unchanged.

    Returns a mapping of call_id -> summary dict (rolled-up or original).
    """
    calls_list = list(calls) if not isinstance(calls, list) else calls
    if not calls_list:
        return {}

    calls_by_id = {call.id: call for call in calls_list}
    children_by_id: dict[str, list[str]] = {call.id: [] for call in calls_list}
    in_degree: dict[str, int] = dict.fromkeys(calls_by_id, 0)

    for call in calls_list:
        parent_id = call.parent_id
        if parent_id and parent_id in calls_by_id:
            children_by_id[parent_id].append(call.id)
            in_degree[call.id] = 1

    # Bottom-up traversal: process leaves first, parents after all children.
    remaining = {cid: len(children_by_id[cid]) for cid in calls_by_id}
    aggregated: dict[str, dict[str, Any]] = {
        cid: dict(calls_by_id[cid].summary or {}) for cid in calls_by_id
    }

    queue = deque(cid for cid, n in remaining.items() if n == 0)
    order: list[str] = []
    while queue:
        cid = queue.popleft()
        order.append(cid)
        parent_id = calls_by_id[cid].parent_id
        if parent_id and parent_id in calls_by_id:
            remaining[parent_id] -= 1
            if remaining[parent_id] == 0:
                queue.append(parent_id)

    # Now roll up in reverse topological order so each parent sees fully
    # aggregated children.
    for cid in order:
        children = children_by_id[cid]
        if not children:
            continue
        # Combine this call's own summary with all (already-rolled-up) children.
        combined = sum_dict_leaves(
            [aggregated[cid]] + [aggregated[child_id] for child_id in children]
        )
        aggregated[cid] = combined

    result: dict[str, dict[str, Any]] = {}
    for call in calls_list:
        if wants_server_side_rollup(call.attributes):
            result[call.id] = aggregated[call.id]
        else:
            result[call.id] = dict(call.summary or {})
    return result
