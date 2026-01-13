import datetime

from tests.trace_server.query_builder.utils import assert_usage_sql
from weave.trace_server.trace_server_interface import (
    AggregationType,
    CallsFilter,
    CallStatsReq,
    UsageMetricSpec,
)


def test_explicit_start_end():
    start_dt = datetime.datetime(2024, 12, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    end_dt = datetime.datetime(2024, 12, 2, 0, 0, 0, tzinfo=datetime.timezone.utc)
    metrics = [
        UsageMetricSpec(
            metric="total_tokens",
            aggregations=[AggregationType.SUM, AggregationType.AVG],
        )
    ]
    req = CallStatsReq(
        project_id="entity/project",
        start=start_dt,
        end=end_dt,
        granularity=3600,
    )
    assert_usage_sql(
        req,
        metrics,
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
        {
            "pb_0": "entity/project",
            "pb_1": 1733011200.0,
            "pb_2": 1733097600.0,
            "pb_3": "UTC",
            "pb_4": 3600,
        },
        ["timestamp", "model", "sum_total_tokens", "avg_total_tokens", "count"],
        3600,
        exp_start=start_dt,
        exp_end=end_dt,
    )


def test_op_names_filter():
    start_dt = datetime.datetime(2024, 12, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    end_dt = datetime.datetime(2024, 12, 2, 0, 0, 0, tzinfo=datetime.timezone.utc)
    metrics = [UsageMetricSpec(metric="total_tokens")]
    req = CallStatsReq(
        project_id="entity/project",
        start=start_dt,
        end=end_dt,
        granularity=3600,
        filter=CallsFilter(op_names=["openai.chat", "anthropic.messages"]),
    )
    assert_usage_sql(
        req,
        metrics,
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
                      AND op_name IN {pb_5:Array(String)}
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
        {
            "pb_0": "entity/project",
            "pb_1": 1733011200.0,
            "pb_2": 1733097600.0,
            "pb_3": "UTC",
            "pb_4": 3600,
            "pb_5": ["openai.chat", "anthropic.messages"],
        },
        ["timestamp", "model", "sum_total_tokens", "count"],
        3600,
        exp_start=start_dt,
        exp_end=end_dt,
    )


def test_all_aggregation_types():
    start_dt = datetime.datetime(2024, 12, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    end_dt = datetime.datetime(2024, 12, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
    metrics = [
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
    ]
    req = CallStatsReq(
        project_id="entity/project",
        start=start_dt,
        end=end_dt,
        granularity=300,
    )
    assert_usage_sql(
        req,
        metrics,
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
        {
            "pb_0": "entity/project",
            "pb_1": 1733011200.0,
            "pb_2": 1733014800.0,
            "pb_3": "UTC",
            "pb_4": 300,
        },
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
        300,
        exp_start=start_dt,
        exp_end=end_dt,
    )


def test_custom_percentiles():
    start_dt = datetime.datetime(2024, 12, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    end_dt = datetime.datetime(2024, 12, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
    metrics = [
        UsageMetricSpec(
            metric="output_tokens",
            aggregations=[],
            percentiles=[50, 75, 90, 95, 99, 99.9],
        )
    ]
    req = CallStatsReq(
        project_id="entity/project",
        start=start_dt,
        end=end_dt,
        granularity=300,
    )
    assert_usage_sql(
        req,
        metrics,
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
        {
            "pb_0": "entity/project",
            "pb_1": 1733011200.0,
            "pb_2": 1733014800.0,
            "pb_3": "UTC",
            "pb_4": 300,
        },
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
        300,
        exp_start=start_dt,
        exp_end=end_dt,
    )


def test_multiple_metrics():
    start_dt = datetime.datetime(2024, 12, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    end_dt = datetime.datetime(2024, 12, 2, 0, 0, 0, tzinfo=datetime.timezone.utc)
    metrics = [
        UsageMetricSpec(metric="input_tokens", aggregations=[AggregationType.SUM]),
        UsageMetricSpec(metric="output_tokens", aggregations=[AggregationType.SUM]),
        UsageMetricSpec(metric="total_tokens", aggregations=[AggregationType.AVG]),
    ]
    req = CallStatsReq(
        project_id="entity/project",
        start=start_dt,
        end=end_dt,
        granularity=3600,
    )
    assert_usage_sql(
        req,
        metrics,
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
        {
            "pb_0": "entity/project",
            "pb_1": 1733011200.0,
            "pb_2": 1733097600.0,
            "pb_3": "UTC",
            "pb_4": 3600,
        },
        [
            "timestamp",
            "model",
            "sum_input_tokens",
            "sum_output_tokens",
            "avg_total_tokens",
            "count",
        ],
        3600,
        exp_start=start_dt,
        exp_end=end_dt,
    )


def test_mixed_aggregations_and_percentiles():
    start_dt = datetime.datetime(2024, 12, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    end_dt = datetime.datetime(2024, 12, 2, 0, 0, 0, tzinfo=datetime.timezone.utc)
    metrics = [
        UsageMetricSpec(
            metric="total_tokens",
            aggregations=[AggregationType.SUM, AggregationType.AVG],
            percentiles=[50, 95, 99],
        )
    ]
    req = CallStatsReq(
        project_id="entity/project",
        start=start_dt,
        end=end_dt,
        granularity=3600,
    )
    assert_usage_sql(
        req,
        metrics,
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
        {
            "pb_0": "entity/project",
            "pb_1": 1733011200.0,
            "pb_2": 1733097600.0,
            "pb_3": "UTC",
            "pb_4": 3600,
        },
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
        3600,
        exp_start=start_dt,
        exp_end=end_dt,
    )


def test_granularity_auto_selection():
    """Test that granularity is automatically selected based on time range."""
    now = datetime.datetime(2024, 12, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)

    metrics = [UsageMetricSpec(metric="total_tokens")]

    # < 2 hours -> 5 minutes (300 seconds)
    req = CallStatsReq(
        project_id="p",
        start=now - datetime.timedelta(hours=1),
        end=now,
    )
    assert_usage_sql(
        req,
        metrics,
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
        {
            "pb_0": "p",
            "pb_1": 1733050800.0,
            "pb_2": 1733054400.0,
            "pb_3": "UTC",
            "pb_4": 300,
        },
        ["timestamp", "model", "sum_total_tokens", "count"],
        300,
    )

    # 2-12 hours -> 1 hour (3600 seconds)
    req = CallStatsReq(
        project_id="p",
        start=now - datetime.timedelta(hours=6),
        end=now,
    )
    assert_usage_sql(
        req,
        metrics,
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
               COALESCE(aggregated_data.count, 0) AS count
        FROM all_buckets
        CROSS JOIN all_models
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        AND all_models.model = aggregated_data.model
        ORDER BY all_buckets.bucket,
                 all_models.model
        """,
        {
            "pb_0": "p",
            "pb_1": 1733032800.0,
            "pb_2": 1733054400.0,
            "pb_3": "UTC",
            "pb_4": 3600,
        },
        ["timestamp", "model", "sum_total_tokens", "count"],
        3600,
    )

    # 12h - 3 days -> 6 hours (21600 seconds)
    req = CallStatsReq(
        project_id="p",
        start=now - datetime.timedelta(days=2),
        end=now,
    )
    assert_usage_sql(
        req,
        metrics,
        """
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 21600 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 21600 SECOND, {pb_3:String}))) / {pb_4:Float64})))
           WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
             aggregated_data AS
          (SELECT bucket,
                  model,
                  sumOrNull(m_total_tokens) AS sum_total_tokens,
                  count() AS count
           FROM
             (SELECT toStartOfInterval(sortable_datetime, INTERVAL 21600 SECOND, {pb_3:String}) AS bucket,
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
        {
            "pb_0": "p",
            "pb_1": 1732881600.0,
            "pb_2": 1733054400.0,
            "pb_3": "UTC",
            "pb_4": 21600,
        },
        ["timestamp", "model", "sum_total_tokens", "count"],
        21600,
    )

    # 3-14 days -> 12 hours (43200 seconds)
    req = CallStatsReq(
        project_id="p",
        start=now - datetime.timedelta(days=10),
        end=now,
    )
    assert_usage_sql(
        req,
        metrics,
        """
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 43200 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 43200 SECOND, {pb_3:String}))) / {pb_4:Float64})))
           WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
             aggregated_data AS
          (SELECT bucket,
                  model,
                  sumOrNull(m_total_tokens) AS sum_total_tokens,
                  count() AS count
           FROM
             (SELECT toStartOfInterval(sortable_datetime, INTERVAL 43200 SECOND, {pb_3:String}) AS bucket,
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
        {
            "pb_0": "p",
            "pb_1": 1732190400.0,
            "pb_2": 1733054400.0,
            "pb_3": "UTC",
            "pb_4": 43200,
        },
        ["timestamp", "model", "sum_total_tokens", "count"],
        43200,
    )

    # > 14 days -> 1 day (86400 seconds)
    req = CallStatsReq(
        project_id="p",
        start=now - datetime.timedelta(days=30),
        end=now,
    )
    assert_usage_sql(
        req,
        metrics,
        """
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 86400 SECOND, {pb_3:String}) + toIntervalSecond(number * {pb_4:Int64}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({pb_2:Float64}, {pb_3:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({pb_1:Float64}, {pb_3:String}), INTERVAL 86400 SECOND, {pb_3:String}))) / {pb_4:Float64})))
           WHERE bucket < toDateTime({pb_2:Float64}, {pb_3:String}) ),
             aggregated_data AS
          (SELECT bucket,
                  model,
                  sumOrNull(m_total_tokens) AS sum_total_tokens,
                  count() AS count
           FROM
             (SELECT toStartOfInterval(sortable_datetime, INTERVAL 86400 SECOND, {pb_3:String}) AS bucket,
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
        {
            "pb_0": "p",
            "pb_1": 1730462400.0,
            "pb_2": 1733054400.0,
            "pb_3": "UTC",
            "pb_4": 86400,
        },
        ["timestamp", "model", "sum_total_tokens", "count"],
        86400,
    )


def test_explicit_granularity_overrides_auto():
    start_dt = datetime.datetime(2024, 12, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    end_dt = datetime.datetime(2024, 12, 2, 0, 0, 0, tzinfo=datetime.timezone.utc)
    metrics = [UsageMetricSpec(metric="total_tokens")]
    req = CallStatsReq(
        project_id="entity/project",
        start=start_dt,
        end=end_dt,
        granularity=300,
    )
    assert_usage_sql(
        req,
        metrics,
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
        {
            "pb_0": "entity/project",
            "pb_1": 1733011200.0,
            "pb_2": 1733097600.0,
            "pb_3": "UTC",
            "pb_4": 300,
        },
        ["timestamp", "model", "sum_total_tokens", "count"],
        300,
        exp_start=start_dt,
        exp_end=end_dt,
    )


def test_trace_roots_only_filter():
    start_dt = datetime.datetime(2024, 12, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    end_dt = datetime.datetime(2024, 12, 2, 0, 0, 0, tzinfo=datetime.timezone.utc)
    metrics = [UsageMetricSpec(metric="total_tokens")]
    req = CallStatsReq(
        project_id="entity/project",
        start=start_dt,
        end=end_dt,
        granularity=3600,
        filter=CallsFilter(trace_roots_only=True),
    )
    assert_usage_sql(
        req,
        metrics,
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
                      AND parent_id IS NULL
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
        {
            "pb_0": "entity/project",
            "pb_1": 1733011200.0,
            "pb_2": 1733097600.0,
            "pb_3": "UTC",
            "pb_4": 3600,
        },
        ["timestamp", "model", "sum_total_tokens", "count"],
        3600,
        exp_start=start_dt,
        exp_end=end_dt,
    )


def test_trace_ids_filter():
    start_dt = datetime.datetime(2024, 12, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    end_dt = datetime.datetime(2024, 12, 2, 0, 0, 0, tzinfo=datetime.timezone.utc)
    metrics = [UsageMetricSpec(metric="total_tokens")]
    req = CallStatsReq(
        project_id="entity/project",
        start=start_dt,
        end=end_dt,
        granularity=3600,
        filter=CallsFilter(trace_ids=["trace_abc", "trace_def"]),
    )
    assert_usage_sql(
        req,
        metrics,
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
                      AND trace_id IN {pb_5:Array(String)}
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
        {
            "pb_0": "entity/project",
            "pb_1": 1733011200.0,
            "pb_2": 1733097600.0,
            "pb_3": "UTC",
            "pb_4": 3600,
            "pb_5": ["trace_abc", "trace_def"],
        },
        ["timestamp", "model", "sum_total_tokens", "count"],
        3600,
        exp_start=start_dt,
        exp_end=end_dt,
    )


def test_wb_user_ids_filter():
    start_dt = datetime.datetime(2024, 12, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    end_dt = datetime.datetime(2024, 12, 2, 0, 0, 0, tzinfo=datetime.timezone.utc)
    metrics = [UsageMetricSpec(metric="total_tokens")]
    req = CallStatsReq(
        project_id="entity/project",
        start=start_dt,
        end=end_dt,
        granularity=3600,
        filter=CallsFilter(wb_user_ids=["user_123"]),
    )
    assert_usage_sql(
        req,
        metrics,
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
                      AND wb_user_id IN {pb_5:Array(String)}
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
        {
            "pb_0": "entity/project",
            "pb_1": 1733011200.0,
            "pb_2": 1733097600.0,
            "pb_3": "UTC",
            "pb_4": 3600,
            "pb_5": ["user_123"],
        },
        ["timestamp", "model", "sum_total_tokens", "count"],
        3600,
        exp_start=start_dt,
        exp_end=end_dt,
    )


# NOTE: Call metrics tests are in test_call_metrics_query_builder.py
# NOTE: Cost metrics (input_cost, output_cost, total_cost) are computed post-query
# by multiplying token counts by prices from llm_token_prices table.
# There is no SQL test for cost metrics since they are not extracted via SQL.
