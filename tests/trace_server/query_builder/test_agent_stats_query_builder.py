import datetime

import pytest
from pydantic import ValidationError

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
