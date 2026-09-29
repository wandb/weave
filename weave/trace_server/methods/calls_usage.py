from collections.abc import Callable, Iterator

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server import usage_utils
from weave.trace_server.errors import InvalidRequest, RequestTooLarge


def calls_usage(
    query_calls: Callable[[tsi.CallsQueryReq], Iterator[tsi.CallSchema]],
    req: tsi.CallsUsageReq,
) -> tsi.CallsUsageRes:
    """Roll up complete traces in batches bounded by the request limit."""
    if req.limit < 1:
        raise InvalidRequest("Usage aggregation limit must be positive")

    root_usage: dict[str, dict[str, tsi.LLMAggregatedUsage]] = {
        call_id: {} for call_id in req.call_ids
    }
    if not req.call_ids:
        return tsi.CallsUsageRes(call_usage=root_usage)

    root_calls = query_calls(
        tsi.CallsQueryReq(
            project_id=req.project_id,
            filter=tsi.CallsFilter(call_ids=req.call_ids),
            columns=["trace_id"],
            limit=len(req.call_ids),
        )
    )
    trace_ids = sorted({call.trace_id for call in root_calls})
    pending_batches = [trace_ids] if trace_ids else []
    unfinished_call_ids: set[str] = set()

    while pending_batches:
        batch = pending_batches.pop()
        result = _aggregate_trace_batch(query_calls, req, batch)
        if result is None:
            if len(batch) == 1:
                raise RequestTooLarge(
                    f"Cannot compute complete usage: a single trace exceeds "
                    f"the {req.limit}-call aggregation limit. Increase limit and retry."
                )

            midpoint = len(batch) // 2
            pending_batches.extend([batch[:midpoint], batch[midpoint:]])
            continue

        for call_id in root_usage.keys() & result.call_usage.keys():
            root_usage[call_id] = result.call_usage[call_id]
        unfinished_call_ids.update(result.unfinished_call_ids)
        del result

    response = tsi.CallsUsageRes(
        call_usage=root_usage,
        unfinished_call_ids=sorted(unfinished_call_ids),
    )

    return response


def _aggregate_trace_batch(
    query_calls: Callable[[tsi.CallsQueryReq], Iterator[tsi.CallSchema]],
    req: tsi.CallsUsageReq,
    trace_ids: list[str],
) -> tsi.TraceUsageRes | None:
    """Return complete usage, or None when the batch exceeds the limit."""
    calls = query_calls(
        tsi.CallsQueryReq(
            project_id=req.project_id,
            filter=tsi.CallsFilter(trace_ids=trace_ids),
            columns=["id", "parent_id", "summary"],
            include_costs=req.include_costs,
            limit=req.limit + 1,
        )
    )
    usage_calls: list[usage_utils.UsageCall] = []
    unfinished_call_ids: list[str] = []

    for call in calls:
        if len(usage_calls) == req.limit:
            return None

        usage_calls.append(
            usage_utils.UsageCall(
                id=call.id,
                parent_id=call.parent_id,
                summary=dict(call.summary) if call.summary is not None else None,
            )
        )
        if call.ended_at is None:
            unfinished_call_ids.append(call.id)

    aggregated_usage = usage_utils.aggregate_usage_with_descendants(
        usage_calls, req.include_costs
    )
    result = tsi.TraceUsageRes(
        call_usage=aggregated_usage, unfinished_call_ids=unfinished_call_ids
    )

    return result
