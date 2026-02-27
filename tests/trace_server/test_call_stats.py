"""Integration tests for call_stats endpoint.

These tests validate the full end-to-end flow of the call statistics feature by:
1. Inserting calls with known usage data via call_start/call_end
2. Querying the call_stats endpoint
3. Verifying aggregated metrics match expected values

Note: call_stats is only implemented in ClickHouseTraceServer, so these tests
skip when running against SQLite.
"""

import datetime
import uuid

import pytest
from pydantic import ValidationError

from tests.trace.util import client_is_sqlite
from weave.trace import weave_client
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.trace_server_interface import (
    AggregationType,
    CallMetricSpec,
    CallsFilter,
    CallStatsReq,
    UsageMetricSpec,
)


def skip_if_sqlite(client: weave_client.WeaveClient):
    """Skip test if running against SQLite (call_stats not implemented)."""
    if client_is_sqlite(client):
        pytest.skip("call_stats is only implemented in ClickHouse")


def force_merge_calls(client: weave_client.WeaveClient):
    """Force ClickHouse to merge calls_merged table for test consistency.

    ClickHouse merges ReplacingMergeTree rows asynchronously. In tests, we write
    and immediately query, so rows may not be merged yet. This forces a merge.
    """
    if client_is_sqlite(client):
        return
    # Access the underlying ClickHouse client
    ch_client = client.server._next_trace_server.ch_client
    ch_client.command("OPTIMIZE TABLE calls_merged FINAL")


def create_call_with_usage(
    client: weave_client.WeaveClient,
    op_name: str,
    usage: dict,
    started_at: datetime.datetime | None = None,
) -> str:
    """Helper to create a call with usage data in the summary."""
    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    project_id = client._project_id()

    if started_at is None:
        started_at = datetime.datetime.now(datetime.timezone.utc)

    ended_at = started_at + datetime.timedelta(seconds=1)

    client.server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=trace_id,
                started_at=started_at,
                op_name=op_name,
                attributes={},
                inputs={},
            )
        )
    )

    client.server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                ended_at=ended_at,
                exception=None,
                output=None,
                summary={"usage": usage},
            )
        )
    )

    return call_id


def test_call_stats_usage_sum_aggregation(client: weave_client.WeaveClient):
    """Test basic SUM aggregation across multiple calls with known usage data."""
    skip_if_sqlite(client)

    project_id = client._project_id()
    model_name = "gpt-4o-test"
    op_name = f"weave:///{project_id}/op/test_op:abc123"

    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now - datetime.timedelta(minutes=30)

    usage_data = [
        {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "requests": 1,
        },
        {
            "prompt_tokens": 200,
            "completion_tokens": 100,
            "total_tokens": 300,
            "requests": 1,
        },
        {
            "prompt_tokens": 150,
            "completion_tokens": 75,
            "total_tokens": 225,
            "requests": 1,
        },
    ]

    for i, usage in enumerate(usage_data):
        call_time = start_time + datetime.timedelta(minutes=i)
        create_call_with_usage(
            client,
            op_name,
            {model_name: usage},
            started_at=call_time,
        )

    force_merge_calls(client)
    result = client.server.call_stats(
        CallStatsReq(
            project_id=project_id,
            start=start_time - datetime.timedelta(minutes=1),
            end=now + datetime.timedelta(minutes=1),
            granularity=3600,
            usage_metrics=[
                UsageMetricSpec(
                    metric="input_tokens",
                    aggregations=[AggregationType.SUM],
                ),
                UsageMetricSpec(
                    metric="total_tokens",
                    aggregations=[AggregationType.SUM],
                ),
            ],
        )
    )

    model_buckets = [b for b in result.usage_buckets if b.get("model") == model_name]
    assert len(model_buckets) > 0, f"Expected buckets for model {model_name}"

    total_input_tokens = sum(b.get("sum_input_tokens", 0) for b in model_buckets)
    total_total_tokens = sum(b.get("sum_total_tokens", 0) for b in model_buckets)

    expected_input_tokens = sum(u["prompt_tokens"] for u in usage_data)
    expected_total_tokens = sum(u["total_tokens"] for u in usage_data)

    assert total_input_tokens == expected_input_tokens, (
        f"Expected sum_input_tokens={expected_input_tokens}, got {total_input_tokens}"
    )
    assert total_total_tokens == expected_total_tokens, (
        f"Expected sum_total_tokens={expected_total_tokens}, got {total_total_tokens}"
    )


def test_compute_costs_for_buckets_uses_cached_tokens() -> None:
    """Input cost should apply cached tokens at cached token rate."""

    class StubServer:
        def _get_prices_for_models(  # noqa: N802 (match production method name)
            self, models: set[str], project_id: str
        ) -> dict[str, dict[str, float]]:
            return {
                model: {
                    "prompt_token_cost": 2.0,
                    "cached_prompt_token_cost": 0.5,
                    "completion_token_cost": 1.0,
                }
                for model in models
            }

    usage_buckets: list[dict[str, object]] = [
        {
            "model": "test-model",
            "sum_input_tokens": 100,
            "sum_output_tokens": 10,
            "sum_cached_tokens": 90,
        },
        {
            "model": "test-model",
            "sum_input_tokens": 100,
            "sum_output_tokens": 0,
            "sum_cached_tokens": 0,
        },
    ]

    ClickHouseTraceServer._compute_costs_for_buckets(  # type: ignore[misc]
        StubServer(),
        usage_buckets,
        "entity/project",
        {"input_cost", "output_cost", "total_cost"},
    )

    # Bucket 0: 10 uncached at 2.0 + 90 cached at 0.5 = 65.
    assert usage_buckets[0]["sum_input_cost"] == pytest.approx(65.0)
    # Bucket 1: 100 uncached at 2.0.
    assert usage_buckets[1]["sum_input_cost"] == pytest.approx(200.0)

    # Output cost remains unchanged and contributes to total cost.
    assert usage_buckets[0]["sum_output_cost"] == pytest.approx(10.0)
    assert usage_buckets[0]["sum_total_cost"] == pytest.approx(75.0)


def test_call_stats_date_range_limit_validation():
    """Reject CallStatsReq with a date range exceeding 31 days."""
    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now - datetime.timedelta(days=32)

    with pytest.raises(ValidationError):
        tsi.CallStatsReq(
            project_id="entity/project",
            start=start_time,
            end=now,
            granularity=3600,
            usage_metrics=[tsi.UsageMetricSpec(metric="total_tokens")],
        )


def test_call_stats_multiple_models(client: weave_client.WeaveClient):
    """Test that different models are tracked and aggregated separately."""
    skip_if_sqlite(client)

    project_id = client._project_id()
    op_name = f"weave:///{project_id}/op/multi_model_op:def456"

    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now - datetime.timedelta(minutes=30)

    model_usage = {
        "gpt-4o": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "requests": 1,
        },
        "claude-3": {
            "prompt_tokens": 200,
            "completion_tokens": 100,
            "total_tokens": 300,
            "requests": 1,
        },
        "gemini-pro": {
            "prompt_tokens": 300,
            "completion_tokens": 150,
            "total_tokens": 450,
            "requests": 1,
        },
    }

    for i, (model, usage) in enumerate(model_usage.items()):
        call_time = start_time + datetime.timedelta(minutes=i)
        create_call_with_usage(
            client,
            op_name,
            {model: usage},
            started_at=call_time,
        )

    force_merge_calls(client)
    result = client.server.call_stats(
        CallStatsReq(
            project_id=project_id,
            start=start_time - datetime.timedelta(minutes=1),
            end=now + datetime.timedelta(minutes=1),
            granularity=3600,
            usage_metrics=[
                UsageMetricSpec(
                    metric="input_tokens",
                    aggregations=[AggregationType.SUM],
                ),
            ],
        )
    )

    for model, usage in model_usage.items():
        model_buckets = [b for b in result.usage_buckets if b.get("model") == model]
        assert len(model_buckets) > 0, f"Expected buckets for model {model}"

        total_input = sum(b.get("sum_input_tokens", 0) for b in model_buckets)
        assert total_input == usage["prompt_tokens"], (
            f"Model {model}: expected {usage['prompt_tokens']}, got {total_input}"
        )


def test_call_stats_all_aggregation_types(client: weave_client.WeaveClient):
    """Test SUM, AVG, MIN, MAX, COUNT aggregations compute correctly."""
    skip_if_sqlite(client)

    project_id = client._project_id()
    model_name = "gpt-4o-agg-test"
    op_name = f"weave:///{project_id}/op/agg_test_op:ghi789"

    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now - datetime.timedelta(minutes=30)

    token_values = [10, 20, 30, 40, 50]

    for i, tokens in enumerate(token_values):
        call_time = start_time + datetime.timedelta(minutes=i)
        create_call_with_usage(
            client,
            op_name,
            {
                model_name: {
                    "prompt_tokens": tokens,
                    "total_tokens": tokens,
                    "requests": 1,
                }
            },
            started_at=call_time,
        )

    force_merge_calls(client)
    result = client.server.call_stats(
        CallStatsReq(
            project_id=project_id,
            start=start_time - datetime.timedelta(minutes=1),
            end=now + datetime.timedelta(minutes=1),
            granularity=3600,
            usage_metrics=[
                UsageMetricSpec(
                    metric="input_tokens",
                    aggregations=[
                        AggregationType.SUM,
                        AggregationType.AVG,
                        AggregationType.MIN,
                        AggregationType.MAX,
                        AggregationType.COUNT,
                    ],
                ),
            ],
        )
    )

    model_buckets = [b for b in result.usage_buckets if b.get("model") == model_name]
    assert len(model_buckets) > 0, f"Expected buckets for model {model_name}"

    total_sum = sum(b.get("sum_input_tokens", 0) for b in model_buckets)
    total_count = sum(b.get("count_input_tokens", 0) for b in model_buckets)

    all_mins = [
        b.get("min_input_tokens")
        for b in model_buckets
        if b.get("min_input_tokens") is not None
    ]
    all_maxs = [
        b.get("max_input_tokens")
        for b in model_buckets
        if b.get("max_input_tokens") is not None
    ]

    expected_sum = sum(token_values)
    expected_min = min(token_values)
    expected_max = max(token_values)
    expected_count = len(token_values)
    expected_avg = expected_sum / expected_count

    assert total_sum == expected_sum, f"SUM: expected {expected_sum}, got {total_sum}"
    assert total_count == expected_count, (
        f"COUNT: expected {expected_count}, got {total_count}"
    )
    assert min(all_mins) == expected_min, (
        f"MIN: expected {expected_min}, got {min(all_mins)}"
    )
    assert max(all_maxs) == expected_max, (
        f"MAX: expected {expected_max}, got {max(all_maxs)}"
    )

    total_avg_weighted = sum(
        b.get("avg_input_tokens", 0) * b.get("count", 1)
        for b in model_buckets
        if b.get("avg_input_tokens") is not None
    )
    total_weight = sum(
        b.get("count", 1)
        for b in model_buckets
        if b.get("avg_input_tokens") is not None
    )
    if total_weight > 0:
        computed_avg = total_avg_weighted / total_weight
        assert abs(computed_avg - expected_avg) < 0.01, (
            f"AVG: expected {expected_avg}, got {computed_avg}"
        )


def test_call_stats_percentiles(client: weave_client.WeaveClient):
    """Test percentile calculations (p50, p95, p99) with varied data."""
    skip_if_sqlite(client)

    project_id = client._project_id()
    model_name = "gpt-4o-pct-test"
    op_name = f"weave:///{project_id}/op/pct_test_op:jkl012"

    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now - datetime.timedelta(minutes=30)

    token_values = list(range(1, 101))

    for i, tokens in enumerate(token_values):
        call_time = start_time + datetime.timedelta(seconds=i)
        create_call_with_usage(
            client,
            op_name,
            {
                model_name: {
                    "prompt_tokens": tokens,
                    "total_tokens": tokens,
                    "requests": 1,
                }
            },
            started_at=call_time,
        )

    force_merge_calls(client)
    result = client.server.call_stats(
        CallStatsReq(
            project_id=project_id,
            start=start_time - datetime.timedelta(minutes=1),
            end=now + datetime.timedelta(minutes=1),
            granularity=3600,
            usage_metrics=[
                UsageMetricSpec(
                    metric="input_tokens",
                    aggregations=[],
                    percentiles=[50, 95, 99],
                ),
            ],
        )
    )

    model_buckets = [b for b in result.usage_buckets if b.get("model") == model_name]
    assert len(model_buckets) > 0, f"Expected buckets for model {model_name}"

    bucket = model_buckets[0]

    p50 = bucket.get("p50_input_tokens")
    p95 = bucket.get("p95_input_tokens")
    p99 = bucket.get("p99_input_tokens")

    assert p50 is not None, "p50 should be present"
    assert p95 is not None, "p95 should be present"
    assert p99 is not None, "p99 should be present"

    assert 25 <= p50 <= 75, f"p50 should be around 50, got {p50}"
    assert 85 <= p95 <= 100, f"p95 should be around 95, got {p95}"
    assert 90 <= p99 <= 100, f"p99 should be around 99, got {p99}"


def test_call_stats_time_buckets(client: weave_client.WeaveClient):
    """Test that calls are grouped into correct time buckets based on started_at."""
    skip_if_sqlite(client)

    project_id = client._project_id()
    model_name = "gpt-4o-bucket-test"
    op_name = f"weave:///{project_id}/op/bucket_test_op:mno345"

    now = datetime.datetime.now(datetime.timezone.utc)
    hour_ago = now - datetime.timedelta(hours=1)
    two_hours_ago = now - datetime.timedelta(hours=2)

    bucket1_usage = [
        {"prompt_tokens": 100, "total_tokens": 100, "requests": 1},
        {"prompt_tokens": 100, "total_tokens": 100, "requests": 1},
    ]
    bucket2_usage = [
        {"prompt_tokens": 200, "total_tokens": 200, "requests": 1},
    ]

    for i, usage in enumerate(bucket1_usage):
        call_time = two_hours_ago + datetime.timedelta(minutes=i * 5)
        create_call_with_usage(
            client,
            op_name,
            {model_name: usage},
            started_at=call_time,
        )

    for i, usage in enumerate(bucket2_usage):
        call_time = hour_ago + datetime.timedelta(minutes=i * 5)
        create_call_with_usage(
            client,
            op_name,
            {model_name: usage},
            started_at=call_time,
        )

    force_merge_calls(client)
    result = client.server.call_stats(
        CallStatsReq(
            project_id=project_id,
            start=two_hours_ago - datetime.timedelta(minutes=5),
            end=now + datetime.timedelta(minutes=5),
            granularity=3600,
            usage_metrics=[
                UsageMetricSpec(
                    metric="input_tokens",
                    aggregations=[AggregationType.SUM],
                ),
            ],
        )
    )

    model_buckets = [b for b in result.usage_buckets if b.get("model") == model_name]

    buckets_with_data = [b for b in model_buckets if b.get("sum_input_tokens", 0) > 0]

    assert len(buckets_with_data) >= 2, (
        f"Expected at least 2 buckets with data, got {len(buckets_with_data)}"
    )

    total_sum = sum(b.get("sum_input_tokens", 0) for b in model_buckets)
    expected_total = sum(u["prompt_tokens"] for u in bucket1_usage + bucket2_usage)
    assert total_sum == expected_total, (
        f"Expected total {expected_total}, got {total_sum}"
    )


def test_call_stats_op_names_filter(client: weave_client.WeaveClient):
    """Test op_names filter works correctly."""
    skip_if_sqlite(client)

    project_id = client._project_id()
    model_name = "gpt-4o-filter-test"

    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now - datetime.timedelta(minutes=30)

    op1 = f"weave:///{project_id}/op/openai.chat:v1"
    op2 = f"weave:///{project_id}/op/anthropic.messages:v1"

    create_call_with_usage(
        client,
        op1,
        {model_name: {"prompt_tokens": 100, "total_tokens": 100, "requests": 1}},
        started_at=start_time + datetime.timedelta(minutes=1),
    )

    create_call_with_usage(
        client,
        op2,
        {model_name: {"prompt_tokens": 200, "total_tokens": 200, "requests": 1}},
        started_at=start_time + datetime.timedelta(minutes=2),
    )

    force_merge_calls(client)
    result = client.server.call_stats(
        CallStatsReq(
            project_id=project_id,
            start=start_time - datetime.timedelta(minutes=1),
            end=now + datetime.timedelta(minutes=1),
            granularity=3600,
            usage_metrics=[
                UsageMetricSpec(
                    metric="input_tokens",
                    aggregations=[AggregationType.SUM],
                ),
            ],
            filter=CallsFilter(op_names=[op1]),
        )
    )
    model_buckets = [b for b in result.usage_buckets if b.get("model") == model_name]
    total_sum = sum(b.get("sum_input_tokens", 0) for b in model_buckets)

    assert total_sum == 100, f"Expected 100 (only op1), got {total_sum}"


def test_call_stats_trace_roots_only_filter(client: weave_client.WeaveClient):
    """Test trace_roots_only filter excludes child calls."""
    skip_if_sqlite(client)

    project_id = client._project_id()
    model_name = "gpt-4o-roots-test"

    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now - datetime.timedelta(minutes=30)

    # Create a root call
    root_call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())

    client.server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=root_call_id,
                trace_id=trace_id,
                started_at=start_time,
                op_name=f"weave:///{project_id}/op/root_op:v1",
                parent_id=None,
                attributes={},
                inputs={},
            )
        )
    )
    client.server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id=root_call_id,
                ended_at=start_time + datetime.timedelta(seconds=1),
                summary={
                    "usage": {model_name: {"prompt_tokens": 100, "total_tokens": 100}}
                },
            )
        )
    )

    # Create a child call
    child_call_id = str(uuid.uuid4())
    client.server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=child_call_id,
                trace_id=trace_id,
                started_at=start_time + datetime.timedelta(seconds=2),
                op_name=f"weave:///{project_id}/op/child_op:v1",
                parent_id=root_call_id,
                attributes={},
                inputs={},
            )
        )
    )
    client.server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id=child_call_id,
                ended_at=start_time + datetime.timedelta(seconds=3),
                summary={
                    "usage": {model_name: {"prompt_tokens": 200, "total_tokens": 200}}
                },
            )
        )
    )

    # Query with trace_roots_only=True should only get root call (100 tokens)
    force_merge_calls(client)
    result = client.server.call_stats(
        CallStatsReq(
            project_id=project_id,
            start=start_time - datetime.timedelta(minutes=1),
            end=now + datetime.timedelta(minutes=1),
            granularity=3600,
            usage_metrics=[
                UsageMetricSpec(
                    metric="input_tokens", aggregations=[AggregationType.SUM]
                ),
            ],
            filter=CallsFilter(trace_roots_only=True),
        )
    )

    model_buckets = [b for b in result.usage_buckets if b.get("model") == model_name]
    total_sum = sum(b.get("sum_input_tokens", 0) for b in model_buckets)

    assert total_sum == 100, f"Expected 100 (root only), got {total_sum}"


def test_call_stats_trace_ids_filter(client: weave_client.WeaveClient):
    """Test trace_ids filter limits to specific traces."""
    skip_if_sqlite(client)

    project_id = client._project_id()
    model_name = "gpt-4o-trace-filter-test"

    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now - datetime.timedelta(minutes=30)

    # Create two traces
    trace_id_1 = str(uuid.uuid4())
    trace_id_2 = str(uuid.uuid4())

    # Call in trace 1
    call_id_1 = str(uuid.uuid4())
    client.server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id_1,
                trace_id=trace_id_1,
                started_at=start_time,
                op_name=f"weave:///{project_id}/op/trace_test:v1",
                attributes={},
                inputs={},
            )
        )
    )
    client.server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id=call_id_1,
                ended_at=start_time + datetime.timedelta(seconds=1),
                summary={
                    "usage": {model_name: {"prompt_tokens": 100, "total_tokens": 100}}
                },
            )
        )
    )

    # Call in trace 2
    call_id_2 = str(uuid.uuid4())
    client.server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id_2,
                trace_id=trace_id_2,
                started_at=start_time + datetime.timedelta(minutes=1),
                op_name=f"weave:///{project_id}/op/trace_test:v1",
                attributes={},
                inputs={},
            )
        )
    )
    client.server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id=call_id_2,
                ended_at=start_time + datetime.timedelta(minutes=1, seconds=1),
                summary={
                    "usage": {model_name: {"prompt_tokens": 200, "total_tokens": 200}}
                },
            )
        )
    )

    # Query for only trace_1 should get 100 tokens
    force_merge_calls(client)
    result = client.server.call_stats(
        CallStatsReq(
            project_id=project_id,
            start=start_time - datetime.timedelta(minutes=1),
            end=now + datetime.timedelta(minutes=1),
            granularity=3600,
            usage_metrics=[
                UsageMetricSpec(
                    metric="input_tokens", aggregations=[AggregationType.SUM]
                ),
            ],
            filter=CallsFilter(trace_ids=[trace_id_1]),
        )
    )

    model_buckets = [b for b in result.usage_buckets if b.get("model") == model_name]
    total_sum = sum(b.get("sum_input_tokens", 0) for b in model_buckets)

    assert total_sum == 100, f"Expected 100 (trace_1 only), got {total_sum}"


def test_call_stats_call_metrics(client: weave_client.WeaveClient):
    """Test call-level metrics (latency, call_count, error_count)."""
    skip_if_sqlite(client)

    project_id = client._project_id()
    op_name = f"weave:///{project_id}/op/call_metrics_test:xyz123"

    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now - datetime.timedelta(minutes=30)

    call_id_1 = str(uuid.uuid4())
    call_id_2 = str(uuid.uuid4())
    call_id_3 = str(uuid.uuid4())
    trace_id_1 = str(uuid.uuid4())
    trace_id_2 = str(uuid.uuid4())
    trace_id_3 = str(uuid.uuid4())

    started_at_1 = start_time
    ended_at_1 = started_at_1 + datetime.timedelta(milliseconds=100)

    started_at_2 = start_time + datetime.timedelta(minutes=1)
    ended_at_2 = started_at_2 + datetime.timedelta(milliseconds=200)

    started_at_3 = start_time + datetime.timedelta(minutes=2)
    ended_at_3 = started_at_3 + datetime.timedelta(milliseconds=150)

    client.server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id_1,
                trace_id=trace_id_1,
                started_at=started_at_1,
                op_name=op_name,
                attributes={},
                inputs={},
            )
        )
    )
    client.server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id=call_id_1,
                ended_at=ended_at_1,
                summary={},
            )
        )
    )

    client.server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id_2,
                trace_id=trace_id_2,
                started_at=started_at_2,
                op_name=op_name,
                attributes={},
                inputs={},
            )
        )
    )
    client.server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id=call_id_2,
                ended_at=ended_at_2,
                summary={},
            )
        )
    )

    client.server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id_3,
                trace_id=trace_id_3,
                started_at=started_at_3,
                op_name=op_name,
                attributes={},
                inputs={},
            )
        )
    )
    client.server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id=call_id_3,
                ended_at=ended_at_3,
                exception="Test error",
                summary={},
            )
        )
    )

    force_merge_calls(client)
    result = client.server.call_stats(
        CallStatsReq(
            project_id=project_id,
            start=start_time - datetime.timedelta(minutes=1),
            end=now + datetime.timedelta(minutes=1),
            granularity=3600,
            call_metrics=[
                CallMetricSpec(
                    metric="latency_ms",
                    aggregations=[AggregationType.SUM, AggregationType.AVG],
                ),
                CallMetricSpec(
                    metric="call_count",
                    aggregations=[AggregationType.SUM],
                ),
                CallMetricSpec(
                    metric="error_count",
                    aggregations=[AggregationType.SUM],
                ),
            ],
            filter=CallsFilter(op_names=[op_name]),
        )
    )

    assert len(result.call_buckets) > 0, "Expected call buckets"
    # Verify bucket keys contain expected columns
    first_bucket = result.call_buckets[0]
    assert "timestamp" in first_bucket
    assert "sum_call_count" in first_bucket
    assert "sum_error_count" in first_bucket

    total_call_count = sum(b.get("sum_call_count", 0) for b in result.call_buckets)
    total_error_count = sum(b.get("sum_error_count", 0) for b in result.call_buckets)

    assert total_call_count == 3, f"Expected 3 calls, got {total_call_count}"
    assert total_error_count == 1, f"Expected 1 error, got {total_error_count}"


def test_call_stats_date_range_limit_query_layer(client: weave_client.WeaveClient):
    """Ensure call_stats rejects max date range during request handling."""
    skip_if_sqlite(client)

    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now - datetime.timedelta(days=32)
    req = tsi.CallStatsReq.model_construct(
        project_id=client._project_id(),
        start=start_time,
        end=now,
        granularity=3600,
        usage_metrics=[tsi.UsageMetricSpec(metric="total_tokens")],
        timezone="UTC",
    )

    with pytest.raises(ValidationError):
        client.server.call_stats(req)
