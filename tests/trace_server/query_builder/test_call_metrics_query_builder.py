"""Tests for the call_metrics_query_builder module.

These tests verify the SQL generation for call-level metrics
(latency, call count, error count) which are NOT grouped by model.
"""

import datetime

import pytest

from tests.trace_server.query_builder.utils import assert_call_metrics_sql
from weave.trace_server.project_version.types import ReadTable
from weave.trace_server.trace_server_interface import (
    AggregationType,
    CallMetricSpec,
    CallsFilter,
    CallStatsReq,
)

START_DT = datetime.datetime(2024, 12, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
DAY_END_DT = datetime.datetime(2024, 12, 2, 0, 0, 0, tzinfo=datetime.timezone.utc)
HOUR_END_DT = datetime.datetime(2024, 12, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
NOW = datetime.datetime(2024, 12, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)


@pytest.mark.parametrize(
    (
        "metrics",
        "granularity",
        "end_dt",
        "exp_query",
        "exp_params",
        "exp_columns",
        "exp_granularity",
    ),
    [
        pytest.param(
            [
                CallMetricSpec(
                    metric="latency_ms",
                    aggregations=[AggregationType.AVG, AggregationType.MAX],
                )
            ],
            3600,
            DAY_END_DT,
            """
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}))) / {pb_4:Float64})))
           WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
             aggregated_data AS
          (SELECT bucket,
                  avgOrNull(m_latency_ms) AS avg_latency_ms,
                  maxOrNull(m_latency_ms) AS max_latency_ms,
                  count() AS count
           FROM
             (SELECT toStartOfInterval(sortable_datetime, INTERVAL 3600 SECOND, {pb_3:String}) AS bucket,
                     dateDiff('millisecond', started_at, ended_at) AS m_latency_ms
              FROM
                (SELECT anyIf(cm.sortable_datetime, cm.sortable_datetime IS NOT NULL) AS sortable_datetime,
                        anyIf(cm.started_at, cm.started_at IS NOT NULL) AS started_at,
                        anyIf(cm.ended_at, cm.ended_at IS NOT NULL) AS ended_at,
                        anyIf(cm.exception, cm.exception IS NOT NULL) AS
                 exception
                 FROM calls_merged AS cm
                 WHERE cm.project_id = {pb_0:String}
                   AND cm.sortable_datetime >= toDateTime({pb_1:Float64}, {pb_3:String})
                   AND cm.sortable_datetime < toDateTime({pb_2:Float64}, {pb_3:String})
                   AND cm.deleted_at IS NULL
                 GROUP BY project_id,
                          id))
           GROUP BY bucket)
        SELECT all_buckets.bucket AS timestamp,
               COALESCE(aggregated_data.avg_latency_ms, 0) AS avg_latency_ms,
               aggregated_data.max_latency_ms AS max_latency_ms,
               COALESCE(aggregated_data.count, 0) AS count
        FROM all_buckets
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        ORDER BY all_buckets.bucket
        """,
            {
                "pb_0": "entity/project",
                "pb_1": 1733011200.0,
                "pb_2": 1733097600.0,
                "pb_3": "UTC",
                "pb_4": 3600,
            },
            ["timestamp", "avg_latency_ms", "max_latency_ms", "count"],
            3600,
            id="latency_avg_max",
        ),
        pytest.param(
            [
                CallMetricSpec(metric="call_count", aggregations=[AggregationType.SUM]),
                CallMetricSpec(
                    metric="error_count", aggregations=[AggregationType.SUM]
                ),
            ],
            3600,
            DAY_END_DT,
            """
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}))) / {pb_4:Float64})))
           WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
             aggregated_data AS
          (SELECT bucket,
                  sumOrNull(m_call_count) AS sum_call_count,
                  sumOrNull(m_error_count) AS sum_error_count,
                  count() AS count
           FROM
             (SELECT toStartOfInterval(sortable_datetime, INTERVAL 3600 SECOND, {pb_3:String}) AS bucket,
                     1 AS m_call_count,
                     if(
                        exception IS NOT NULL, 1, 0) AS m_error_count
              FROM
                (SELECT anyIf(cm.sortable_datetime, cm.sortable_datetime IS NOT NULL) AS sortable_datetime,
                        anyIf(cm.started_at, cm.started_at IS NOT NULL) AS started_at,
                        anyIf(cm.ended_at, cm.ended_at IS NOT NULL) AS ended_at,
                        anyIf(cm.exception, cm.exception IS NOT NULL) AS
                 exception
                 FROM calls_merged AS cm
                 WHERE cm.project_id = {pb_0:String}
                   AND cm.sortable_datetime >= toDateTime({pb_1:Float64}, {pb_3:String})
                   AND cm.sortable_datetime < toDateTime({pb_2:Float64}, {pb_3:String})
                   AND cm.deleted_at IS NULL
                 GROUP BY project_id,
                          id))
           GROUP BY bucket)
        SELECT all_buckets.bucket AS timestamp,
               COALESCE(aggregated_data.sum_call_count, 0) AS sum_call_count,
               COALESCE(aggregated_data.sum_error_count, 0) AS sum_error_count,
               COALESCE(aggregated_data.count, 0) AS count
        FROM all_buckets
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        ORDER BY all_buckets.bucket
        """,
            {
                "pb_0": "entity/project",
                "pb_1": 1733011200.0,
                "pb_2": 1733097600.0,
                "pb_3": "UTC",
                "pb_4": 3600,
            },
            ["timestamp", "sum_call_count", "sum_error_count", "count"],
            3600,
            id="call_and_error_counts",
        ),
        pytest.param(
            [
                CallMetricSpec(
                    metric="latency_ms",
                    aggregations=[
                        AggregationType.SUM,
                        AggregationType.AVG,
                        AggregationType.MIN,
                        AggregationType.MAX,
                        AggregationType.COUNT,
                    ],
                )
            ],
            300,
            HOUR_END_DT,
            """
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 300 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 300 SECOND, {pb_3:String}))) / {pb_4:Float64})))
           WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
             aggregated_data AS
          (SELECT bucket,
                  sumOrNull(m_latency_ms) AS sum_latency_ms,
                  avgOrNull(m_latency_ms) AS avg_latency_ms,
                  minOrNull(m_latency_ms) AS min_latency_ms,
                  maxOrNull(m_latency_ms) AS max_latency_ms,
                  countOrNull(m_latency_ms) AS count_latency_ms,
                  count() AS count
           FROM
             (SELECT toStartOfInterval(sortable_datetime, INTERVAL 300 SECOND, {pb_3:String}) AS bucket,
                     dateDiff('millisecond', started_at, ended_at) AS m_latency_ms
              FROM
                (SELECT anyIf(cm.sortable_datetime, cm.sortable_datetime IS NOT NULL) AS sortable_datetime,
                        anyIf(cm.started_at, cm.started_at IS NOT NULL) AS started_at,
                        anyIf(cm.ended_at, cm.ended_at IS NOT NULL) AS ended_at,
                        anyIf(cm.exception, cm.exception IS NOT NULL) AS
                 exception
                 FROM calls_merged AS cm
                 WHERE cm.project_id = {pb_0:String}
                   AND cm.sortable_datetime >= toDateTime({pb_1:Float64}, {pb_3:String})
                   AND cm.sortable_datetime < toDateTime({pb_2:Float64}, {pb_3:String})
                   AND cm.deleted_at IS NULL
                 GROUP BY project_id,
                          id))
           GROUP BY bucket)
        SELECT all_buckets.bucket AS timestamp,
               COALESCE(aggregated_data.sum_latency_ms, 0) AS sum_latency_ms,
               COALESCE(aggregated_data.avg_latency_ms, 0) AS avg_latency_ms,
               aggregated_data.min_latency_ms AS min_latency_ms,
               aggregated_data.max_latency_ms AS max_latency_ms,
               COALESCE(aggregated_data.count_latency_ms, 0) AS count_latency_ms,
               COALESCE(aggregated_data.count, 0) AS count
        FROM all_buckets
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        ORDER BY all_buckets.bucket
        """,
            {
                "pb_0": "entity/project",
                "pb_1": 1733011200.0,
                "pb_2": 1733014800.0,
                "pb_3": "UTC",
                "pb_4": 300,
            },
            [
                "timestamp",
                "sum_latency_ms",
                "avg_latency_ms",
                "min_latency_ms",
                "max_latency_ms",
                "count_latency_ms",
                "count",
            ],
            300,
            id="all_aggregation_types",
        ),
        pytest.param(
            [
                CallMetricSpec(
                    metric="latency_ms",
                    aggregations=[],
                    percentiles=[50, 95, 99],
                )
            ],
            300,
            HOUR_END_DT,
            """
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 300 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 300 SECOND, {pb_3:String}))) / {pb_4:Float64})))
           WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
             aggregated_data AS
          (SELECT bucket,
                  quantileOrNull(0.5)(m_latency_ms) AS p50_latency_ms,
                  quantileOrNull(0.95)(m_latency_ms) AS p95_latency_ms,
                  quantileOrNull(0.99)(m_latency_ms) AS p99_latency_ms,
                  count() AS count
           FROM
             (SELECT toStartOfInterval(sortable_datetime, INTERVAL 300 SECOND, {pb_3:String}) AS bucket,
                     dateDiff('millisecond', started_at, ended_at) AS m_latency_ms
              FROM
                (SELECT anyIf(cm.sortable_datetime, cm.sortable_datetime IS NOT NULL) AS sortable_datetime,
                        anyIf(cm.started_at, cm.started_at IS NOT NULL) AS started_at,
                        anyIf(cm.ended_at, cm.ended_at IS NOT NULL) AS ended_at,
                        anyIf(cm.exception, cm.exception IS NOT NULL) AS
                 exception
                 FROM calls_merged AS cm
                 WHERE cm.project_id = {pb_0:String}
                   AND cm.sortable_datetime >= toDateTime({pb_1:Float64}, {pb_3:String})
                   AND cm.sortable_datetime < toDateTime({pb_2:Float64}, {pb_3:String})
                   AND cm.deleted_at IS NULL
                 GROUP BY project_id,
                          id))
           GROUP BY bucket)
        SELECT all_buckets.bucket AS timestamp,
               aggregated_data.p50_latency_ms AS p50_latency_ms,
               aggregated_data.p95_latency_ms AS p95_latency_ms,
               aggregated_data.p99_latency_ms AS p99_latency_ms,
               COALESCE(aggregated_data.count, 0) AS count
        FROM all_buckets
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        ORDER BY all_buckets.bucket
        """,
            {
                "pb_0": "entity/project",
                "pb_1": 1733011200.0,
                "pb_2": 1733014800.0,
                "pb_3": "UTC",
                "pb_4": 300,
            },
            [
                "timestamp",
                "p50_latency_ms",
                "p95_latency_ms",
                "p99_latency_ms",
                "count",
            ],
            300,
            id="latency_percentiles",
        ),
        pytest.param(
            [
                CallMetricSpec(
                    metric="latency_ms",
                    aggregations=[AggregationType.AVG, AggregationType.MAX],
                ),
                CallMetricSpec(metric="call_count", aggregations=[AggregationType.SUM]),
                CallMetricSpec(
                    metric="error_count", aggregations=[AggregationType.SUM]
                ),
            ],
            3600,
            DAY_END_DT,
            """
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}))) / {pb_4:Float64})))
           WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
             aggregated_data AS
          (SELECT bucket,
                  avgOrNull(m_latency_ms) AS avg_latency_ms,
                  maxOrNull(m_latency_ms) AS max_latency_ms,
                  sumOrNull(m_call_count) AS sum_call_count,
                  sumOrNull(m_error_count) AS sum_error_count,
                  count() AS count
           FROM
             (SELECT toStartOfInterval(sortable_datetime, INTERVAL 3600 SECOND, {pb_3:String}) AS bucket,
                     dateDiff('millisecond', started_at, ended_at) AS m_latency_ms,
                     1 AS m_call_count,
                     if(
                        exception IS NOT NULL, 1, 0) AS m_error_count
              FROM
                (SELECT anyIf(cm.sortable_datetime, cm.sortable_datetime IS NOT NULL) AS sortable_datetime,
                        anyIf(cm.started_at, cm.started_at IS NOT NULL) AS started_at,
                        anyIf(cm.ended_at, cm.ended_at IS NOT NULL) AS ended_at,
                        anyIf(cm.exception, cm.exception IS NOT NULL) AS
                 exception
                 FROM calls_merged AS cm
                 WHERE cm.project_id = {pb_0:String}
                   AND cm.sortable_datetime >= toDateTime({pb_1:Float64}, {pb_3:String})
                   AND cm.sortable_datetime < toDateTime({pb_2:Float64}, {pb_3:String})
                   AND cm.deleted_at IS NULL
                 GROUP BY project_id,
                          id))
           GROUP BY bucket)
        SELECT all_buckets.bucket AS timestamp,
               COALESCE(aggregated_data.avg_latency_ms, 0) AS avg_latency_ms,
               aggregated_data.max_latency_ms AS max_latency_ms,
               COALESCE(aggregated_data.sum_call_count, 0) AS sum_call_count,
               COALESCE(aggregated_data.sum_error_count, 0) AS sum_error_count,
               COALESCE(aggregated_data.count, 0) AS count
        FROM all_buckets
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        ORDER BY all_buckets.bucket
        """,
            {
                "pb_0": "entity/project",
                "pb_1": 1733011200.0,
                "pb_2": 1733097600.0,
                "pb_3": "UTC",
                "pb_4": 3600,
            },
            [
                "timestamp",
                "avg_latency_ms",
                "max_latency_ms",
                "sum_call_count",
                "sum_error_count",
                "count",
            ],
            3600,
            id="combined_metrics",
        ),
    ],
)
def test_calls_merged_metric_shapes(
    metrics: list[CallMetricSpec],
    granularity: int,
    end_dt: datetime.datetime,
    exp_query: str,
    exp_params: dict[str, object],
    exp_columns: list[str],
    exp_granularity: int,
):
    """calls_merged metric/aggregation/percentile SQL shapes."""
    req = CallStatsReq(
        project_id="entity/project",
        start=START_DT,
        end=end_dt,
        granularity=granularity,
    )
    assert_call_metrics_sql(
        req,
        metrics,
        exp_query,
        exp_params,
        exp_columns,
        exp_granularity,
        exp_start=START_DT,
        exp_end=end_dt,
    )


@pytest.mark.parametrize(
    ("metric", "call_filter", "exp_query", "exp_params", "exp_columns"),
    [
        pytest.param(
            "call_count",
            CallsFilter(op_names=["openai.chat", "anthropic.messages"]),
            """
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}))) / {pb_4:Float64})))
           WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
             aggregated_data AS
          (SELECT bucket,
                  sumOrNull(m_call_count) AS sum_call_count,
                  count() AS count
           FROM
             (SELECT toStartOfInterval(sortable_datetime, INTERVAL 3600 SECOND, {pb_3:String}) AS bucket,
                     1 AS m_call_count
              FROM
                (SELECT anyIf(cm.sortable_datetime, cm.sortable_datetime IS NOT NULL) AS sortable_datetime,
                        anyIf(cm.started_at, cm.started_at IS NOT NULL) AS started_at,
                        anyIf(cm.ended_at, cm.ended_at IS NOT NULL) AS ended_at,
                        anyIf(cm.exception, cm.exception IS NOT NULL) AS
                 exception
                 FROM calls_merged AS cm
                 WHERE cm.project_id = {pb_0:String}
                   AND cm.sortable_datetime >= toDateTime({pb_1:Float64}, {pb_3:String})
                   AND cm.sortable_datetime < toDateTime({pb_2:Float64}, {pb_3:String})
                   AND cm.deleted_at IS NULL
                   AND op_name IN {pb_5:Array(String)}
                 GROUP BY project_id,
                          id))
           GROUP BY bucket)
        SELECT all_buckets.bucket AS timestamp,
               COALESCE(aggregated_data.sum_call_count, 0) AS sum_call_count,
               COALESCE(aggregated_data.count, 0) AS count
        FROM all_buckets
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        ORDER BY all_buckets.bucket
        """,
            {
                "pb_0": "entity/project",
                "pb_1": 1733011200.0,
                "pb_2": 1733097600.0,
                "pb_3": "UTC",
                "pb_4": 3600,
                "pb_5": ["openai.chat", "anthropic.messages"],
            },
            ["timestamp", "sum_call_count", "count"],
            id="op_names",
        ),
        pytest.param(
            "latency_ms",
            CallsFilter(trace_roots_only=True),
            """
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}))) / {pb_4:Float64})))
           WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
             aggregated_data AS
          (SELECT bucket,
                  avgOrNull(m_latency_ms) AS avg_latency_ms,
                  count() AS count
           FROM
             (SELECT toStartOfInterval(sortable_datetime, INTERVAL 3600 SECOND, {pb_3:String}) AS bucket,
                     dateDiff('millisecond', started_at, ended_at) AS m_latency_ms
              FROM
                (SELECT anyIf(cm.sortable_datetime, cm.sortable_datetime IS NOT NULL) AS sortable_datetime,
                        anyIf(cm.started_at, cm.started_at IS NOT NULL) AS started_at,
                        anyIf(cm.ended_at, cm.ended_at IS NOT NULL) AS ended_at,
                        anyIf(cm.exception, cm.exception IS NOT NULL) AS
                 exception
                 FROM calls_merged AS cm
                 WHERE cm.project_id = {pb_0:String}
                   AND cm.sortable_datetime >= toDateTime({pb_1:Float64}, {pb_3:String})
                   AND cm.sortable_datetime < toDateTime({pb_2:Float64}, {pb_3:String})
                   AND cm.deleted_at IS NULL
                   AND parent_id IS NULL
                 GROUP BY project_id,
                          id))
           GROUP BY bucket)
        SELECT all_buckets.bucket AS timestamp,
               COALESCE(aggregated_data.avg_latency_ms, 0) AS avg_latency_ms,
               COALESCE(aggregated_data.count, 0) AS count
        FROM all_buckets
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        ORDER BY all_buckets.bucket
        """,
            {
                "pb_0": "entity/project",
                "pb_1": 1733011200.0,
                "pb_2": 1733097600.0,
                "pb_3": "UTC",
                "pb_4": 3600,
            },
            ["timestamp", "avg_latency_ms", "count"],
            id="trace_roots_only",
        ),
        pytest.param(
            "error_count",
            CallsFilter(trace_ids=["trace_abc", "trace_def"]),
            """
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}))) / {pb_4:Float64})))
           WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
             aggregated_data AS
          (SELECT bucket,
                  sumOrNull(m_error_count) AS sum_error_count,
                  count() AS count
           FROM
             (SELECT toStartOfInterval(sortable_datetime, INTERVAL 3600 SECOND, {pb_3:String}) AS bucket,
                     if(
                        exception IS NOT NULL, 1, 0) AS m_error_count
              FROM
                (SELECT anyIf(cm.sortable_datetime, cm.sortable_datetime IS NOT NULL) AS sortable_datetime,
                        anyIf(cm.started_at, cm.started_at IS NOT NULL) AS started_at,
                        anyIf(cm.ended_at, cm.ended_at IS NOT NULL) AS ended_at,
                        anyIf(cm.exception, cm.exception IS NOT NULL) AS
                 exception
                 FROM calls_merged AS cm
                 WHERE cm.project_id = {pb_0:String}
                   AND cm.sortable_datetime >= toDateTime({pb_1:Float64}, {pb_3:String})
                   AND cm.sortable_datetime < toDateTime({pb_2:Float64}, {pb_3:String})
                   AND cm.deleted_at IS NULL
                   AND ifNull(trace_id, '') IN {pb_5:Array(String)}
                 GROUP BY project_id,
                          id))
           GROUP BY bucket)
        SELECT all_buckets.bucket AS timestamp,
               COALESCE(aggregated_data.sum_error_count, 0) AS sum_error_count,
               COALESCE(aggregated_data.count, 0) AS count
        FROM all_buckets
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        ORDER BY all_buckets.bucket
        """,
            {
                "pb_0": "entity/project",
                "pb_1": 1733011200.0,
                "pb_2": 1733097600.0,
                "pb_3": "UTC",
                "pb_4": 3600,
                "pb_5": ["trace_abc", "trace_def"],
            },
            ["timestamp", "sum_error_count", "count"],
            id="trace_ids",
        ),
    ],
)
def test_calls_merged_filters(
    metric: str,
    call_filter: CallsFilter,
    exp_query: str,
    exp_params: dict[str, object],
    exp_columns: list[str],
):
    """calls_merged filter-clause WHERE rewrites (op_names, trace_roots, trace_ids)."""
    agg = AggregationType.SUM if metric != "latency_ms" else AggregationType.AVG
    req = CallStatsReq(
        project_id="entity/project",
        start=START_DT,
        end=DAY_END_DT,
        granularity=3600,
        filter=call_filter,
    )
    assert_call_metrics_sql(
        req,
        [CallMetricSpec(metric=metric, aggregations=[agg])],
        exp_query,
        exp_params,
        exp_columns,
        3600,
        exp_start=START_DT,
        exp_end=DAY_END_DT,
    )


@pytest.mark.parametrize(
    ("delta", "granularity", "exp_query", "exp_params", "exp_granularity"),
    [
        pytest.param(
            datetime.timedelta(hours=1),
            300,
            """
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 300 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 300 SECOND, {pb_3:String}))) / {pb_4:Float64})))
           WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
             aggregated_data AS
          (SELECT bucket,
                  sumOrNull(m_call_count) AS sum_call_count,
                  count() AS count
           FROM
             (SELECT toStartOfInterval(sortable_datetime, INTERVAL 300 SECOND, {pb_3:String}) AS bucket,
                     1 AS m_call_count
              FROM
                (SELECT anyIf(cm.sortable_datetime, cm.sortable_datetime IS NOT NULL) AS sortable_datetime,
                        anyIf(cm.started_at, cm.started_at IS NOT NULL) AS started_at,
                        anyIf(cm.ended_at, cm.ended_at IS NOT NULL) AS ended_at,
                        anyIf(cm.exception, cm.exception IS NOT NULL) AS
                 exception
                 FROM calls_merged AS cm
                 WHERE cm.project_id = {pb_0:String}
                   AND cm.sortable_datetime >= toDateTime({pb_1:Float64}, {pb_3:String})
                   AND cm.sortable_datetime < toDateTime({pb_2:Float64}, {pb_3:String})
                   AND cm.deleted_at IS NULL
                 GROUP BY project_id,
                          id))
           GROUP BY bucket)
        SELECT all_buckets.bucket AS timestamp,
               COALESCE(aggregated_data.sum_call_count, 0) AS sum_call_count,
               COALESCE(aggregated_data.count, 0) AS count
        FROM all_buckets
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        ORDER BY all_buckets.bucket
        """,
            {
                "pb_0": "p",
                "pb_1": 1733050800.0,
                "pb_2": 1733054400.0,
                "pb_3": "UTC",
                "pb_4": 300,
            },
            300,
            id="under_2h_300s",
        ),
        pytest.param(
            datetime.timedelta(hours=6),
            3600,
            """
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}))) / {pb_4:Float64})))
           WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
             aggregated_data AS
          (SELECT bucket,
                  sumOrNull(m_call_count) AS sum_call_count,
                  count() AS count
           FROM
             (SELECT toStartOfInterval(sortable_datetime, INTERVAL 3600 SECOND, {pb_3:String}) AS bucket,
                     1 AS m_call_count
              FROM
                (SELECT anyIf(cm.sortable_datetime, cm.sortable_datetime IS NOT NULL) AS sortable_datetime,
                        anyIf(cm.started_at, cm.started_at IS NOT NULL) AS started_at,
                        anyIf(cm.ended_at, cm.ended_at IS NOT NULL) AS ended_at,
                        anyIf(cm.exception, cm.exception IS NOT NULL) AS
                 exception
                 FROM calls_merged AS cm
                 WHERE cm.project_id = {pb_0:String}
                   AND cm.sortable_datetime >= toDateTime({pb_1:Float64}, {pb_3:String})
                   AND cm.sortable_datetime < toDateTime({pb_2:Float64}, {pb_3:String})
                   AND cm.deleted_at IS NULL
                 GROUP BY project_id,
                          id))
           GROUP BY bucket)
        SELECT all_buckets.bucket AS timestamp,
               COALESCE(aggregated_data.sum_call_count, 0) AS sum_call_count,
               COALESCE(aggregated_data.count, 0) AS count
        FROM all_buckets
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        ORDER BY all_buckets.bucket
        """,
            {
                "pb_0": "p",
                "pb_1": 1733032800.0,
                "pb_2": 1733054400.0,
                "pb_3": "UTC",
                "pb_4": 3600,
            },
            3600,
            id="2_to_12h_3600s",
        ),
    ],
)
def test_granularity_auto_selection(
    delta: datetime.timedelta,
    granularity: int,
    exp_query: str,
    exp_params: dict[str, object],
    exp_granularity: int,
):
    """Automatic granularity selection based on time range (only 2 of 5 ladder steps)."""
    req = CallStatsReq(
        project_id="p",
        start=NOW - delta,
        end=NOW,
    )
    assert_call_metrics_sql(
        req,
        [CallMetricSpec(metric="call_count")],
        exp_query,
        exp_params,
        ["timestamp", "sum_call_count", "count"],
        granularity,
    )


# =============================================================================
# CALLS_COMPLETE TABLE TESTS
# =============================================================================
# These tests verify SQL generation for the calls_complete table which:
# - Uses started_at instead of sortable_datetime for datetime filtering/bucketing
# - Does not use anyIf aggregation (single row per call)
# - Does not use GROUP BY project_id, id
# =============================================================================


@pytest.mark.parametrize(
    ("metrics", "call_filter", "exp_query", "exp_params", "exp_columns"),
    [
        pytest.param(
            [
                CallMetricSpec(
                    metric="latency_ms",
                    aggregations=[AggregationType.AVG, AggregationType.MAX],
                )
            ],
            None,
            """
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}))) / {pb_4:Float64})))
           WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
             aggregated_data AS
          (SELECT bucket,
                  avgOrNull(m_latency_ms) AS avg_latency_ms,
                  maxOrNull(m_latency_ms) AS max_latency_ms,
                  count() AS count
           FROM
             (SELECT toStartOfInterval(started_at, INTERVAL 3600 SECOND, {pb_3:String}) AS bucket,
                     dateDiff('millisecond', started_at, ended_at) AS m_latency_ms
              FROM
                (SELECT cm.started_at AS started_at,
                        cm.started_at AS started_at,
                        cm.ended_at AS ended_at,
                        cm.exception AS
                 exception
                 FROM calls_complete AS cm
                 WHERE cm.project_id = {pb_0:String}
                   AND cm.started_at >= toDateTime({pb_1:Float64}, {pb_3:String})
                   AND cm.started_at < toDateTime({pb_2:Float64}, {pb_3:String})
                   AND cm.deleted_at = toDateTime64(0, 3) ))
           GROUP BY bucket)
        SELECT all_buckets.bucket AS timestamp,
               COALESCE(aggregated_data.avg_latency_ms, 0) AS avg_latency_ms,
               aggregated_data.max_latency_ms AS max_latency_ms,
               COALESCE(aggregated_data.count, 0) AS count
        FROM all_buckets
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        ORDER BY all_buckets.bucket
        """,
            {
                "pb_0": "entity/project",
                "pb_1": 1733011200.0,
                "pb_2": 1733097600.0,
                "pb_3": "UTC",
                "pb_4": 3600,
            },
            ["timestamp", "avg_latency_ms", "max_latency_ms", "count"],
            id="latency_basic",
        ),
        pytest.param(
            [
                CallMetricSpec(metric="call_count", aggregations=[AggregationType.SUM]),
                CallMetricSpec(
                    metric="error_count", aggregations=[AggregationType.SUM]
                ),
            ],
            None,
            """
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}))) / {pb_4:Float64})))
           WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
             aggregated_data AS
          (SELECT bucket,
                  sumOrNull(m_call_count) AS sum_call_count,
                  sumOrNull(m_error_count) AS sum_error_count,
                  count() AS count
           FROM
             (SELECT toStartOfInterval(started_at, INTERVAL 3600 SECOND, {pb_3:String}) AS bucket,
                     1 AS m_call_count,
                     if(
                        exception != {pb_5:String}, 1, 0) AS m_error_count
              FROM
                (SELECT cm.started_at AS started_at,
                        cm.started_at AS started_at,
                        cm.ended_at AS ended_at,
                        cm.exception AS
                 exception
                 FROM calls_complete AS cm
                 WHERE cm.project_id = {pb_0:String}
                   AND cm.started_at >= toDateTime({pb_1:Float64}, {pb_3:String})
                   AND cm.started_at < toDateTime({pb_2:Float64}, {pb_3:String})
                   AND cm.deleted_at = toDateTime64(0, 3) ))
           GROUP BY bucket)
        SELECT all_buckets.bucket AS timestamp,
               COALESCE(aggregated_data.sum_call_count, 0) AS sum_call_count,
               COALESCE(aggregated_data.sum_error_count, 0) AS sum_error_count,
               COALESCE(aggregated_data.count, 0) AS count
        FROM all_buckets
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        ORDER BY all_buckets.bucket
        """,
            {
                "pb_0": "entity/project",
                "pb_1": 1733011200.0,
                "pb_2": 1733097600.0,
                "pb_3": "UTC",
                "pb_4": 3600,
                "pb_5": "",
            },
            ["timestamp", "sum_call_count", "sum_error_count", "count"],
            id="call_and_error_counts",
        ),
        pytest.param(
            [CallMetricSpec(metric="latency_ms", aggregations=[AggregationType.AVG])],
            CallsFilter(trace_roots_only=True),
            """
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}))) / {pb_4:Float64})))
           WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
             aggregated_data AS
          (SELECT bucket,
                  avgOrNull(m_latency_ms) AS avg_latency_ms,
                  count() AS count
           FROM
             (SELECT toStartOfInterval(started_at, INTERVAL 3600 SECOND, {pb_3:String}) AS bucket,
                     dateDiff('millisecond', started_at, ended_at) AS m_latency_ms
              FROM
                (SELECT cm.started_at AS started_at,
                        cm.started_at AS started_at,
                        cm.ended_at AS ended_at,
                        cm.exception AS
                 exception
                 FROM calls_complete AS cm
                 WHERE cm.project_id = {pb_0:String}
                   AND cm.started_at >= toDateTime({pb_1:Float64}, {pb_3:String})
                   AND cm.started_at < toDateTime({pb_2:Float64}, {pb_3:String})
                   AND cm.deleted_at = toDateTime64(0, 3)
                   AND parent_id = {pb_5:String} ))
           GROUP BY bucket)
        SELECT all_buckets.bucket AS timestamp,
               COALESCE(aggregated_data.avg_latency_ms, 0) AS avg_latency_ms,
               COALESCE(aggregated_data.count, 0) AS count
        FROM all_buckets
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        ORDER BY all_buckets.bucket
        """,
            {
                "pb_0": "entity/project",
                "pb_1": 1733011200.0,
                "pb_2": 1733097600.0,
                "pb_3": "UTC",
                "pb_4": 3600,
                "pb_5": "",
            },
            ["timestamp", "avg_latency_ms", "count"],
            id="trace_roots_only_sentinel",
        ),
        pytest.param(
            [CallMetricSpec(metric="call_count", aggregations=[AggregationType.SUM])],
            CallsFilter(op_names=["openai.chat"]),
            """
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}))) / {pb_4:Float64})))
           WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
             aggregated_data AS
          (SELECT bucket,
                  sumOrNull(m_call_count) AS sum_call_count,
                  count() AS count
           FROM
             (SELECT toStartOfInterval(started_at, INTERVAL 3600 SECOND, {pb_3:String}) AS bucket,
                     1 AS m_call_count
              FROM
                (SELECT cm.started_at AS started_at,
                        cm.started_at AS started_at,
                        cm.ended_at AS ended_at,
                        cm.exception AS
                 exception
                 FROM calls_complete AS cm
                 WHERE cm.project_id = {pb_0:String}
                   AND cm.started_at >= toDateTime({pb_1:Float64}, {pb_3:String})
                   AND cm.started_at < toDateTime({pb_2:Float64}, {pb_3:String})
                   AND cm.deleted_at = toDateTime64(0, 3)
                   AND op_name IN {pb_5:Array(String)} ))
           GROUP BY bucket)
        SELECT all_buckets.bucket AS timestamp,
               COALESCE(aggregated_data.sum_call_count, 0) AS sum_call_count,
               COALESCE(aggregated_data.count, 0) AS count
        FROM all_buckets
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        ORDER BY all_buckets.bucket
        """,
            {
                "pb_0": "entity/project",
                "pb_1": 1733011200.0,
                "pb_2": 1733097600.0,
                "pb_3": "UTC",
                "pb_4": 3600,
                "pb_5": ["openai.chat"],
            },
            ["timestamp", "sum_call_count", "count"],
            id="op_names_filter",
        ),
    ],
)
def test_calls_complete_shapes(
    metrics: list[CallMetricSpec],
    call_filter: CallsFilter | None,
    exp_query: str,
    exp_params: dict[str, object],
    exp_columns: list[str],
):
    """calls_complete inner-query shape: started_at bucketing, no anyIf/GROUP BY, sentinel branches."""
    req = CallStatsReq(
        project_id="entity/project",
        start=START_DT,
        end=DAY_END_DT,
        granularity=3600,
        filter=call_filter,
    )
    assert_call_metrics_sql(
        req,
        metrics,
        exp_query,
        exp_params,
        exp_columns,
        3600,
        exp_start=START_DT,
        exp_end=DAY_END_DT,
        read_table=ReadTable.CALLS_COMPLETE,
    )
