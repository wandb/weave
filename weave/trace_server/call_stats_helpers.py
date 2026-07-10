import datetime
from typing import Any

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import InvalidRequest


def validate_call_stats_range(start: datetime.datetime, end: datetime.datetime) -> None:
    """Validate the time range for call stats requests.

    Args:
        start: Inclusive range start.
        end: Inclusive range end.

    Raises:
        InvalidRequest: If the range is invalid or too large.

    Examples:
        >>> start = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
        >>> end = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc)
        >>> validate_call_stats_range(start, end)
    """
    if end < start:
        raise InvalidRequest("CallStatsReq end must be after start")
    if end - start > tsi.MAX_CALL_STATS_RANGE:
        raise InvalidRequest(
            f"CallStatsReq date range cannot exceed {tsi.MAX_CALL_STATS_RANGE_DAYS} days"
        )


def split_usage_metrics(
    usage_metrics: list[tsi.UsageMetricSpec] | None,
) -> tuple[list[tsi.UsageMetricSpec], set[str]]:
    """Split usage metrics into token metrics and requested cost metrics.

    Args:
        usage_metrics: Usage metrics from the request.

    Returns:
        Token metric specs plus the set of requested cost metric names.

    Examples:
        >>> metrics = [
        ...     tsi.UsageMetricSpec(
        ...         metric="input_cost",
        ...         aggregations=[tsi.AggregationType.SUM],
        ...     )
        ... ]
        >>> token_metrics, cost_metrics = split_usage_metrics(metrics)
        >>> "input_cost" in cost_metrics
        True
    """
    cost_metrics = {"input_cost", "output_cost", "total_cost"}
    requested_cost_metrics: set[str] = set()
    token_metrics: list[tsi.UsageMetricSpec] = []

    if not usage_metrics:
        return token_metrics, requested_cost_metrics

    for metric_spec in usage_metrics:
        if metric_spec.metric in cost_metrics:
            requested_cost_metrics.add(metric_spec.metric)
        else:
            token_metrics.append(metric_spec)

    if requested_cost_metrics:

        def ensure_sum_metric(metric: tsi.UsageMetric) -> None:
            for index, metric_spec in enumerate(token_metrics):
                if metric_spec.metric == metric:
                    if tsi.AggregationType.SUM not in metric_spec.aggregations:
                        token_metrics[index] = metric_spec.model_copy(
                            update={
                                "aggregations": [
                                    *metric_spec.aggregations,
                                    tsi.AggregationType.SUM,
                                ]
                            }
                        )
                    return
            token_metrics.append(
                tsi.UsageMetricSpec(
                    metric=metric,
                    aggregations=[tsi.AggregationType.SUM],
                )
            )

        needs_input = (
            "input_cost" in requested_cost_metrics
            or "total_cost" in requested_cost_metrics
        )
        if needs_input:
            ensure_sum_metric("input_tokens")
        needs_output = (
            "output_cost" in requested_cost_metrics
            or "total_cost" in requested_cost_metrics
        )
        if needs_output:
            ensure_sum_metric("output_tokens")

    return token_metrics, requested_cost_metrics


def rows_to_bucket_dicts(
    columns: list[str], rows: list[tuple[Any, ...]]
) -> list[dict[str, Any]]:
    """Convert query rows into bucket dictionaries.

    Args:
        columns: Column names returned by the query.
        rows: Row tuples returned by the query.

    Returns:
        Buckets formatted as dictionaries with ISO timestamps.

    Examples:
        >>> rows = [
        ...     (datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc), 1)
        ... ]
        >>> rows_to_bucket_dicts(["timestamp", "count"], rows)
        [{'timestamp': '2024-01-01T00:00:00+00:00', 'count': 1}]
    """
    buckets: list[dict[str, Any]] = []
    for tup in rows:
        row: dict[str, Any] = {}
        for idx, col in enumerate(columns):
            val = tup[idx] if idx < len(tup) else None
            if col == "timestamp" and isinstance(val, datetime.datetime):
                row[col] = val.isoformat()
            else:
                row[col] = val
        buckets.append(row)
    return buckets
