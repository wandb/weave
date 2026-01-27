"""Shared utilities for computing usage metrics across trace server implementations.

This module provides common functions for extracting, merging, and aggregating
LLM usage metrics from call summaries. Used by both ClickHouse and SQLite
implementations.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from weave.trace_server import trace_server_interface as tsi

if TYPE_CHECKING:
    from collections.abc import Sequence


# Default limit for usage queries. Set high to allow most use cases while
# providing a safety net against unbounded memory usage. Callers querying
# very large datasets should consider pagination or streaming approaches.
DEFAULT_USAGE_LIMIT = 100_000


def extract_usage_from_call(
    call: tsi.CallSchema, include_costs: bool
) -> dict[str, tsi.LLMAggregatedUsage]:
    """Extract usage metrics from a call's summary.

    Args:
        call: The call to extract usage from.
        include_costs: Whether to include cost data from weave.costs.

    Returns:
        A dict mapping LLM IDs to their aggregated usage metrics.
    """
    result: dict[str, tsi.LLMAggregatedUsage] = {}

    if call.summary is None:
        return result

    # Usage is in summary.usage as {llm_id: LLMUsageSchema}
    usage = call.summary.get("usage", {})
    if not usage:
        return result

    for llm_id, llm_usage in usage.items():
        if not isinstance(llm_usage, dict):
            continue

        # Handle both prompt_tokens/completion_tokens and input_tokens/output_tokens
        extracted = tsi.LLMAggregatedUsage(
            requests=llm_usage.get("requests", 0) or 0,
            prompt_tokens=(llm_usage.get("prompt_tokens", 0) or 0)
            + (llm_usage.get("input_tokens", 0) or 0),
            completion_tokens=(llm_usage.get("completion_tokens", 0) or 0)
            + (llm_usage.get("output_tokens", 0) or 0),
            total_tokens=llm_usage.get("total_tokens", 0) or 0,
        )

        result[llm_id] = extracted

    # If costs are requested, extract them from weave.costs
    if include_costs:
        weave_summary = call.summary.get("weave", {})
        costs = weave_summary.get("costs", {}) if weave_summary else {}

        for llm_id, cost_data in (costs or {}).items():
            if not isinstance(cost_data, dict):
                continue

            if llm_id in result:
                result[llm_id].prompt_tokens_total_cost = cost_data.get(
                    "prompt_tokens_total_cost"
                )
                result[llm_id].completion_tokens_total_cost = cost_data.get(
                    "completion_tokens_total_cost"
                )
            else:
                # Cost data for an LLM not in usage (shouldn't normally happen)
                result[llm_id] = tsi.LLMAggregatedUsage(
                    prompt_tokens_total_cost=cost_data.get("prompt_tokens_total_cost"),
                    completion_tokens_total_cost=cost_data.get(
                        "completion_tokens_total_cost"
                    ),
                )

    return result


def merge_usage(
    target: dict[str, tsi.LLMAggregatedUsage],
    source: dict[str, tsi.LLMAggregatedUsage],
) -> None:
    """Merge source usage into target (mutates target).

    Args:
        target: The dict to merge into.
        source: The dict to merge from.
    """
    for llm_id, source_usage in source.items():
        if llm_id not in target:
            target[llm_id] = tsi.LLMAggregatedUsage()

        target_usage = target[llm_id]
        target_usage.requests += source_usage.requests
        target_usage.prompt_tokens += source_usage.prompt_tokens
        target_usage.completion_tokens += source_usage.completion_tokens
        target_usage.total_tokens += source_usage.total_tokens

        if source_usage.prompt_tokens_total_cost is not None:
            if target_usage.prompt_tokens_total_cost is None:
                target_usage.prompt_tokens_total_cost = 0.0
            target_usage.prompt_tokens_total_cost += source_usage.prompt_tokens_total_cost

        if source_usage.completion_tokens_total_cost is not None:
            if target_usage.completion_tokens_total_cost is None:
                target_usage.completion_tokens_total_cost = 0.0
            target_usage.completion_tokens_total_cost += (
                source_usage.completion_tokens_total_cost
            )


def copy_usage(
    usage: dict[str, tsi.LLMAggregatedUsage],
) -> dict[str, tsi.LLMAggregatedUsage]:
    """Create a deep copy of usage data to avoid mutation issues.

    Args:
        usage: The usage dict to copy.

    Returns:
        A new dict with copied LLMAggregatedUsage instances.
    """
    result: dict[str, tsi.LLMAggregatedUsage] = {}
    for llm_id, u in usage.items():
        result[llm_id] = tsi.LLMAggregatedUsage(
            requests=u.requests,
            prompt_tokens=u.prompt_tokens,
            completion_tokens=u.completion_tokens,
            total_tokens=u.total_tokens,
            prompt_tokens_total_cost=u.prompt_tokens_total_cost,
            completion_tokens_total_cost=u.completion_tokens_total_cost,
        )
    return result


def aggregate_usage_with_descendants(
    calls: Sequence[tsi.CallSchema],
    include_costs: bool,
) -> dict[str, dict[str, tsi.LLMAggregatedUsage]]:
    """Compute per-call usage with descendant rollup using iterative topological sort.

    Each call's usage = its own metrics + sum of all descendants' metrics.
    This uses an iterative bottom-up approach (reverse topological order) to avoid
    recursion depth limits for deep call hierarchies.

    Args:
        calls: The calls to compute usage for.
        include_costs: Whether to include cost data.

    Returns:
        A dict mapping call_id to its aggregated usage (own + all descendants).
    """
    if not calls:
        return {}

    # Build call ID to call mapping
    call_map = {call.id: call for call in calls}

    # Build parent-to-children mapping
    children_map: dict[str, list[str]] = defaultdict(list)
    for call in calls:
        if call.parent_id is not None:
            children_map[call.parent_id].append(call.id)

    # Extract own usage for each call
    own_usage: dict[str, dict[str, tsi.LLMAggregatedUsage]] = {}
    for call in calls:
        own_usage[call.id] = extract_usage_from_call(call, include_costs)

    # Count children within our result set for each call
    # (only count children that are in call_map)
    child_count: dict[str, int] = {call_id: 0 for call_id in call_map}
    for call_id in call_map:
        for child_id in children_map.get(call_id, []):
            if child_id in call_map:
                child_count[call_id] += 1

    # Aggregated usage (own + descendants)
    aggregated_usage: dict[str, dict[str, tsi.LLMAggregatedUsage]] = {}

    # Start with leaf nodes (no children in our result set)
    queue = [call_id for call_id, count in child_count.items() if count == 0]

    while queue:
        call_id = queue.pop()

        # Start with own usage
        result = copy_usage(own_usage.get(call_id, {}))

        # Add all children's aggregated usage (children are already processed)
        for child_id in children_map.get(call_id, []):
            if child_id in aggregated_usage:
                merge_usage(result, aggregated_usage[child_id])

        aggregated_usage[call_id] = result

        # Update parent's child count and add to queue if all children processed
        call = call_map[call_id]
        if call.parent_id is not None and call.parent_id in child_count:
            child_count[call.parent_id] -= 1
            if child_count[call.parent_id] == 0:
                queue.append(call.parent_id)

    return aggregated_usage
