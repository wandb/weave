import datetime

import pytest
import sqlparse
from pydantic import ValidationError

from weave.trace_server.agents.constants import MAX_AGENT_STATS_RESULT_ROWS
from weave.trace_server.agents.types import (
    AgentGroupByRef,
    AgentSpanStatsFieldRef,
    AgentSpanStatsMetricSpec,
    AgentSpanStatsReq,
)
from weave.trace_server.interface.query import Query
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.agent_stats_query_builder import (
    build_agent_span_stats_query,
)


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


def _req(**kwargs) -> AgentSpanStatsReq:
    defaults = {
        "project_id": "p1",
        "start": datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        "end": datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
        "granularity": 3600,
        "metrics": [
            AgentSpanStatsMetricSpec(
                alias="input_tokens",
                value_type="number",
                field=AgentSpanStatsFieldRef(
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
        query=Query.model_validate(
            {
                "$expr": {
                    "$eq": [
                        {"$getField": "agent.name"},
                        {"$literal": "agent-a"},
                    ]
                }
            }
        ),
        metrics=[
            AgentSpanStatsMetricSpec(
                alias="duration_ms",
                value_type="number",
                derived="duration_ms",
                aggregations=["avg"],
                percentiles=[95],
            ),
            AgentSpanStatsMetricSpec(
                alias="errors",
                value_type="boolean",
                derived="is_error",
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
        "genai_1": datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        "genai_2": datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
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


def test_grouped_stats_query_full_sql_shape() -> None:
    pb = ParamBuilder("genai")
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
                field=AgentSpanStatsFieldRef(
                    source="custom_attrs_float",
                    key="score",
                ),
                aggregations=["avg", "count"],
            )
        ],
        group_limit=1000,
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
          SELECT s.custom_attrs_string[{genai_3:String}] AS env
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
              s.custom_attrs_string[{genai_3:String}] AS env,
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
        "genai_1": datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        "genai_2": datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
        "genai_3": "env",
        "genai_4": "score",
        "genai_5": 1767225600.0,
        "genai_6": 1767312000.0,
        "genai_7": "UTC",
        "genai_8": 3600,
        "genai_9": 400,
    }
    assert_sql(expected_sql, expected_params, result.sql, result.parameters)
    assert result.columns == ["timestamp", "env", "avg_score", "count_score"]


def test_basic_stats_query_uses_query_filter_and_bucket() -> None:
    pb = ParamBuilder("genai")
    req = _req(
        query=Query.model_validate(
            {
                "$expr": {
                    "$eq": [
                        {"$getField": "agent.name"},
                        {"$literal": "agent-a"},
                    ]
                }
            }
        ),
        metrics=[
            AgentSpanStatsMetricSpec(
                alias="duration_ms",
                value_type="number",
                derived="duration_ms",
                aggregations=["avg"],
                percentiles=[95],
            ),
            AgentSpanStatsMetricSpec(
                alias="errors",
                value_type="boolean",
                derived="is_error",
                aggregations=["count_true"],
            ),
        ],
    )

    result = build_agent_span_stats_query(req, pb)
    sql = " ".join(result.sql.split())

    assert "FROM spans s" in result.sql
    assert "s.agent_name = {genai_3:String}" in result.sql
    assert "toStartOfInterval(s.started_at, INTERVAL 3600 SECOND" in result.sql
    assert "avgOrNull(if(v_duration_ms, m_duration_ms, NULL)) AS avg_duration_ms" in sql
    assert (
        "quantileOrNull(0.95)(if(v_duration_ms, m_duration_ms, NULL)) AS p95_duration_ms"
        in sql
    )
    assert "aggregated_data.avg_duration_ms AS avg_duration_ms" in sql
    assert "COALESCE(aggregated_data.avg_duration_ms, 0)" not in sql
    assert "countIf(v_errors AND m_errors = 1) AS count_true_errors" in sql
    assert result.columns == [
        "timestamp",
        "avg_duration_ms",
        "p95_duration_ms",
        "count_true_errors",
    ]


def test_group_by_custom_attr_and_metric_custom_attr() -> None:
    pb = ParamBuilder("genai")
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
                field=AgentSpanStatsFieldRef(
                    source="custom_attrs_float",
                    key="score",
                ),
                aggregations=["avg", "count"],
            )
        ],
    )

    result = build_agent_span_stats_query(req, pb)
    sql = " ".join(result.sql.split())

    assert "top_groups AS" in result.sql
    assert "s.custom_attrs_string[{genai_3:String}] AS env" in result.sql
    assert "s.custom_attrs_float[{genai_4:String}]" in result.sql
    assert "mapContains(s.custom_attrs_float, {genai_4:String})" in result.sql
    assert "GROUP BY bucket, env" in sql
    assert "LIMIT {genai_9:UInt64}" in result.sql
    assert result.columns == ["timestamp", "env", "avg_score", "count_score"]


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


def test_metric_validation_rejects_invalid_type_aggregation() -> None:
    with pytest.raises(ValidationError):
        AgentSpanStatsMetricSpec(
            alias="agent",
            value_type="string",
            field=AgentSpanStatsFieldRef(source="field", key="agent.name"),
            aggregations=["sum"],
        )


def test_request_validation_rejects_duplicate_aliases() -> None:
    with pytest.raises(ValidationError):
        _req(
            metrics=[
                AgentSpanStatsMetricSpec(
                    alias="tokens",
                    value_type="number",
                    field=AgentSpanStatsFieldRef(
                        source="field",
                        key="usage.input_tokens",
                    ),
                    aggregations=["sum"],
                ),
                AgentSpanStatsMetricSpec(
                    alias="tokens",
                    value_type="number",
                    field=AgentSpanStatsFieldRef(
                        source="field",
                        key="usage.output_tokens",
                    ),
                    aggregations=["sum"],
                ),
            ]
        )


def test_request_validation_rejects_large_range() -> None:
    with pytest.raises(ValidationError):
        _req(
            end=datetime.datetime(2026, 2, 15, tzinfo=datetime.timezone.utc),
        )
