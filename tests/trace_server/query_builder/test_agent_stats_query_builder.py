import datetime
from collections.abc import Callable

import pytest
import sqlparse
from pydantic import ValidationError

from weave.trace_server.agents.constants import MAX_AGENT_STATS_RESULT_ROWS
from weave.trace_server.agents.types import (
    AgentGroupByRef,
    AgentSpanGroupFilter,
    AgentSpanMeasureSpec,
    AgentSpanStatsMetricSpec,
    AgentSpanStatsNumericBucketSpec,
    AgentSpanStatsReq,
    AgentSpanValueRef,
)
from weave.trace_server.interface.query import Query
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.agent_stats_query_builder import (
    build_agent_span_stats_query,
)

_START = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
_END = datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc)
_AGENT_NAME_FILTER = Query.model_validate(
    {"$expr": {"$eq": [{"$getField": "agent.name"}, {"$literal": "agent-a"}]}}
)


def _req(**kwargs) -> AgentSpanStatsReq:
    defaults = {
        "project_id": "p1",
        "start": _START,
        "end": _END,
        "granularity": 3600,
        "metrics": [
            AgentSpanStatsMetricSpec(
                alias="input_tokens",
                value_type="number",
                value=AgentSpanValueRef(
                    source="field",
                    key="usage.input_tokens",
                ),
                aggregations=["sum"],
            )
        ],
    }
    defaults.update(kwargs)
    return AgentSpanStatsReq(**defaults)


def test_ungrouped_stats_query_full_sql_shape() -> None:
    pb = ParamBuilder("genai")
    req = _req(
        query=_AGENT_NAME_FILTER,
        metrics=[
            AgentSpanStatsMetricSpec(
                alias="duration_ms",
                value_type="number",
                value=AgentSpanValueRef(source="derived", key="duration_ms"),
                aggregations=["avg"],
                percentiles=[95],
            ),
            AgentSpanStatsMetricSpec(
                alias="errors",
                value_type="boolean",
                value=AgentSpanValueRef(source="derived", key="is_error"),
                aggregations=["count_true"],
            ),
        ],
    )

    result = build_agent_span_stats_query(req, pb)

    expected_sql = """
        WITH all_buckets AS (
          SELECT toStartOfInterval(
            toDateTime({genai_4:Float64}, {genai_6:String}),
            INTERVAL 3600 SECOND,
            {genai_6:String}
          ) + toIntervalSecond(number * {genai_7:Int64}) AS bucket
          FROM numbers(
            toUInt64(
              ceil(
                (
                  toUnixTimestamp(toDateTime({genai_5:Float64}, {genai_6:String})) -
                  toUnixTimestamp(
                    toStartOfInterval(
                      toDateTime({genai_4:Float64}, {genai_6:String}),
                      INTERVAL 3600 SECOND,
                      {genai_6:String}
                    )
                  )
                ) / {genai_7:Float64}
              )
            )
          )
          WHERE bucket < toDateTime({genai_5:Float64}, {genai_6:String})
        ),
        filtered_spans AS (
          SELECT *
          FROM spans s
          WHERE s.project_id = {genai_0:String}
            AND s.started_at >= {genai_1:DateTime64(6)}
            AND s.started_at < {genai_2:DateTime64(6)}
          AND (s.agent_name = {genai_3:String})
        ),
        aggregated_data AS (
          SELECT
            bucket,
            avgOrNull(if(v_duration_ms, m_duration_ms, NULL)) AS avg_duration_ms,
            quantileOrNull(0.95)(if(v_duration_ms, m_duration_ms, NULL)) AS p95_duration_ms,
            countIf(v_errors AND m_errors = 1) AS count_true_errors
          FROM (
            SELECT
              toStartOfInterval(s.started_at, INTERVAL 3600 SECOND, {genai_6:String}) AS bucket,
              if(
                s.ended_at > s.started_at,
                toFloat64(toUnixTimestamp64Milli(s.ended_at) - toUnixTimestamp64Milli(s.started_at)),
                NULL
              ) AS m_duration_ms,
              toUInt8(s.ended_at > s.started_at) AS v_duration_ms,
              s.status_code = 'ERROR' AS m_errors,
              toUInt8(1) AS v_errors
            FROM filtered_spans s
          )
          GROUP BY bucket
        )
        SELECT
          all_buckets.bucket AS timestamp,
          aggregated_data.avg_duration_ms AS avg_duration_ms,
          aggregated_data.p95_duration_ms AS p95_duration_ms,
          COALESCE(aggregated_data.count_true_errors, 0) AS count_true_errors
        FROM all_buckets
        LEFT JOIN aggregated_data
          ON all_buckets.bucket = aggregated_data.bucket
        ORDER BY timestamp
    """
    expected_params = {
        "genai_0": "p1",
        "genai_1": _START,
        "genai_2": _END,
        "genai_3": "agent-a",
        "genai_4": 1767225600.0,
        "genai_5": 1767312000.0,
        "genai_6": "UTC",
        "genai_7": 3600,
    }
    assert_sql(expected_sql, expected_params, result.sql, result.parameters)
    assert result.columns == [
        "timestamp",
        "avg_duration_ms",
        "p95_duration_ms",
        "count_true_errors",
    ]


@pytest.mark.parametrize(
    ("group_limit", "expected_group_limit_param"),
    [
        pytest.param(1000, 400, id="group_limit_capped"),
        pytest.param(None, 50, id="group_limit_default"),
    ],
)
def test_grouped_stats_query_full_sql_shape(
    group_limit: int | None, expected_group_limit_param: int
) -> None:
    pb = ParamBuilder("genai")
    extra = {} if group_limit is None else {"group_limit": group_limit}
    req = _req(
        group_by=[
            AgentGroupByRef(
                source="custom_attrs_string",
                key="env",
                alias="env",
            )
        ],
        metrics=[
            AgentSpanStatsMetricSpec(
                alias="score",
                value_type="number",
                value=AgentSpanValueRef(
                    source="custom_attrs_float",
                    key="score",
                ),
                aggregations=["avg", "count"],
            )
        ],
        **extra,
    )

    result = build_agent_span_stats_query(req, pb)

    expected_sql = """
        WITH all_buckets AS (
          SELECT toStartOfInterval(
            toDateTime({genai_5:Float64}, {genai_7:String}),
            INTERVAL 3600 SECOND,
            {genai_7:String}
          ) + toIntervalSecond(number * {genai_8:Int64}) AS bucket
          FROM numbers(
            toUInt64(
              ceil(
                (
                  toUnixTimestamp(toDateTime({genai_6:Float64}, {genai_7:String})) -
                  toUnixTimestamp(
                    toStartOfInterval(
                      toDateTime({genai_5:Float64}, {genai_7:String}),
                      INTERVAL 3600 SECOND,
                      {genai_7:String}
                    )
                  )
                ) / {genai_8:Float64}
              )
            )
          )
          WHERE bucket < toDateTime({genai_6:Float64}, {genai_7:String})
        ),
        filtered_spans AS (
          SELECT *
          FROM spans s
          WHERE s.project_id = {genai_0:String}
            AND s.started_at >= {genai_1:DateTime64(6)}
            AND s.started_at < {genai_2:DateTime64(6)}
        ),
        top_groups AS (
          SELECT if(mapContains(s.custom_attrs_string, {genai_3:String}), s.custom_attrs_string[{genai_3:String}], NULL) AS env
          FROM filtered_spans s
          GROUP BY env
          ORDER BY count() DESC
          LIMIT {genai_9:UInt64}
        ),
        aggregated_data AS (
          SELECT
            bucket,
            env,
            avgOrNull(if(v_score, m_score, NULL)) AS avg_score,
            countIf(v_score) AS count_score
          FROM (
            SELECT
              toStartOfInterval(s.started_at, INTERVAL 3600 SECOND, {genai_7:String}) AS bucket,
              if(mapContains(s.custom_attrs_string, {genai_3:String}), s.custom_attrs_string[{genai_3:String}], NULL) AS env,
              toFloat64(s.custom_attrs_float[{genai_4:String}]) AS m_score,
              toUInt8(mapContains(s.custom_attrs_float, {genai_4:String})) AS v_score
            FROM filtered_spans s
          )
          GROUP BY bucket, env
        )
        SELECT
          all_buckets.bucket AS timestamp,
          top_groups.env AS env,
          aggregated_data.avg_score AS avg_score,
          COALESCE(aggregated_data.count_score, 0) AS count_score
        FROM all_buckets
        CROSS JOIN top_groups
        LEFT JOIN aggregated_data
          ON all_buckets.bucket = aggregated_data.bucket
         AND top_groups.env = aggregated_data.env
        ORDER BY timestamp, env
    """
    expected_params = {
        "genai_0": "p1",
        "genai_1": _START,
        "genai_2": _END,
        "genai_3": "env",
        "genai_4": "score",
        "genai_5": 1767225600.0,
        "genai_6": 1767312000.0,
        "genai_7": "UTC",
        "genai_8": 3600,
        "genai_9": expected_group_limit_param,
    }
    assert_sql(expected_sql, expected_params, result.sql, result.parameters)
    assert result.columns == ["timestamp", "env", "avg_score", "count_score"]


@pytest.mark.parametrize(
    ("bucket_by", "metrics", "expected_sql", "extra_params", "expected_columns"),
    [
        pytest.param(
            AgentSpanStatsNumericBucketSpec(
                type="number",
                value=AgentSpanValueRef(source="derived", key="duration_ms"),
                bins=4,
            ),
            [
                AgentSpanStatsMetricSpec(
                    alias="spans",
                    value_type="boolean",
                    value=AgentSpanValueRef(source="derived", key="is_error"),
                    aggregations=["count"],
                )
            ],
            """
        WITH filtered_spans AS
          (SELECT *
           FROM spans s
           WHERE s.project_id = {genai_0:String}
             AND s.started_at >= {genai_1:DateTime64(6)}
             AND s.started_at < {genai_2:DateTime64(6)} ),
             value_rows AS
          (SELECT if(s.ended_at > s.started_at, toFloat64(toUnixTimestamp64Milli(s.ended_at) - toUnixTimestamp64Milli(s.started_at)), NULL) AS bucket_value,
                  s.status_code = 'ERROR' AS m_spans,
                  toUInt8(1) AS v_spans
           FROM filtered_spans s
           WHERE s.ended_at > s.started_at
             AND isNotNull(if(s.ended_at > s.started_at, toFloat64(toUnixTimestamp64Milli(s.ended_at) - toUnixTimestamp64Milli(s.started_at)), NULL))
             AND isFinite(if(s.ended_at > s.started_at, toFloat64(toUnixTimestamp64Milli(s.ended_at) - toUnixTimestamp64Milli(s.started_at)), NULL)) ),
             bounds AS
          (SELECT toFloat64(min(bucket_value)) AS bucket_min_bound,
                  toFloat64(max(bucket_value)) AS bucket_max_bound,
                  count() AS value_count
           FROM value_rows),
             all_buckets AS
          (SELECT toUInt64(number) AS bucket
           FROM numbers({genai_3:UInt64})),
             aggregated_data AS
          (SELECT if(bounds.bucket_max_bound = bounds.bucket_min_bound, toUInt64(0), toUInt64(least(toFloat64({genai_3:UInt64}) - 1.0, floor((value_rows.bucket_value - bounds.bucket_min_bound) / if(bounds.bucket_max_bound > bounds.bucket_min_bound, (bounds.bucket_max_bound - bounds.bucket_min_bound) / {genai_3:Float64}, 1.0))))) AS bucket,
                  countIf(v_spans) AS count_spans
           FROM value_rows
           CROSS JOIN bounds
           WHERE bounds.value_count > 0
             AND value_rows.bucket_value >= bounds.bucket_min_bound
             AND value_rows.bucket_value <= bounds.bucket_max_bound
           GROUP BY bucket)
        SELECT all_buckets.bucket AS bucket_index,
               if(bounds.bucket_max_bound = bounds.bucket_min_bound, bounds.bucket_min_bound, bounds.bucket_min_bound + toFloat64(all_buckets.bucket) * if(bounds.bucket_max_bound > bounds.bucket_min_bound, (bounds.bucket_max_bound - bounds.bucket_min_bound) / {genai_3:Float64}, 1.0)) AS bucket_min,
               if(bounds.bucket_max_bound = bounds.bucket_min_bound, bounds.bucket_max_bound, if(all_buckets.bucket = {genai_3:UInt64} - toUInt64(1), bounds.bucket_max_bound, bounds.bucket_min_bound + toFloat64(all_buckets.bucket + 1) * if(bounds.bucket_max_bound > bounds.bucket_min_bound, (bounds.bucket_max_bound - bounds.bucket_min_bound) / {genai_3:Float64}, 1.0))) AS bucket_max,
               COALESCE(aggregated_data.count_spans, 0) AS count_spans
        FROM all_buckets
        CROSS JOIN bounds
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        WHERE bounds.value_count > 0
          AND (bounds.bucket_max_bound > bounds.bucket_min_bound
               OR all_buckets.bucket = 0)
        ORDER BY bucket_index
    """,
            {"genai_3": 4},
            ["bucket_index", "bucket_min", "bucket_max", "count_spans"],
            id="value_buckets",
        ),
        pytest.param(
            AgentSpanStatsNumericBucketSpec(
                type="number",
                bins=8,
                group_by=[AgentGroupByRef(source="column", key="conversation_id")],
                measure=AgentSpanMeasureSpec(
                    alias="avg_score",
                    aggregation="avg",
                    value=AgentSpanValueRef(source="custom_attrs_float", key="score"),
                    value_type="number",
                ),
            ),
            [],
            """
        WITH filtered_spans AS
          (SELECT *
           FROM spans s
           WHERE s.project_id = {genai_0:String}
             AND s.started_at >= {genai_1:DateTime64(6)}
             AND s.started_at < {genai_2:DateTime64(6)} ),
             value_rows AS
          (SELECT avgOrNull(if((mapContains(s.custom_attrs_float, {genai_4:String})), toFloat64(s.custom_attrs_float[{genai_4:String}]), NULL)) AS bucket_value
           FROM filtered_spans s
           GROUP BY s.conversation_id),
             bounds AS
          (SELECT toFloat64(min(bucket_value)) AS bucket_min_bound,
                  toFloat64(max(bucket_value)) AS bucket_max_bound,
                  count() AS value_count
           FROM value_rows),
             all_buckets AS
          (SELECT toUInt64(number) AS bucket
           FROM numbers({genai_3:UInt64})),
             aggregated_data AS
          (SELECT if(bounds.bucket_max_bound = bounds.bucket_min_bound, toUInt64(0), toUInt64(least(toFloat64({genai_3:UInt64}) - 1.0, floor((value_rows.bucket_value - bounds.bucket_min_bound) / if(bounds.bucket_max_bound > bounds.bucket_min_bound, (bounds.bucket_max_bound - bounds.bucket_min_bound) / {genai_3:Float64}, 1.0))))) AS bucket,
                  count() AS count
           FROM value_rows
           CROSS JOIN bounds
           WHERE bounds.value_count > 0
             AND value_rows.bucket_value >= bounds.bucket_min_bound
             AND value_rows.bucket_value <= bounds.bucket_max_bound
           GROUP BY bucket)
        SELECT all_buckets.bucket AS bucket_index,
               if(bounds.bucket_max_bound = bounds.bucket_min_bound, bounds.bucket_min_bound, bounds.bucket_min_bound + toFloat64(all_buckets.bucket) * if(bounds.bucket_max_bound > bounds.bucket_min_bound, (bounds.bucket_max_bound - bounds.bucket_min_bound) / {genai_3:Float64}, 1.0)) AS bucket_min,
               if(bounds.bucket_max_bound = bounds.bucket_min_bound, bounds.bucket_max_bound, if(all_buckets.bucket = {genai_3:UInt64} - toUInt64(1), bounds.bucket_max_bound, bounds.bucket_min_bound + toFloat64(all_buckets.bucket + 1) * if(bounds.bucket_max_bound > bounds.bucket_min_bound, (bounds.bucket_max_bound - bounds.bucket_min_bound) / {genai_3:Float64}, 1.0))) AS bucket_max,
               COALESCE(aggregated_data.count, 0) AS count
        FROM all_buckets
        CROSS JOIN bounds
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        WHERE bounds.value_count > 0
          AND (bounds.bucket_max_bound > bounds.bucket_min_bound
               OR all_buckets.bucket = 0)
        ORDER BY bucket_index
    """,
            {"genai_3": 8, "genai_4": "score"},
            ["bucket_index", "bucket_min", "bucket_max", "count"],
            id="groups_custom_attr_measure",
        ),
    ],
)
def test_numeric_bucket_stats_query(
    bucket_by: AgentSpanStatsNumericBucketSpec,
    metrics: list[AgentSpanStatsMetricSpec],
    expected_sql: str,
    extra_params: dict,
    expected_columns: list[str],
) -> None:
    pb = ParamBuilder("genai")
    req = _req(bucket_by=bucket_by, metrics=metrics)

    result = build_agent_span_stats_query(req, pb)

    expected_params = {
        "genai_0": "p1",
        "genai_1": _START,
        "genai_2": _END,
        **extra_params,
    }
    assert_sql(expected_sql, expected_params, result.sql, result.parameters)
    assert result.columns == expected_columns
    assert result.granularity_seconds is None
    assert result.bucket_type == "number"


def test_numeric_bucket_group_filter_rejects_mismatched_group_by() -> None:
    pb = ParamBuilder("genai")
    req = _req(
        bucket_by=AgentSpanStatsNumericBucketSpec(
            type="number",
            bins=8,
            group_by=[AgentGroupByRef(source="column", key="conversation_id")],
            measure=AgentSpanMeasureSpec(
                alias="avg_score",
                aggregation="avg",
                value=AgentSpanValueRef(source="custom_attrs_float", key="score"),
                value_type="number",
            ),
        ),
        group_filters=[
            AgentSpanGroupFilter(
                group_by=[AgentGroupByRef(source="column", key="trace_id")],
                measure=AgentSpanMeasureSpec(alias="spans", aggregation="count"),
                min=1,
            )
        ],
        metrics=[],
    )

    with pytest.raises(
        ValueError,
        match="numeric bucket group_filters must use the same group_by",
    ):
        build_agent_span_stats_query(req, pb)


def test_time_stats_apply_group_filters() -> None:
    pb = ParamBuilder("genai")
    req = _req(
        metrics=[
            AgentSpanStatsMetricSpec(
                alias="conversations",
                value_type="string",
                value=AgentSpanValueRef(source="field", key="conversation_id"),
                aggregations=["count_distinct"],
            )
        ],
        group_filters=[
            AgentSpanGroupFilter(
                measure=AgentSpanMeasureSpec(
                    alias="total_tokens",
                    aggregation="sum",
                    value=AgentSpanValueRef(source="derived", key="total_tokens"),
                    value_type="number",
                ),
                min=10,
                max=100,
            )
        ],
    )

    result = build_agent_span_stats_query(req, pb)

    expected_sql = """
        WITH all_buckets AS
          (SELECT toStartOfInterval(toDateTime({genai_3:Float64}, {genai_5:String}), INTERVAL 3600 SECOND, {genai_5:String}) + toIntervalSecond(number * {genai_6:Int64}) AS bucket
           FROM numbers(toUInt64(ceil((toUnixTimestamp(toDateTime({genai_4:Float64}, {genai_5:String})) - toUnixTimestamp(toStartOfInterval(toDateTime({genai_3:Float64}, {genai_5:String}), INTERVAL 3600 SECOND, {genai_5:String}))) / {genai_6:Float64})))
           WHERE bucket < toDateTime({genai_4:Float64}, {genai_5:String}) ),
             filtered_spans AS
          (SELECT *
           FROM spans s
           WHERE s.project_id = {genai_0:String}
             AND s.started_at >= {genai_1:DateTime64(6)}
             AND s.started_at < {genai_2:DateTime64(6)} ),
             qualified_groups_0 AS
          (SELECT s.conversation_id AS conversation_id
           FROM filtered_spans s
           GROUP BY conversation_id
           HAVING sumOrNull(if((1), toFloat64(s.input_tokens + s.output_tokens + s.reasoning_tokens), NULL)) >= {genai_7:Float64}
           AND sumOrNull(if((1), toFloat64(s.input_tokens + s.output_tokens + s.reasoning_tokens), NULL)) <= {genai_8:Float64}),
             filtered_metric_spans AS
          (SELECT s.*
           FROM filtered_spans s
           INNER JOIN qualified_groups_0 q ON s.conversation_id = q.conversation_id),
             aggregated_data AS
          (SELECT bucket,
                  uniqExactIf(m_conversations, v_conversations) AS count_distinct_conversations
           FROM
             (SELECT toStartOfInterval(s.started_at, INTERVAL 3600 SECOND, {genai_5:String}) AS bucket,
                     s.conversation_id AS m_conversations,
                     toUInt8(1) AS v_conversations
              FROM filtered_metric_spans s)
           GROUP BY bucket)
        SELECT all_buckets.bucket AS timestamp,
               COALESCE(aggregated_data.count_distinct_conversations, 0) AS count_distinct_conversations
        FROM all_buckets
        LEFT JOIN aggregated_data ON all_buckets.bucket = aggregated_data.bucket
        ORDER BY timestamp
    """
    expected_params = {
        "genai_0": "p1",
        "genai_1": _START,
        "genai_2": _END,
        "genai_3": 1767225600.0,
        "genai_4": 1767312000.0,
        "genai_5": "UTC",
        "genai_6": 3600,
        "genai_7": 10.0,
        "genai_8": 100.0,
    }
    assert_sql(expected_sql, expected_params, result.sql, result.parameters)


def test_group_by_caps_output_rows() -> None:
    pb = ParamBuilder("genai")
    req = _req(
        group_by=[
            AgentGroupByRef(
                source="custom_attrs_string",
                key="env",
                alias="env",
            )
        ],
        group_limit=1000,
    )

    result = build_agent_span_stats_query(req, pb)

    expected_bucket_count = 25
    expected_group_limit = MAX_AGENT_STATS_RESULT_ROWS // expected_bucket_count
    assert expected_group_limit in result.parameters.values()
    assert 1000 not in result.parameters.values()


def test_request_validation_normalizes_naive_datetimes() -> None:
    start = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    req = _req(start=start, end=None)

    assert req.start.tzinfo == datetime.timezone.utc
    assert req.end is None


@pytest.mark.parametrize(
    ("build", "match"),
    [
        pytest.param(
            lambda: _req(
                bucket_by=AgentSpanStatsNumericBucketSpec(
                    type="number",
                    group_by=[AgentGroupByRef(source="column", key="conversation_id")],
                    measure=AgentSpanMeasureSpec(alias="spans", aggregation="count"),
                ),
                metrics=[
                    AgentSpanStatsMetricSpec(
                        alias="input_tokens",
                        value_type="number",
                        value=AgentSpanValueRef(
                            source="field", key="usage.input_tokens"
                        ),
                        aggregations=["sum"],
                    )
                ],
            ),
            "grouped numeric bucket stats do not support explicit metrics",
            id="grouped_numeric_bucket_with_metrics",
        ),
        pytest.param(
            lambda: AgentSpanStatsMetricSpec(
                alias="agent",
                value_type="string",
                value=AgentSpanValueRef(source="field", key="agent.name"),
                aggregations=["sum"],
            ),
            None,
            id="invalid_type_aggregation",
        ),
        pytest.param(
            lambda: _req(
                metrics=[
                    AgentSpanStatsMetricSpec(
                        alias="tokens",
                        value_type="number",
                        value=AgentSpanValueRef(
                            source="field",
                            key="usage.input_tokens",
                        ),
                        aggregations=["sum"],
                    ),
                    AgentSpanStatsMetricSpec(
                        alias="tokens",
                        value_type="number",
                        value=AgentSpanValueRef(
                            source="field",
                            key="usage.output_tokens",
                        ),
                        aggregations=["sum"],
                    ),
                ]
            ),
            None,
            id="duplicate_aliases",
        ),
        pytest.param(
            lambda: AgentSpanStatsNumericBucketSpec(
                type="number",
                value=AgentSpanValueRef(source="derived", key="is_error"),
            ),
            None,
            id="non_numeric_derived_field",
        ),
        pytest.param(
            lambda: _req(
                bucket_by=AgentSpanStatsNumericBucketSpec(
                    type="number",
                    value=AgentSpanValueRef(source="derived", key="duration_ms"),
                ),
                group_by=[
                    AgentGroupByRef(
                        source="field",
                        key="agent.name",
                    )
                ],
            ),
            None,
            id="numeric_bucket_with_group_by",
        ),
        pytest.param(
            lambda: _req(
                end=datetime.datetime(2026, 2, 15, tzinfo=datetime.timezone.utc),
            ),
            None,
            id="large_range",
        ),
    ],
)
def test_request_validation_errors(
    build: Callable[[], object], match: str | None
) -> None:
    with pytest.raises(ValidationError, match=match):
        build()


def assert_sql(
    expected_query: str,
    expected_params: dict,
    query: str,
    params: dict,
) -> None:
    expected_formatted = sqlparse.format(expected_query, reindent=True).strip()
    found_formatted = sqlparse.format(query, reindent=True).strip()

    assert expected_formatted == found_formatted, (
        f"\nExpected:\n{expected_formatted}\n\nGot:\n{found_formatted}"
    )
    assert expected_params == params, (
        f"\nExpected params: {expected_params}\n\nGot params: {params}"
    )
