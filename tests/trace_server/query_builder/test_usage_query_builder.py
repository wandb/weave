import datetime

import pytest

from tests.trace_server.query_builder.utils import assert_usage_sql
from weave.trace_server.project_version.types import ReadTable
from weave.trace_server.trace_server_interface import (
    AggregationType,
    CallsFilter,
    CallStatsReq,
    UsageMetricSpec,
)

START_DT = datetime.datetime(2024, 12, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
END_DT = datetime.datetime(2024, 12, 2, 0, 0, 0, tzinfo=datetime.timezone.utc)
END_DT_1H = datetime.datetime(2024, 12, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)


@pytest.mark.parametrize(
    ("metrics", "end_dt", "granularity", "expected_query", "expected_columns"),
    [
        pytest.param(
            [
                UsageMetricSpec(
                    metric="total_tokens",
                    aggregations=[AggregationType.SUM, AggregationType.AVG],
                )
            ],
            END_DT,
            3600,
            """
            WITH all_buckets AS
              (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
               FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}))) / {pb_4:Float64})))
               WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
                 aggregated_data AS
              (SELECT bucket,
                      model,
                      sumOrNull(m_total_tokens) AS sum_total_tokens,
                      avgOrNull(m_total_tokens) AS avg_total_tokens,
                      count() AS count
               FROM
                 (SELECT toStartOfInterval(sortable_datetime, INTERVAL 3600 SECOND, {pb_3:String}) AS bucket,
                         kv.1 AS model,
                         toFloat64OrNull(JSONExtractRaw(kv.2, 'total_tokens')) AS m_total_tokens
                  FROM
                    (SELECT sortable_datetime,
                            JSONExtractRaw(ifNull(summary_dump, '{}'), 'usage') AS usage_raw
                     FROM
                       (SELECT anyIf(cm.sortable_datetime, cm.sortable_datetime IS NOT NULL) AS sortable_datetime,
                               anyIf(cm.summary_dump, cm.summary_dump IS NOT NULL) AS summary_dump
                        FROM calls_merged AS cm
                        WHERE cm.project_id = {pb_0:String}
                          AND cm.sortable_datetime >= toDateTime({pb_1:Float64}, {pb_3:String})
                          AND cm.sortable_datetime < toDateTime({pb_2:Float64}, {pb_3:String})
                          AND cm.deleted_at IS NULL
                        GROUP BY project_id,
                                 id)) ARRAY
                  JOIN JSONExtractKeysAndValuesRaw(ifNull(usage_raw, '{}')) AS kv)
               GROUP BY bucket,
                        model),
                 all_models AS
              (SELECT DISTINCT model
               FROM aggregated_data)
            SELECT all_buckets.bucket AS timestamp,
                   all_models.model,
                   COALESCE(aggregated_data.sum_total_tokens, 0) AS sum_total_tokens,
                   COALESCE(aggregated_data.avg_total_tokens, 0) AS avg_total_tokens,
                   COALESCE(aggregated_data.count, 0) AS count
            FROM all_buckets
            CROSS JOIN all_models
            LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
            AND all_models.model = aggregated_data.model
            ORDER BY all_buckets.bucket,
                     all_models.model
            """,
            ["timestamp", "model", "sum_total_tokens", "avg_total_tokens", "count"],
            id="sum_avg",
        ),
        pytest.param(
            [
                UsageMetricSpec(
                    metric="total_tokens",
                    aggregations=[
                        AggregationType.SUM,
                        AggregationType.AVG,
                        AggregationType.MIN,
                        AggregationType.MAX,
                        AggregationType.COUNT,
                    ],
                )
            ],
            END_DT_1H,
            300,
            """
            WITH all_buckets AS
              (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 300 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
               FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 300 SECOND, {pb_3:String}))) / {pb_4:Float64})))
               WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
                 aggregated_data AS
              (SELECT bucket,
                      model,
                      sumOrNull(m_total_tokens) AS sum_total_tokens,
                      avgOrNull(m_total_tokens) AS avg_total_tokens,
                      minOrNull(m_total_tokens) AS min_total_tokens,
                      maxOrNull(m_total_tokens) AS max_total_tokens,
                      countOrNull(m_total_tokens) AS count_total_tokens,
                      count() AS count
               FROM
                 (SELECT toStartOfInterval(sortable_datetime, INTERVAL 300 SECOND, {pb_3:String}) AS bucket,
                         kv.1 AS model,
                         toFloat64OrNull(JSONExtractRaw(kv.2, 'total_tokens')) AS m_total_tokens
                  FROM
                    (SELECT sortable_datetime,
                            JSONExtractRaw(ifNull(summary_dump, '{}'), 'usage') AS usage_raw
                     FROM
                       (SELECT anyIf(cm.sortable_datetime, cm.sortable_datetime IS NOT NULL) AS sortable_datetime,
                               anyIf(cm.summary_dump, cm.summary_dump IS NOT NULL) AS summary_dump
                        FROM calls_merged AS cm
                        WHERE cm.project_id = {pb_0:String}
                          AND cm.sortable_datetime >= toDateTime({pb_1:Float64}, {pb_3:String})
                          AND cm.sortable_datetime < toDateTime({pb_2:Float64}, {pb_3:String})
                          AND cm.deleted_at IS NULL
                        GROUP BY project_id,
                                 id)) ARRAY
                  JOIN JSONExtractKeysAndValuesRaw(ifNull(usage_raw, '{}')) AS kv)
               GROUP BY bucket,
                        model),
                 all_models AS
              (SELECT DISTINCT model
               FROM aggregated_data)
            SELECT all_buckets.bucket AS timestamp,
                   all_models.model,
                   COALESCE(aggregated_data.sum_total_tokens, 0) AS sum_total_tokens,
                   COALESCE(aggregated_data.avg_total_tokens, 0) AS avg_total_tokens,
                   aggregated_data.min_total_tokens AS min_total_tokens,
                   aggregated_data.max_total_tokens AS max_total_tokens,
                   COALESCE(aggregated_data.count_total_tokens, 0) AS count_total_tokens,
                   COALESCE(aggregated_data.count, 0) AS count
            FROM all_buckets
            CROSS JOIN all_models
            LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
            AND all_models.model = aggregated_data.model
            ORDER BY all_buckets.bucket,
                     all_models.model
            """,
            [
                "timestamp",
                "model",
                "sum_total_tokens",
                "avg_total_tokens",
                "min_total_tokens",
                "max_total_tokens",
                "count_total_tokens",
                "count",
            ],
            id="all_aggregation_types",
        ),
        pytest.param(
            [
                UsageMetricSpec(
                    metric="output_tokens",
                    aggregations=[],
                    percentiles=[50, 75, 90, 95, 99, 99.9],
                )
            ],
            END_DT_1H,
            300,
            """
            WITH all_buckets AS
              (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 300 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
               FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 300 SECOND, {pb_3:String}))) / {pb_4:Float64})))
               WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
                 aggregated_data AS
              (SELECT bucket,
                      model,
                      quantileOrNull(0.5)(m_output_tokens) AS p50_output_tokens,
                      quantileOrNull(0.75)(m_output_tokens) AS p75_output_tokens,
                      quantileOrNull(0.9)(m_output_tokens) AS p90_output_tokens,
                      quantileOrNull(0.95)(m_output_tokens) AS p95_output_tokens,
                      quantileOrNull(0.99)(m_output_tokens) AS p99_output_tokens,
                      quantileOrNull(0.999)(m_output_tokens) AS p99.9_output_tokens,
                      count() AS count
               FROM
                 (SELECT toStartOfInterval(sortable_datetime, INTERVAL 300 SECOND, {pb_3:String}) AS bucket,
                         kv.1 AS model,
                         (ifNull(toFloat64OrNull(JSONExtractRaw(kv.2, 'completion_tokens')), 0) + ifNull(toFloat64OrNull(JSONExtractRaw(kv.2, 'output_tokens')), 0)) AS m_output_tokens
                  FROM
                    (SELECT sortable_datetime,
                            JSONExtractRaw(ifNull(summary_dump, '{}'), 'usage') AS usage_raw
                     FROM
                       (SELECT anyIf(cm.sortable_datetime, cm.sortable_datetime IS NOT NULL) AS sortable_datetime,
                               anyIf(cm.summary_dump, cm.summary_dump IS NOT NULL) AS summary_dump
                        FROM calls_merged AS cm
                        WHERE cm.project_id = {pb_0:String}
                          AND cm.sortable_datetime >= toDateTime({pb_1:Float64}, {pb_3:String})
                          AND cm.sortable_datetime < toDateTime({pb_2:Float64}, {pb_3:String})
                          AND cm.deleted_at IS NULL
                        GROUP BY project_id,
                                 id)) ARRAY
                  JOIN JSONExtractKeysAndValuesRaw(ifNull(usage_raw, '{}')) AS kv)
               GROUP BY bucket,
                        model),
                 all_models AS
              (SELECT DISTINCT model
               FROM aggregated_data)
            SELECT all_buckets.bucket AS timestamp,
                   all_models.model,
                   aggregated_data.p50_output_tokens AS p50_output_tokens,
                   aggregated_data.p75_output_tokens AS p75_output_tokens,
                   aggregated_data.p90_output_tokens AS p90_output_tokens,
                   aggregated_data.p95_output_tokens AS p95_output_tokens,
                   aggregated_data.p99_output_tokens AS p99_output_tokens,
                   aggregated_data.p99.9_output_tokens AS p99.9_output_tokens,
                   COALESCE(aggregated_data.count, 0) AS count
            FROM all_buckets
            CROSS JOIN all_models
            LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
            AND all_models.model = aggregated_data.model
            ORDER BY all_buckets.bucket,
                     all_models.model
            """,
            [
                "timestamp",
                "model",
                "p50_output_tokens",
                "p75_output_tokens",
                "p90_output_tokens",
                "p95_output_tokens",
                "p99_output_tokens",
                "p99.9_output_tokens",
                "count",
            ],
            id="custom_percentiles",
        ),
        pytest.param(
            [
                UsageMetricSpec(
                    metric="input_tokens", aggregations=[AggregationType.SUM]
                ),
                UsageMetricSpec(
                    metric="output_tokens", aggregations=[AggregationType.SUM]
                ),
                UsageMetricSpec(
                    metric="total_tokens", aggregations=[AggregationType.AVG]
                ),
            ],
            END_DT,
            3600,
            """
            WITH all_buckets AS
              (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
               FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}))) / {pb_4:Float64})))
               WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
                 aggregated_data AS
              (SELECT bucket,
                      model,
                      sumOrNull(m_input_tokens) AS sum_input_tokens,
                      sumOrNull(m_output_tokens) AS sum_output_tokens,
                      avgOrNull(m_total_tokens) AS avg_total_tokens,
                      count() AS count
               FROM
                 (SELECT toStartOfInterval(sortable_datetime, INTERVAL 3600 SECOND, {pb_3:String}) AS bucket,
                         kv.1 AS model,
                         (ifNull(toFloat64OrNull(JSONExtractRaw(kv.2, 'prompt_tokens')), 0) + ifNull(toFloat64OrNull(JSONExtractRaw(kv.2, 'input_tokens')), 0)) AS m_input_tokens,
                         (ifNull(toFloat64OrNull(JSONExtractRaw(kv.2, 'completion_tokens')), 0) + ifNull(toFloat64OrNull(JSONExtractRaw(kv.2, 'output_tokens')), 0)) AS m_output_tokens,
                         toFloat64OrNull(JSONExtractRaw(kv.2, 'total_tokens')) AS m_total_tokens
                  FROM
                    (SELECT sortable_datetime,
                            JSONExtractRaw(ifNull(summary_dump, '{}'), 'usage') AS usage_raw
                     FROM
                       (SELECT anyIf(cm.sortable_datetime, cm.sortable_datetime IS NOT NULL) AS sortable_datetime,
                               anyIf(cm.summary_dump, cm.summary_dump IS NOT NULL) AS summary_dump
                        FROM calls_merged AS cm
                        WHERE cm.project_id = {pb_0:String}
                          AND cm.sortable_datetime >= toDateTime({pb_1:Float64}, {pb_3:String})
                          AND cm.sortable_datetime < toDateTime({pb_2:Float64}, {pb_3:String})
                          AND cm.deleted_at IS NULL
                        GROUP BY project_id,
                                 id)) ARRAY
                  JOIN JSONExtractKeysAndValuesRaw(ifNull(usage_raw, '{}')) AS kv)
               GROUP BY bucket,
                        model),
                 all_models AS
              (SELECT DISTINCT model
               FROM aggregated_data)
            SELECT all_buckets.bucket AS timestamp,
                   all_models.model,
                   COALESCE(aggregated_data.sum_input_tokens, 0) AS sum_input_tokens,
                   COALESCE(aggregated_data.sum_output_tokens, 0) AS sum_output_tokens,
                   COALESCE(aggregated_data.avg_total_tokens, 0) AS avg_total_tokens,
                   COALESCE(aggregated_data.count, 0) AS count
            FROM all_buckets
            CROSS JOIN all_models
            LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
            AND all_models.model = aggregated_data.model
            ORDER BY all_buckets.bucket,
                     all_models.model
            """,
            [
                "timestamp",
                "model",
                "sum_input_tokens",
                "sum_output_tokens",
                "avg_total_tokens",
                "count",
            ],
            id="multiple_metrics",
        ),
        pytest.param(
            [
                UsageMetricSpec(
                    metric="total_tokens",
                    aggregations=[AggregationType.SUM, AggregationType.AVG],
                    percentiles=[50, 95, 99],
                )
            ],
            END_DT,
            3600,
            """
            WITH all_buckets AS
              (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
               FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}))) / {pb_4:Float64})))
               WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
                 aggregated_data AS
              (SELECT bucket,
                      model,
                      sumOrNull(m_total_tokens) AS sum_total_tokens,
                      avgOrNull(m_total_tokens) AS avg_total_tokens,
                      quantileOrNull(0.5)(m_total_tokens) AS p50_total_tokens,
                      quantileOrNull(0.95)(m_total_tokens) AS p95_total_tokens,
                      quantileOrNull(0.99)(m_total_tokens) AS p99_total_tokens,
                      count() AS count
               FROM
                 (SELECT toStartOfInterval(sortable_datetime, INTERVAL 3600 SECOND, {pb_3:String}) AS bucket,
                         kv.1 AS model,
                         toFloat64OrNull(JSONExtractRaw(kv.2, 'total_tokens')) AS m_total_tokens
                  FROM
                    (SELECT sortable_datetime,
                            JSONExtractRaw(ifNull(summary_dump, '{}'), 'usage') AS usage_raw
                     FROM
                       (SELECT anyIf(cm.sortable_datetime, cm.sortable_datetime IS NOT NULL) AS sortable_datetime,
                               anyIf(cm.summary_dump, cm.summary_dump IS NOT NULL) AS summary_dump
                        FROM calls_merged AS cm
                        WHERE cm.project_id = {pb_0:String}
                          AND cm.sortable_datetime >= toDateTime({pb_1:Float64}, {pb_3:String})
                          AND cm.sortable_datetime < toDateTime({pb_2:Float64}, {pb_3:String})
                          AND cm.deleted_at IS NULL
                        GROUP BY project_id,
                                 id)) ARRAY
                  JOIN JSONExtractKeysAndValuesRaw(ifNull(usage_raw, '{}')) AS kv)
               GROUP BY bucket,
                        model),
                 all_models AS
              (SELECT DISTINCT model
               FROM aggregated_data)
            SELECT all_buckets.bucket AS timestamp,
                   all_models.model,
                   COALESCE(aggregated_data.sum_total_tokens, 0) AS sum_total_tokens,
                   COALESCE(aggregated_data.avg_total_tokens, 0) AS avg_total_tokens,
                   aggregated_data.p50_total_tokens AS p50_total_tokens,
                   aggregated_data.p95_total_tokens AS p95_total_tokens,
                   aggregated_data.p99_total_tokens AS p99_total_tokens,
                   COALESCE(aggregated_data.count, 0) AS count
            FROM all_buckets
            CROSS JOIN all_models
            LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
            AND all_models.model = aggregated_data.model
            ORDER BY all_buckets.bucket,
                     all_models.model
            """,
            [
                "timestamp",
                "model",
                "sum_total_tokens",
                "avg_total_tokens",
                "p50_total_tokens",
                "p95_total_tokens",
                "p99_total_tokens",
                "count",
            ],
            id="mixed_aggregations_and_percentiles",
        ),
        pytest.param(
            [UsageMetricSpec(metric="total_tokens")],
            END_DT,
            300,
            """
            WITH all_buckets AS
              (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 300 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
               FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 300 SECOND, {pb_3:String}))) / {pb_4:Float64})))
               WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
                 aggregated_data AS
              (SELECT bucket,
                      model,
                      sumOrNull(m_total_tokens) AS sum_total_tokens,
                      count() AS count
               FROM
                 (SELECT toStartOfInterval(sortable_datetime, INTERVAL 300 SECOND, {pb_3:String}) AS bucket,
                         kv.1 AS model,
                         toFloat64OrNull(JSONExtractRaw(kv.2, 'total_tokens')) AS m_total_tokens
                  FROM
                    (SELECT sortable_datetime,
                            JSONExtractRaw(ifNull(summary_dump, '{}'), 'usage') AS usage_raw
                     FROM
                       (SELECT anyIf(cm.sortable_datetime, cm.sortable_datetime IS NOT NULL) AS sortable_datetime,
                               anyIf(cm.summary_dump, cm.summary_dump IS NOT NULL) AS summary_dump
                        FROM calls_merged AS cm
                        WHERE cm.project_id = {pb_0:String}
                          AND cm.sortable_datetime >= toDateTime({pb_1:Float64}, {pb_3:String})
                          AND cm.sortable_datetime < toDateTime({pb_2:Float64}, {pb_3:String})
                          AND cm.deleted_at IS NULL
                        GROUP BY project_id,
                                 id)) ARRAY
                  JOIN JSONExtractKeysAndValuesRaw(ifNull(usage_raw, '{}')) AS kv)
               GROUP BY bucket,
                        model),
                 all_models AS
              (SELECT DISTINCT model
               FROM aggregated_data)
            SELECT all_buckets.bucket AS timestamp,
                   all_models.model,
                   COALESCE(aggregated_data.sum_total_tokens, 0) AS sum_total_tokens,
                   COALESCE(aggregated_data.count, 0) AS count
            FROM all_buckets
            CROSS JOIN all_models
            LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
            AND all_models.model = aggregated_data.model
            ORDER BY all_buckets.bucket,
                     all_models.model
            """,
            ["timestamp", "model", "sum_total_tokens", "count"],
            id="explicit_granularity_overrides_auto",
        ),
    ],
)
def test_calls_merged_aggregation_shapes(
    metrics: list[UsageMetricSpec],
    end_dt: datetime.datetime,
    granularity: int,
    expected_query: str,
    expected_columns: list[str],
) -> None:
    req = CallStatsReq(
        project_id="entity/project",
        start=START_DT,
        end=end_dt,
        granularity=granularity,
    )
    assert_usage_sql(
        req,
        metrics,
        expected_query,
        {
            "pb_0": "entity/project",
            "pb_1": 1733011200.0,
            "pb_2": end_dt.timestamp(),
            "pb_3": "UTC",
            "pb_4": granularity,
        },
        expected_columns,
        granularity,
        exp_start=START_DT,
        exp_end=end_dt,
    )


@pytest.mark.parametrize(
    ("call_filter", "where_clause", "pb_5"),
    [
        pytest.param(
            CallsFilter(op_names=["openai.chat", "anthropic.messages"]),
            "AND op_name IN {pb_5:Array(String)}",
            ["openai.chat", "anthropic.messages"],
            id="op_names",
        ),
        pytest.param(
            CallsFilter(trace_roots_only=True),
            "AND parent_id IS NULL",
            None,
            id="trace_roots_only",
        ),
        pytest.param(
            CallsFilter(trace_ids=["trace_abc", "trace_def"]),
            "AND ifNull(trace_id, '') IN {pb_5:Array(String)}",
            ["trace_abc", "trace_def"],
            id="trace_ids",
        ),
        pytest.param(
            CallsFilter(wb_user_ids=["user_123"]),
            "AND wb_user_id IN {pb_5:Array(String)}",
            ["user_123"],
            id="wb_user_ids",
        ),
    ],
)
def test_calls_merged_filter_clauses(
    call_filter: CallsFilter,
    where_clause: str,
    pb_5: list[str] | None,
) -> None:
    metrics = [UsageMetricSpec(metric="total_tokens")]
    req = CallStatsReq(
        project_id="entity/project",
        start=START_DT,
        end=END_DT,
        granularity=3600,
        filter=call_filter,
    )
    expected_query = f"""
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({{pb_1:Float64}}, {{pb_3:String}}), INTERVAL 3600 SECOND, {{pb_3:String}}) + toIntervalSecond(number * {{pb_4:Int64}}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({{pb_2:Float64}}, {{pb_3:String}})) - toUnixTimestamp(toStartOfInterval(toDateTime({{pb_1:Float64}}, {{pb_3:String}}), INTERVAL 3600 SECOND, {{pb_3:String}}))) / {{pb_4:Float64}})))
           WHERE bucket < toDateTime({{pb_2:Float64}}, {{pb_3:String}}) ),
             aggregated_data AS
          (SELECT bucket,
                  model,
                  sumOrNull(m_total_tokens) AS sum_total_tokens,
                  count() AS count
           FROM
             (SELECT toStartOfInterval(sortable_datetime, INTERVAL 3600 SECOND, {{pb_3:String}}) AS bucket,
                     kv.1 AS model,
                     toFloat64OrNull(JSONExtractRaw(kv.2, 'total_tokens')) AS m_total_tokens
              FROM
                (SELECT sortable_datetime,
                        JSONExtractRaw(ifNull(summary_dump, '{{}}'), 'usage') AS usage_raw
                 FROM
                   (SELECT anyIf(cm.sortable_datetime, cm.sortable_datetime IS NOT NULL) AS sortable_datetime,
                           anyIf(cm.summary_dump, cm.summary_dump IS NOT NULL) AS summary_dump
                    FROM calls_merged AS cm
                    WHERE cm.project_id = {{pb_0:String}}
                      AND cm.sortable_datetime >= toDateTime({{pb_1:Float64}}, {{pb_3:String}})
                      AND cm.sortable_datetime < toDateTime({{pb_2:Float64}}, {{pb_3:String}})
                      AND cm.deleted_at IS NULL
                      {where_clause}
                    GROUP BY project_id,
                             id)) ARRAY
              JOIN JSONExtractKeysAndValuesRaw(ifNull(usage_raw, '{{}}')) AS kv)
           GROUP BY bucket,
                    model),
             all_models AS
          (SELECT DISTINCT model
           FROM aggregated_data)
        SELECT all_buckets.bucket AS timestamp,
               all_models.model,
               COALESCE(aggregated_data.sum_total_tokens, 0) AS sum_total_tokens,
               COALESCE(aggregated_data.count, 0) AS count
        FROM all_buckets
        CROSS JOIN all_models
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        AND all_models.model = aggregated_data.model
        ORDER BY all_buckets.bucket,
                 all_models.model
        """
    expected_params = {
        "pb_0": "entity/project",
        "pb_1": 1733011200.0,
        "pb_2": 1733097600.0,
        "pb_3": "UTC",
        "pb_4": 3600,
    }
    if pb_5 is not None:
        expected_params["pb_5"] = pb_5
    assert_usage_sql(
        req,
        metrics,
        expected_query,
        expected_params,
        ["timestamp", "model", "sum_total_tokens", "count"],
        3600,
        exp_start=START_DT,
        exp_end=END_DT,
    )


@pytest.mark.parametrize(
    ("delta", "granularity", "expected_pb_1"),
    [
        pytest.param(datetime.timedelta(hours=1), 300, 1733050800.0, id="under_2h_300"),
        pytest.param(datetime.timedelta(hours=6), 3600, 1733032800.0, id="2h_12h_3600"),
        pytest.param(
            datetime.timedelta(days=2), 21600, 1732881600.0, id="12h_3d_21600"
        ),
        pytest.param(
            datetime.timedelta(days=10), 43200, 1732190400.0, id="3d_14d_43200"
        ),
        pytest.param(
            datetime.timedelta(days=30), 86400, 1730462400.0, id="over_14d_86400"
        ),
    ],
)
def test_granularity_auto_selection(
    delta: datetime.timedelta,
    granularity: int,
    expected_pb_1: float,
) -> None:
    now = datetime.datetime(2024, 12, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    metrics = [UsageMetricSpec(metric="total_tokens")]
    req = CallStatsReq(project_id="p", start=now - delta, end=now)
    expected_query = f"""
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({{pb_1:Float64}}, {{pb_3:String}}), INTERVAL {granularity} SECOND, {{pb_3:String}}) + toIntervalSecond(number * {{pb_4:Int64}}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({{pb_2:Float64}}, {{pb_3:String}})) - toUnixTimestamp(toStartOfInterval(toDateTime({{pb_1:Float64}}, {{pb_3:String}}), INTERVAL {granularity} SECOND, {{pb_3:String}}))) / {{pb_4:Float64}})))
           WHERE bucket < toDateTime({{pb_2:Float64}}, {{pb_3:String}}) ),
             aggregated_data AS
          (SELECT bucket,
                  model,
                  sumOrNull(m_total_tokens) AS sum_total_tokens,
                  count() AS count
           FROM
             (SELECT toStartOfInterval(sortable_datetime, INTERVAL {granularity} SECOND, {{pb_3:String}}) AS bucket,
                     kv.1 AS model,
                     toFloat64OrNull(JSONExtractRaw(kv.2, 'total_tokens')) AS m_total_tokens
              FROM
                (SELECT sortable_datetime,
                        JSONExtractRaw(ifNull(summary_dump, '{{}}'), 'usage') AS usage_raw
                 FROM
                   (SELECT anyIf(cm.sortable_datetime, cm.sortable_datetime IS NOT NULL) AS sortable_datetime,
                           anyIf(cm.summary_dump, cm.summary_dump IS NOT NULL) AS summary_dump
                    FROM calls_merged AS cm
                    WHERE cm.project_id = {{pb_0:String}}
                      AND cm.sortable_datetime >= toDateTime({{pb_1:Float64}}, {{pb_3:String}})
                      AND cm.sortable_datetime < toDateTime({{pb_2:Float64}}, {{pb_3:String}})
                      AND cm.deleted_at IS NULL
                    GROUP BY project_id,
                             id)) ARRAY
              JOIN JSONExtractKeysAndValuesRaw(ifNull(usage_raw, '{{}}')) AS kv)
           GROUP BY bucket,
                    model),
             all_models AS
          (SELECT DISTINCT model
           FROM aggregated_data)
        SELECT all_buckets.bucket AS timestamp,
               all_models.model,
               COALESCE(aggregated_data.sum_total_tokens, 0) AS sum_total_tokens,
               COALESCE(aggregated_data.count, 0) AS count
        FROM all_buckets
        CROSS JOIN all_models
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        AND all_models.model = aggregated_data.model
        ORDER BY all_buckets.bucket,
                 all_models.model
        """
    assert_usage_sql(
        req,
        metrics,
        expected_query,
        {
            "pb_0": "p",
            "pb_1": expected_pb_1,
            "pb_2": 1733054400.0,
            "pb_3": "UTC",
            "pb_4": granularity,
        },
        ["timestamp", "model", "sum_total_tokens", "count"],
        granularity,
    )


# NOTE: Call metrics tests are in test_call_metrics_query_builder.py
# NOTE: Cost metrics (input_cost, output_cost, total_cost) are computed post-query
# by multiplying token counts by prices from llm_token_prices table.
# There is no SQL test for cost metrics since they are not extracted via SQL.


# =============================================================================
# CALLS_COMPLETE TABLE TESTS
# =============================================================================
# These tests verify SQL generation for the calls_complete table which:
# - Uses started_at instead of sortable_datetime for datetime filtering/bucketing
# - Does not use anyIf aggregation (single row per call)
# - Does not use GROUP BY project_id, id
# =============================================================================


@pytest.mark.parametrize(
    ("metrics", "call_filter", "expected_query", "expected_columns", "expected_params"),
    [
        pytest.param(
            [
                UsageMetricSpec(
                    metric="total_tokens",
                    aggregations=[AggregationType.SUM, AggregationType.AVG],
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
                      model,
                      sumOrNull(m_total_tokens) AS sum_total_tokens,
                      avgOrNull(m_total_tokens) AS avg_total_tokens,
                      count() AS count
               FROM
                 (SELECT toStartOfInterval(started_at, INTERVAL 3600 SECOND, {pb_3:String}) AS bucket,
                         kv.1 AS model,
                         toFloat64OrNull(JSONExtractRaw(kv.2, 'total_tokens')) AS m_total_tokens
                  FROM
                    (SELECT started_at,
                            JSONExtractRaw(ifNull(summary_dump, '{}'), 'usage') AS usage_raw
                     FROM
                       (SELECT cm.started_at AS started_at,
                               cm.summary_dump AS summary_dump
                        FROM calls_complete AS cm
                        WHERE cm.project_id = {pb_0:String}
                          AND cm.started_at >= toDateTime({pb_1:Float64}, {pb_3:String})
                          AND cm.started_at < toDateTime({pb_2:Float64}, {pb_3:String})
                          AND cm.deleted_at = toDateTime64(0, 3) )) ARRAY
                  JOIN JSONExtractKeysAndValuesRaw(ifNull(usage_raw, '{}')) AS kv)
               GROUP BY bucket,
                        model),
                 all_models AS
              (SELECT DISTINCT model
               FROM aggregated_data)
            SELECT all_buckets.bucket AS timestamp,
                   all_models.model,
                   COALESCE(aggregated_data.sum_total_tokens, 0) AS sum_total_tokens,
                   COALESCE(aggregated_data.avg_total_tokens, 0) AS avg_total_tokens,
                   COALESCE(aggregated_data.count, 0) AS count
            FROM all_buckets
            CROSS JOIN all_models
            LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
            AND all_models.model = aggregated_data.model
            ORDER BY all_buckets.bucket,
                     all_models.model
            """,
            ["timestamp", "model", "sum_total_tokens", "avg_total_tokens", "count"],
            {
                "pb_0": "entity/project",
                "pb_1": 1733011200.0,
                "pb_2": 1733097600.0,
                "pb_3": "UTC",
                "pb_4": 3600,
            },
            id="basic",
        ),
        pytest.param(
            [UsageMetricSpec(metric="total_tokens")],
            CallsFilter(trace_roots_only=True),
            """
            WITH all_buckets AS
              (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
               FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}))) / {pb_4:Float64})))
               WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
                 aggregated_data AS
              (SELECT bucket,
                      model,
                      sumOrNull(m_total_tokens) AS sum_total_tokens,
                      count() AS count
               FROM
                 (SELECT toStartOfInterval(started_at, INTERVAL 3600 SECOND, {pb_3:String}) AS bucket,
                         kv.1 AS model,
                         toFloat64OrNull(JSONExtractRaw(kv.2, 'total_tokens')) AS m_total_tokens
                  FROM
                    (SELECT started_at,
                            JSONExtractRaw(ifNull(summary_dump, '{}'), 'usage') AS usage_raw
                     FROM
                       (SELECT cm.started_at AS started_at,
                               cm.summary_dump AS summary_dump
                        FROM calls_complete AS cm
                        WHERE cm.project_id = {pb_0:String}
                          AND cm.started_at >= toDateTime({pb_1:Float64}, {pb_3:String})
                          AND cm.started_at < toDateTime({pb_2:Float64}, {pb_3:String})
                          AND cm.deleted_at = toDateTime64(0, 3)
                          AND parent_id = {pb_5:String} )) ARRAY
                  JOIN JSONExtractKeysAndValuesRaw(ifNull(usage_raw, '{}')) AS kv)
               GROUP BY bucket,
                        model),
                 all_models AS
              (SELECT DISTINCT model
               FROM aggregated_data)
            SELECT all_buckets.bucket AS timestamp,
                   all_models.model,
                   COALESCE(aggregated_data.sum_total_tokens, 0) AS sum_total_tokens,
                   COALESCE(aggregated_data.count, 0) AS count
            FROM all_buckets
            CROSS JOIN all_models
            LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
            AND all_models.model = aggregated_data.model
            ORDER BY all_buckets.bucket,
                     all_models.model
            """,
            ["timestamp", "model", "sum_total_tokens", "count"],
            {
                "pb_0": "entity/project",
                "pb_1": 1733011200.0,
                "pb_2": 1733097600.0,
                "pb_3": "UTC",
                "pb_4": 3600,
                "pb_5": "",
            },
            id="trace_roots_only_sentinel",
        ),
        pytest.param(
            [UsageMetricSpec(metric="input_tokens")],
            CallsFilter(op_names=["openai.chat"]),
            """
            WITH all_buckets AS
              (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
               FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 3600 SECOND, {pb_3:String}))) / {pb_4:Float64})))
               WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
                 aggregated_data AS
              (SELECT bucket,
                      model,
                      sumOrNull(m_input_tokens) AS sum_input_tokens,
                      count() AS count
               FROM
                 (SELECT toStartOfInterval(started_at, INTERVAL 3600 SECOND, {pb_3:String}) AS bucket,
                         kv.1 AS model,
                         (ifNull(toFloat64OrNull(JSONExtractRaw(kv.2, 'prompt_tokens')), 0) + ifNull(toFloat64OrNull(JSONExtractRaw(kv.2, 'input_tokens')), 0)) AS m_input_tokens
                  FROM
                    (SELECT started_at,
                            JSONExtractRaw(ifNull(summary_dump, '{}'), 'usage') AS usage_raw
                     FROM
                       (SELECT cm.started_at AS started_at,
                               cm.summary_dump AS summary_dump
                        FROM calls_complete AS cm
                        WHERE cm.project_id = {pb_0:String}
                          AND cm.started_at >= toDateTime({pb_1:Float64}, {pb_3:String})
                          AND cm.started_at < toDateTime({pb_2:Float64}, {pb_3:String})
                          AND cm.deleted_at = toDateTime64(0, 3)
                          AND op_name IN {pb_5:Array(String)} )) ARRAY
                  JOIN JSONExtractKeysAndValuesRaw(ifNull(usage_raw, '{}')) AS kv)
               GROUP BY bucket,
                        model),
                 all_models AS
              (SELECT DISTINCT model
               FROM aggregated_data)
            SELECT all_buckets.bucket AS timestamp,
                   all_models.model,
                   COALESCE(aggregated_data.sum_input_tokens, 0) AS sum_input_tokens,
                   COALESCE(aggregated_data.count, 0) AS count
            FROM all_buckets
            CROSS JOIN all_models
            LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
            AND all_models.model = aggregated_data.model
            ORDER BY all_buckets.bucket,
                     all_models.model
            """,
            ["timestamp", "model", "sum_input_tokens", "count"],
            {
                "pb_0": "entity/project",
                "pb_1": 1733011200.0,
                "pb_2": 1733097600.0,
                "pb_3": "UTC",
                "pb_4": 3600,
                "pb_5": ["openai.chat"],
            },
            id="op_names_filter",
        ),
    ],
)
def test_calls_complete_table_variants(
    metrics: list[UsageMetricSpec],
    call_filter: CallsFilter | None,
    expected_query: str,
    expected_columns: list[str],
    expected_params: dict[str, object],
) -> None:
    req = CallStatsReq(
        project_id="entity/project",
        start=START_DT,
        end=END_DT,
        granularity=3600,
        filter=call_filter,
    )
    assert_usage_sql(
        req,
        metrics,
        expected_query,
        expected_params,
        expected_columns,
        3600,
        exp_start=START_DT,
        exp_end=END_DT,
        read_table=ReadTable.CALLS_COMPLETE,
    )
