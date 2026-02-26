from __future__ import annotations

import dataclasses
from collections import deque
from collections.abc import Iterable
from typing import Any

import ddtrace

from weave.trace_server import trace_server_interface as tsi


@dataclasses.dataclass(frozen=True)
class UsageCall:
    id: str
    parent_id: str | None
    summary: dict[str, Any] | None


@ddtrace.tracer.wrap(name="usage_utils.aggregate_usage_with_descendants")
def aggregate_usage_with_descendants(
    calls: Iterable[UsageCall],
    include_costs: bool,
) -> dict[str, dict[str, tsi.LLMAggregatedUsage]]:
    """Aggregate usage per call, including all descendant usage.

    Uses a bottom-up traversal to avoid recursion limits.
    """
    # This materializes the calls into memory, which is not ideal for
    # large traces, but is necessary for this approach.
    # Reuse the input list directly when possible to avoid an extra copy.
    if isinstance(calls, list):
        calls_list = calls
    else:
        calls_list = list(calls)
    if not calls_list:
        return {}

    # Index calls for O(1) parent lookups and child counting.
    calls_by_id = {call.id: call for call in calls_list}
    children_remaining = dict.fromkeys(calls_by_id, 0)
    parent_by_id: dict[str, str] = {}

    # Count in-scope children and record each call's parent.
    for call in calls_list:
        parent_id = call.parent_id
        if parent_id and parent_id in calls_by_id:
            children_remaining[parent_id] += 1
            parent_by_id[call.id] = parent_id

    # Seed each call's usage with its own summary data.
    aggregated_usage: dict[str, dict[str, tsi.LLMAggregatedUsage]] = {}
    for call in calls_list:
        aggregated_usage[call.id] = _extract_call_usage(call, include_costs)

    # Start from leaves (calls with no remaining children) for bottom-up merge.
    queue = deque(
        [call_id for call_id, count in children_remaining.items() if count == 0]
    )

    while queue:
        call_id = queue.popleft()
        # Merge this call's usage into its parent once all children are merged.
        parent_id = parent_by_id.get(call_id)
        if parent_id is None:
            continue
        _merge_usage(
            aggregated_usage[parent_id], aggregated_usage[call_id], include_costs
        )
        # Decrement child count and enqueue parent when it becomes a leaf.
        children_remaining[parent_id] -= 1
        if children_remaining[parent_id] == 0:
            queue.append(parent_id)

    return aggregated_usage


def _extract_call_usage(
    call: UsageCall,
    include_costs: bool,
) -> dict[str, tsi.LLMAggregatedUsage]:
    # Pull the usage map out of the call summary (if present).
    summary = call.summary or {}
    usage_map = summary.get("usage")
    if not isinstance(usage_map, dict):
        return {}

    # Optional cost data lives in a separate "weave" summary block.
    costs_map: dict[str, Any] = {}
    if include_costs:
        weave_summary = summary.get("weave")
        if isinstance(weave_summary, dict):
            costs_map = weave_summary.get("costs") or {}

    # Build per-model usage objects, skipping malformed entries.
    aggregated: dict[str, tsi.LLMAggregatedUsage] = {}
    for model_name, usage in usage_map.items():
        if not isinstance(usage, dict):
            continue
        # Normalize token counts across multiple field names.
        prompt_tokens = _safe_int(usage.get("prompt_tokens")) + _safe_int(
            usage.get("input_tokens")
        )
        completion_tokens = _safe_int(usage.get("completion_tokens")) + _safe_int(
            usage.get("output_tokens")
        )
        requests = _safe_int(usage.get("requests"))
        total_tokens = _safe_int(usage.get("total_tokens"))
        if total_tokens == 0:
            total_tokens = prompt_tokens + completion_tokens

        # Costs are optional and only populated when requested.
        prompt_cost: float | None = None
        completion_cost: float | None = None
        if include_costs:
            prompt_cost = 0.0
            completion_cost = 0.0
            cost_entry = (
                costs_map.get(model_name) if isinstance(costs_map, dict) else {}
            )
            if isinstance(cost_entry, dict):
                prompt_cost = _safe_float(cost_entry.get("prompt_tokens_total_cost"))
                completion_cost = _safe_float(
                    cost_entry.get("completion_tokens_total_cost")
                )

        # Only store entries that contain any usage (or cost when requested).
        usage_obj = tsi.LLMAggregatedUsage(
            requests=requests,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            prompt_tokens_total_cost=prompt_cost,
            completion_tokens_total_cost=completion_cost,
        )

        if _has_usage(usage_obj, include_costs):
            aggregated[str(model_name)] = usage_obj

    return aggregated


def _merge_usage(
    target: dict[str, tsi.LLMAggregatedUsage],
    source: dict[str, tsi.LLMAggregatedUsage],
    include_costs: bool,
) -> None:
    for model_name, usage in source.items():
        existing = target.get(model_name)
        if existing is None:
            target[model_name] = usage.model_copy(deep=True)
        else:
            existing.requests += usage.requests
            existing.prompt_tokens += usage.prompt_tokens
            existing.completion_tokens += usage.completion_tokens
            existing.total_tokens += usage.total_tokens

            if include_costs:
                existing.prompt_tokens_total_cost = (
                    existing.prompt_tokens_total_cost or 0.0
                ) + (usage.prompt_tokens_total_cost or 0.0)
                existing.completion_tokens_total_cost = (
                    existing.completion_tokens_total_cost or 0.0
                ) + (usage.completion_tokens_total_cost or 0.0)


def _safe_int(value: Any) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _has_usage(usage: tsi.LLMAggregatedUsage, include_costs: bool) -> bool:
    if (
        usage.requests
        or usage.prompt_tokens
        or usage.completion_tokens
        or usage.total_tokens
    ):
        return True
    if include_costs:
        return bool(
            (usage.prompt_tokens_total_cost or 0.0)
            or (usage.completion_tokens_total_cost or 0.0)
        )
    return False
