"""SQL shape assertions for every ``make_*_query`` function in the agent
query builder.

Each test builds a ``ParamBuilder``, calls the builder, and compares the full
formatted SQL + param dict against an expected value, matching the style of
``test_annotation_queues_query_builder.py`` etc.
"""

import datetime
from collections.abc import Callable

import pytest
import sqlparse
from pydantic import ValidationError

from weave.trace_server.agents.types import (
    AgentConversationChatReq,
    AgentCustomAttrsSchemaReq,
    AgentGroupByRef,
    AgentSearchReq,
    AgentSortBy,
    AgentSpanGroupDistributionSpec,
    AgentSpanGroupFilter,
    AgentSpanMeasureSpec,
    AgentSpansQueryReq,
    AgentSpanValueRef,
    AgentsQueryFilters,
    AgentsQueryReq,
    AgentVersionsQueryReq,
)
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.interface.query import Query
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.agent_query_builder import (
    CHAT_VIEW_COLS,
    SPAN_SORTABLE_COLS,
    SPANS_DETAILS_COLS,
    SPANS_LIST_COLS,
    build_order_by,
    make_agent_versions_count_query,
    make_agent_versions_list_query,
    make_agents_count_query,
    make_agents_list_query,
    make_conversation_chat_spans_query,
    make_conversation_chat_turns_count_query,
    make_conversation_previews_query,
    make_custom_attrs_schema_query,
    make_message_search_query,
    make_span_group_categorical_distributions_query,
    make_span_group_numeric_distributions_query,
    make_spans_count_query,
    make_spans_list_query,
    make_trace_detail_spans_query,
    resolve_group_by,
)

#: The fixed aggregate tail emitted by the grouped list query, as it would
#: appear after ``SELECT <group_cols>,``. Used to keep test expected SQL
#: readable without duplicating the bundle across every test.
_GROUPED_AGG_TAIL = """count() AS span_count,
               countIf(s.operation_name = 'invoke_agent') AS invocation_count,
               uniqExact(s.conversation_id) AS conversation_count,
               sum(s.input_tokens) AS total_input_tokens,
               sum(s.cache_creation_input_tokens) AS total_cache_creation_input_tokens,
               sum(s.cache_read_input_tokens) AS total_cache_read_input_tokens,
               sum(s.output_tokens) AS total_output_tokens,
               sum(s.reasoning_tokens) AS total_reasoning_tokens,
               sum(toUnixTimestamp64Milli(s.ended_at) - toUnixTimestamp64Milli(s.started_at)) AS total_duration_ms,
               countIf(s.status_code = 'ERROR') AS error_count,
               groupUniqArray(s.agent_name) AS agent_names,
               groupUniqArray(s.agent_version) AS agent_versions,
               groupUniqArray(s.provider_name) AS provider_names,
               groupUniqArray(s.request_model) AS request_models,
               groupUniqArray(s.conversation_name) AS conversation_names,
               min(s.started_at) AS first_seen,
               max(s.started_at) AS last_seen"""

_START = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
_END = datetime.datetime(2026, 2, 1, tzinfo=datetime.timezone.utc)
_MESSAGE_SEARCH_SELECT = """SELECT conversation_id, conversation_name, agent_name,
                   span_id, trace_id, role,
                   substring(content, 1, 500) AS content,
                   lower(hex(content_digest)) AS content_digest, started_at"""
_CUSTOM_ATTRS_SCHEMA_SELECT = """SELECT tupleElement(attr, 1) AS source,
                   tupleElement(attr, 2) AS key,
                   tupleElement(attr, 3) AS value_type,
                   count() AS span_count"""
_CUSTOM_ATTRS_SCHEMA_ARRAY_JOIN = """ARRAY JOIN arrayConcat(
                arrayMap(k -> tuple('custom_attrs_string', k, 'string'), filtered.custom_attrs_string_keys),
                arrayMap(k -> tuple('custom_attrs_int', k, 'int'), filtered.custom_attrs_int_keys),
                arrayMap(k -> tuple('custom_attrs_float', k, 'float'), filtered.custom_attrs_float_keys),
                arrayMap(k -> tuple('custom_attrs_bool', k, 'bool'), filtered.custom_attrs_bool_keys)
            ) AS attr
            GROUP BY source, key, value_type
            ORDER BY span_count DESC, key ASC, source ASC"""


# ============================================================================
# make_spans_count_query (ungrouped)
# ============================================================================


@pytest.mark.parametrize(
    ("req", "expected", "expected_params"),
    [
        pytest.param(
            AgentSpansQueryReq(project_id="p1"),
            "SELECT count() FROM spans s WHERE s.project_id = {genai_0:String}",
            {"genai_0": "p1"},
            id="basic",
        ),
        pytest.param(
            AgentSpansQueryReq(
                project_id="p1",
                query=Query.model_validate(
                    {
                        "$expr": {
                            "$and": [
                                {
                                    "$eq": [
                                        {"$getField": "agent.name"},
                                        {"$literal": "bot"},
                                    ]
                                },
                                {
                                    "$eq": [
                                        {"$getField": "custom_attrs_string.env"},
                                        {"$literal": "prod"},
                                    ]
                                },
                            ]
                        }
                    }
                ),
                started_after=_START,
                started_before=_END,
            ),
            """
            SELECT count() FROM spans s
            WHERE s.project_id = {genai_0:String}
              AND s.started_at >= {genai_1:DateTime64(6)}
              AND s.started_at < {genai_2:DateTime64(6)}
            AND ((s.agent_name = {genai_3:String}) AND (if(mapContains(s.custom_attrs_string, {genai_4:String}), s.custom_attrs_string[{genai_4:String}], NULL) = {genai_5:String}))
        """,
            {
                "genai_0": "p1",
                "genai_1": _START,
                "genai_2": _END,
                "genai_3": "bot",
                "genai_4": "env",
                "genai_5": "prod",
            },
            id="with_query_and_time",
        ),
    ],
)
def test_make_spans_count_query(
    req: AgentSpansQueryReq, expected: str, expected_params: dict
) -> None:
    pb = ParamBuilder("genai")
    query = make_spans_count_query(pb, req)
    assert_sql(expected, expected_params, query, pb.get_params())


@pytest.mark.parametrize(
    ("query", "expected_match"),
    [
        pytest.param(
            Query.model_construct(
                expr_=tsi_query.NotOperation.model_construct(not_=())
            ),
            "Empty \\$not",
            id="empty_not",
        ),
        pytest.param(
            Query.model_validate(
                {
                    "$expr": {
                        "$gt": [
                            {"$getField": "input_tokens"},
                            {"$literal": None},
                        ]
                    }
                }
            ),
            "Null values are not allowed",
            id="null_non_eq_comparison",
        ),
        pytest.param(
            Query.model_validate(
                {
                    "$expr": {
                        "$in": [
                            {"$getField": "agent_name"},
                            [{"$literal": "bot"}, {"$literal": 1}],
                        ]
                    }
                }
            ),
            "same type",
            id="mixed_in_literal_types",
        ),
    ],
)
def test_make_spans_count_query_rejects_bad_filter(
    query: Query, expected_match: str
) -> None:
    pb = ParamBuilder("genai")
    with pytest.raises(ValueError, match=expected_match):
        make_spans_count_query(pb, AgentSpansQueryReq(project_id="p1", query=query))


# ============================================================================
# make_spans_list_query (ungrouped)
# ============================================================================


@pytest.mark.parametrize(
    ("req", "expected", "expected_params"),
    [
        pytest.param(
            AgentSpansQueryReq(project_id="p1"),
            f"""
            SELECT {SPANS_LIST_COLS}
            FROM spans s
            WHERE s.project_id = {{genai_0:String}}
            ORDER BY started_at DESC
            LIMIT {{genai_1:UInt64}} OFFSET {{genai_2:UInt64}}
        """,
            {"genai_0": "p1", "genai_1": 100, "genai_2": 0},
            id="basic",
        ),
        pytest.param(
            AgentSpansQueryReq(
                project_id="p1",
                sort_by=[AgentSortBy(field="input_tokens", direction="asc")],
            ),
            f"""
            SELECT {SPANS_LIST_COLS}
            FROM spans s
            WHERE s.project_id = {{genai_0:String}}
            ORDER BY input_tokens asc
            LIMIT {{genai_1:UInt64}} OFFSET {{genai_2:UInt64}}
        """,
            {"genai_0": "p1", "genai_1": 100, "genai_2": 0},
            id="custom_sort",
        ),
        pytest.param(
            AgentSpansQueryReq(
                project_id="p1",
                custom_attr_columns=[
                    AgentSpanValueRef(source="custom_attrs_float", key="score")
                ],
                sort_by=[
                    AgentSortBy(field="custom_attrs_float.score", direction="desc")
                ],
            ),
            f"""
            SELECT {SPANS_LIST_COLS}, mapFilter((k, v) -> has({{genai_4:Array(String)}}, k), s.custom_attrs_float) AS custom_attrs_float
            FROM spans s
            WHERE s.project_id = {{genai_0:String}}
            ORDER BY if(mapContains(s.custom_attrs_float, {{genai_3:String}}), toFloat64(s.custom_attrs_float[{{genai_3:String}}]), NULL) desc
            LIMIT {{genai_1:UInt64}} OFFSET {{genai_2:UInt64}}
        """,
            {
                "genai_0": "p1",
                "genai_1": 100,
                "genai_2": 0,
                "genai_3": "score",
                "genai_4": ["score"],
            },
            id="custom_attr_columns_projected_and_sorted",
        ),
        pytest.param(
            AgentSpansQueryReq(project_id="p1", include_details=True),
            f"""
            SELECT {SPANS_LIST_COLS}, {SPANS_DETAILS_COLS}
            FROM spans s
            WHERE s.project_id = {{genai_0:String}}
            ORDER BY started_at DESC
            LIMIT {{genai_1:UInt64}} OFFSET {{genai_2:UInt64}}
        """,
            {"genai_0": "p1", "genai_1": 100, "genai_2": 0},
            id="include_details_projects_detail_columns",
        ),
        pytest.param(
            AgentSpansQueryReq(project_id="p1", limit=0),
            f"""
            SELECT {SPANS_LIST_COLS}
            FROM spans s
            WHERE s.project_id = {{genai_0:String}}
            ORDER BY started_at DESC
            LIMIT {{genai_1:UInt64}} OFFSET {{genai_2:UInt64}}
        """,
            {"genai_0": "p1", "genai_1": 0, "genai_2": 0},
            id="limit_zero_is_honored",
        ),
    ],
)
def test_make_spans_list_query(
    req: AgentSpansQueryReq, expected: str, expected_params: dict
) -> None:
    pb = ParamBuilder("genai")
    query = make_spans_list_query(pb, req)
    assert_sql(expected, expected_params, query, pb.get_params())


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({"limit": 99999}, id="limit_above_max"),
        pytest.param({"limit": -1}, id="limit_negative"),
        pytest.param({"offset": -1}, id="offset_negative"),
    ],
)
def test_spans_query_req_rejects_limit_offset(kwargs: dict) -> None:
    with pytest.raises(ValidationError):
        AgentSpansQueryReq(project_id="p1", **kwargs)


@pytest.mark.parametrize(
    "extra_kwargs",
    [
        pytest.param(
            {
                "custom_attr_columns": [
                    AgentSpanValueRef(source="custom_attrs_string", key="env")
                ]
            },
            id="custom_attr_columns_with_group_by",
        ),
        pytest.param({"include_details": True}, id="include_details_with_group_by"),
    ],
)
def test_spans_query_req_rejects_ungrouped_only_fields_with_group_by(
    extra_kwargs: dict,
) -> None:
    """custom_attr_columns and include_details only project on the ungrouped
    path; the validator rejects pairing them with group_by instead of silently
    dropping the projection.
    """
    with pytest.raises(ValidationError):
        AgentSpansQueryReq(
            project_id="p1",
            group_by=[AgentGroupByRef(source="column", key="agent_name")],
            **extra_kwargs,
        )


# ============================================================================
# make_conversation_previews_query
# ============================================================================


def test_conversation_previews_scoped_to_conversation_ids() -> None:
    pb = ParamBuilder("genai")
    query = make_conversation_previews_query(pb, "p1", ["conv-a", "conv-b"])
    expected = """
        SELECT s.conversation_id AS conversation_id,
               argMinIf(s.input_messages, s.started_at, length(s.input_messages) > 0) AS first_input_messages,
               argMaxIf(s.output_messages, s.ended_at, length(s.output_messages) > 0) AS last_output_messages
        FROM spans s
        WHERE s.project_id = {genai_0:String} AND s.conversation_id IN {genai_1:Array(String)}
        GROUP BY conversation_id
    """
    assert_sql(
        expected,
        {"genai_0": "p1", "genai_1": ["conv-a", "conv-b"]},
        query,
        pb.get_params(),
    )


def test_conversation_previews_applies_time_range() -> None:
    pb = ParamBuilder("genai")
    start = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    end = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc)
    query = make_conversation_previews_query(
        pb, "p1", ["conv-a"], started_after=start, started_before=end
    )
    expected = """
        SELECT s.conversation_id AS conversation_id,
               argMinIf(s.input_messages, s.started_at, length(s.input_messages) > 0) AS first_input_messages,
               argMaxIf(s.output_messages, s.ended_at, length(s.output_messages) > 0) AS last_output_messages
        FROM spans s
        WHERE s.project_id = {genai_0:String} AND s.conversation_id IN {genai_1:Array(String)}
          AND s.started_at >= {genai_2:DateTime64(6)}
          AND s.started_at < {genai_3:DateTime64(6)}
        GROUP BY conversation_id
    """
    assert_sql(
        expected,
        {
            "genai_0": "p1",
            "genai_1": ["conv-a"],
            "genai_2": start,
            "genai_3": end,
        },
        query,
        pb.get_params(),
    )


# ============================================================================
# make_spans_count_query (grouped)
# ============================================================================


@pytest.mark.parametrize(
    ("group_by", "expected", "expected_params"),
    [
        pytest.param(
            AgentGroupByRef(source="column", key="trace_id"),
            """
            SELECT count() FROM (
                SELECT s.trace_id FROM spans s
                WHERE s.project_id = {genai_0:String}
                GROUP BY s.trace_id
            )
        """,
            {"genai_0": "p1"},
            id="group_by_column",
        ),
        pytest.param(
            AgentGroupByRef(source="custom_attrs_string", key="env"),
            """
            SELECT count() FROM (
                SELECT if(mapContains(s.custom_attrs_string, {genai_1:String}), s.custom_attrs_string[{genai_1:String}], NULL) FROM spans s
                WHERE s.project_id = {genai_0:String}
                GROUP BY if(mapContains(s.custom_attrs_string, {genai_1:String}), s.custom_attrs_string[{genai_1:String}], NULL)
            )
        """,
            {"genai_0": "p1", "genai_1": "env"},
            id="group_by_custom_attr",
        ),
    ],
)
def test_make_grouped_spans_count_query(
    group_by: AgentGroupByRef, expected: str, expected_params: dict
) -> None:
    pb = ParamBuilder("genai")
    query = make_spans_count_query(
        pb, AgentSpansQueryReq(project_id="p1", group_by=[group_by])
    )
    assert_sql(expected, expected_params, query, pb.get_params())


# ============================================================================
# make_spans_list_query (grouped)
# ============================================================================


@pytest.mark.parametrize(
    ("req", "expected", "expected_params"),
    [
        pytest.param(
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[AgentGroupByRef(source="column", key="trace_id")],
            ),
            f"""
            SELECT s.trace_id AS trace_id,
                   {_GROUPED_AGG_TAIL}
            FROM spans s
            WHERE s.project_id = {{genai_0:String}}
            GROUP BY trace_id
            ORDER BY last_seen DESC
            LIMIT {{genai_1:UInt64}} OFFSET {{genai_2:UInt64}}
        """,
            {"genai_0": "p1", "genai_1": 100, "genai_2": 0},
            id="group_by_trace_id",
        ),
        pytest.param(
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[AgentGroupByRef(source="column", key="conversation_id")],
                started_after=_START,
                started_before=_END,
            ),
            f"""
            SELECT s.conversation_id AS conversation_id,
                   {_GROUPED_AGG_TAIL}
            FROM spans s
            WHERE s.project_id = {{genai_0:String}}
              AND s.started_at >= {{genai_1:DateTime64(6)}}
              AND s.started_at < {{genai_2:DateTime64(6)}}
            GROUP BY conversation_id
            ORDER BY last_seen DESC
            LIMIT {{genai_3:UInt64}} OFFSET {{genai_4:UInt64}}
        """,
            {
                "genai_0": "p1",
                "genai_1": _START,
                "genai_2": _END,
                "genai_3": 100,
                "genai_4": 0,
            },
            id="group_by_conversation_id_with_time",
        ),
        pytest.param(
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[AgentGroupByRef(source="custom_attrs_string", key="env")],
            ),
            f"""
            SELECT if(mapContains(s.custom_attrs_string, {{genai_3:String}}), s.custom_attrs_string[{{genai_3:String}}], NULL) AS env,
                   {_GROUPED_AGG_TAIL}
            FROM spans s
            WHERE s.project_id = {{genai_0:String}}
            GROUP BY env
            ORDER BY last_seen DESC
            LIMIT {{genai_1:UInt64}} OFFSET {{genai_2:UInt64}}
        """,
            {
                "genai_0": "p1",
                "genai_1": 100,
                "genai_2": 0,
                "genai_3": "env",
            },
            id="group_by_custom_attr",
        ),
        pytest.param(
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[
                    AgentGroupByRef(source="field", key="agent.name"),
                    AgentGroupByRef(source="column", key="request_model"),
                ],
                sort_by=[AgentSortBy(field="agent_name", direction="asc")],
            ),
            f"""
            SELECT s.agent_name AS agent_name,
                   s.request_model AS request_model,
                   {_GROUPED_AGG_TAIL}
            FROM spans s
            WHERE s.project_id = {{genai_0:String}}
            GROUP BY agent_name, request_model
            ORDER BY agent_name asc
            LIMIT {{genai_1:UInt64}} OFFSET {{genai_2:UInt64}}
        """,
            {"genai_0": "p1", "genai_1": 100, "genai_2": 0},
            id="group_by_multi_column_and_sort_by_alias",
        ),
        pytest.param(
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[AgentGroupByRef(source="column", key="conversation_id")],
                measures=[
                    AgentSpanMeasureSpec(alias="spans", aggregation="count"),
                    AgentSpanMeasureSpec(
                        alias="tool_calls",
                        aggregation="count",
                        filter=Query.model_validate(
                            {
                                "$expr": {
                                    "$eq": [
                                        {"$getField": "operation_name"},
                                        {"$literal": "execute_tool"},
                                    ]
                                }
                            }
                        ),
                    ),
                    AgentSpanMeasureSpec(
                        alias="avg_score",
                        aggregation="avg",
                        value=AgentSpanValueRef(
                            source="custom_attrs_float",
                            key="score",
                        ),
                        value_type="number",
                    ),
                ],
                group_filters=[
                    AgentSpanGroupFilter(
                        measure=AgentSpanMeasureSpec(
                            alias="avg_score",
                            aggregation="avg",
                            value=AgentSpanValueRef(
                                source="custom_attrs_float",
                                key="score",
                            ),
                            value_type="number",
                        ),
                        min=0.5,
                    )
                ],
                sort_by=[AgentSortBy(field="avg_score", direction="desc")],
            ),
            """
            SELECT s.conversation_id AS conversation_id,
                   {_GROUPED_AGG_TAIL},
                   count() AS spans,
                   countIf(((s.operation_name = {genai_3:String}))) AS tool_calls,
                   avgOrNull(if((mapContains(s.custom_attrs_float, {genai_4:String})), toFloat64(s.custom_attrs_float[{genai_4:String}]), NULL)) AS avg_score
            FROM spans s
            WHERE s.project_id = {genai_0:String}
            GROUP BY conversation_id
            HAVING avgOrNull(if((mapContains(s.custom_attrs_float, {genai_5:String})), toFloat64(s.custom_attrs_float[{genai_5:String}]), NULL)) >= {genai_6:Float64}
            ORDER BY avg_score desc
            LIMIT {genai_1:UInt64} OFFSET {genai_2:UInt64}
        """,
            {
                "genai_0": "p1",
                "genai_1": 100,
                "genai_2": 0,
                "genai_3": "execute_tool",
                "genai_4": "score",
                "genai_5": "score",
                "genai_6": 0.5,
            },
            id="dynamic_measures_filter_and_sort",
        ),
        pytest.param(
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[AgentGroupByRef(source="column", key="conversation_id")],
                measures=[
                    AgentSpanMeasureSpec(
                        alias="flagged_count",
                        aggregation="count_true",
                        value=AgentSpanValueRef(
                            source="custom_attrs_bool",
                            key="flagged",
                        ),
                    )
                ],
            ),
            """
            SELECT s.conversation_id AS conversation_id,
                   {_GROUPED_AGG_TAIL},
                   countIf((mapContains(s.custom_attrs_bool, {genai_3:String})) AND s.custom_attrs_bool[{genai_3:String}] = 1) AS flagged_count
            FROM spans s
            WHERE s.project_id = {genai_0:String}
            GROUP BY conversation_id
            ORDER BY flagged_count DESC
            LIMIT {genai_1:UInt64} OFFSET {genai_2:UInt64}
        """,
            {
                "genai_0": "p1",
                "genai_1": 100,
                "genai_2": 0,
                "genai_3": "flagged",
            },
            id="dynamic_measure_infers_boolean_count_true",
        ),
    ],
)
def test_make_grouped_spans_list_query(
    req: AgentSpansQueryReq, expected: str, expected_params: dict
) -> None:
    pb = ParamBuilder("genai")
    query = make_spans_list_query(pb, req)
    expected = expected.replace("{_GROUPED_AGG_TAIL}", _GROUPED_AGG_TAIL)
    assert_sql(expected, expected_params, query, pb.get_params())


@pytest.mark.parametrize(
    ("measures", "expected_match"),
    [
        pytest.param(
            [
                AgentSpanMeasureSpec(
                    alias="span_count",
                    aggregation="count",
                )
            ],
            "measure aliases collide with grouped row fields: \\['span_count'\\]",
            id="alias_collides_with_fixed_field",
        ),
        pytest.param(
            [
                AgentSpanMeasureSpec(
                    alias="conversation_id",
                    aggregation="count",
                )
            ],
            "measure aliases collide with grouped row fields: \\['conversation_id'\\]",
            id="alias_collides_with_group_key",
        ),
    ],
)
def test_spans_query_req_rejects_measure_alias_collision(
    measures: list[AgentSpanMeasureSpec], expected_match: str
) -> None:
    with pytest.raises(ValidationError, match=expected_match):
        AgentSpansQueryReq(
            project_id="p1",
            group_by=[AgentGroupByRef(source="column", key="conversation_id")],
            measures=measures,
        )


@pytest.mark.parametrize(
    ("req", "expected_match"),
    [
        pytest.param(
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[AgentGroupByRef(source="column", key="conversation_id")],
                measures=[
                    AgentSpanMeasureSpec(
                        alias="bad_sum",
                        aggregation="sum",
                        value=AgentSpanValueRef(
                            source="custom_attrs_string",
                            key="score",
                        ),
                    )
                ],
            ),
            "not valid for value_type 'string'",
            id="invalid_resolved_aggregation",
        ),
        pytest.param(
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[AgentGroupByRef(source="column", key="conversation_id")],
                measures=[AgentSpanMeasureSpec(alias="spans", aggregation="count")],
                group_filters=[
                    AgentSpanGroupFilter(
                        measure=AgentSpanMeasureSpec(
                            alias="spans",
                            aggregation="count",
                        ),
                        min=datetime.datetime(2026, 1, 1),
                    )
                ],
            ),
            "datetime group filter bounds require a datetime measure",
            id="mismatched_datetime_bound",
        ),
        pytest.param(
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[AgentGroupByRef(source="column", key="conversation_id")],
                measures=[AgentSpanMeasureSpec(alias="spans", aggregation="count")],
                group_filters=[
                    AgentSpanGroupFilter(
                        group_by=[AgentGroupByRef(source="column", key="trace_id")],
                        measure=AgentSpanMeasureSpec(
                            alias="spans",
                            aggregation="count",
                        ),
                        min=1,
                    )
                ],
            ),
            "spans list group_filters must use the same group_by",
            id="mismatched_group_by",
        ),
    ],
)
def test_make_grouped_spans_list_query_builder_errors(
    req: AgentSpansQueryReq, expected_match: str
) -> None:
    pb = ParamBuilder("genai")
    with pytest.raises(ValueError, match=expected_match):
        make_spans_list_query(pb, req)


# ============================================================================
# make_span_group_*_distribution_query
# ============================================================================


def test_numeric_distributions_query_batches_specs() -> None:
    pb = ParamBuilder("genai")
    query = make_span_group_numeric_distributions_query(
        pb,
        AgentSpansQueryReq(
            project_id="p1",
            group_by=[AgentGroupByRef(source="column", key="conversation_id")],
        ),
        ["conv-a", None, 12],
        [
            AgentSpanGroupDistributionSpec(
                alias="score_distribution",
                value=AgentSpanValueRef(source="custom_attrs_float", key="score"),
                bins=4,
            ),
            AgentSpanGroupDistributionSpec(
                alias="latency_distribution",
                value=AgentSpanValueRef(source="custom_attrs_int", key="latency"),
                bins=3,
            ),
        ],
    )

    expected = """
        WITH
          value_rows AS (
            SELECT group_key,
                   alias,
                   bins,
                   value
            FROM (
              SELECT toString(s.conversation_id) AS group_key,
                     tupleElement(spec, 1) AS alias,
                     tupleElement(spec, 4) AS bins,
                     multiIf(tupleElement(spec, 2) = 'custom_attrs_int', toFloat64(s.custom_attrs_int[tupleElement(spec, 3)]), tupleElement(spec, 2) = 'custom_attrs_float', toFloat64(s.custom_attrs_float[tupleElement(spec, 3)]), NULL) AS value
              FROM spans s
              ARRAY JOIN array(tuple({genai_2:String}, {genai_3:String}, {genai_4:String}, {genai_5:UInt64}), tuple({genai_6:String}, {genai_7:String}, {genai_8:String}, {genai_9:UInt64})) AS spec
              WHERE s.project_id = {genai_0:String}
                AND toString(s.conversation_id) IN {genai_1:Array(String)}
                AND multiIf(tupleElement(spec, 2) = 'custom_attrs_int', mapContains(s.custom_attrs_int, tupleElement(spec, 3)), tupleElement(spec, 2) = 'custom_attrs_float', mapContains(s.custom_attrs_float, tupleElement(spec, 3)), false)
            )
            WHERE isNotNull(value)
              AND isFinite(value)
          ),
          bounds AS (
            SELECT group_key,
                   alias,
                   bins,
                   min(value) AS min_value,
                   max(value) AS max_value,
                   count() AS present_count
            FROM value_rows
            GROUP BY group_key, alias, bins
          ),
          all_buckets AS (
            SELECT group_key,
                   alias,
                   bins,
                   toUInt64(bucket_index) AS bucket_index
            FROM bounds
            ARRAY JOIN range(bins) AS bucket_index
          ),
          aggregated AS (
            SELECT value_rows.group_key AS group_key,
                   value_rows.alias AS alias,
                   if(bounds.max_value = bounds.min_value, toUInt64(0), toUInt64(least(toFloat64(bounds.bins) - 1.0, floor((value_rows.value - bounds.min_value) / if(bounds.max_value > bounds.min_value, (bounds.max_value - bounds.min_value) / toFloat64(bounds.bins), 1.0))))) AS bucket_index,
                   count() AS bin_count
            FROM value_rows
            INNER JOIN bounds
              ON value_rows.group_key = bounds.group_key
             AND value_rows.alias = bounds.alias
            GROUP BY group_key, alias, bucket_index
          )
        SELECT bounds.group_key AS group_key,
               bounds.alias AS alias,
               all_buckets.bucket_index AS bucket_index,
               if(bounds.max_value = bounds.min_value, bounds.min_value, bounds.min_value + toFloat64(all_buckets.bucket_index) * if(bounds.max_value > bounds.min_value, (bounds.max_value - bounds.min_value) / toFloat64(bounds.bins), 1.0)) AS bucket_min,
               if(bounds.max_value = bounds.min_value, bounds.max_value, if(all_buckets.bucket_index = bounds.bins - toUInt64(1), bounds.max_value, bounds.min_value + toFloat64(all_buckets.bucket_index + 1) * if(bounds.max_value > bounds.min_value, (bounds.max_value - bounds.min_value) / toFloat64(bounds.bins), 1.0))) AS bucket_max,
               ifNull(aggregated.bin_count, 0) AS count,
               bounds.present_count AS present_count
        FROM bounds
        INNER JOIN all_buckets
          ON all_buckets.group_key = bounds.group_key
         AND all_buckets.alias = bounds.alias
        LEFT JOIN aggregated
          ON aggregated.group_key = bounds.group_key
         AND aggregated.alias = bounds.alias
         AND aggregated.bucket_index = all_buckets.bucket_index
        WHERE bounds.present_count > 0
          AND (
            bounds.max_value > bounds.min_value
            OR all_buckets.bucket_index = 0
          )
        ORDER BY group_key ASC, alias ASC, bucket_index ASC
    """
    expected_params = {
        "genai_0": "p1",
        "genai_1": ["conv-a", "", "12"],
        "genai_2": "score_distribution",
        "genai_3": "custom_attrs_float",
        "genai_4": "score",
        "genai_5": 4,
        "genai_6": "latency_distribution",
        "genai_7": "custom_attrs_int",
        "genai_8": "latency",
        "genai_9": 3,
    }
    assert_sql(expected, expected_params, query, pb.get_params())


def test_categorical_distributions_query_batches_specs() -> None:
    pb = ParamBuilder("genai")
    query = make_span_group_categorical_distributions_query(
        pb,
        AgentSpansQueryReq(
            project_id="p1",
            group_by=[AgentGroupByRef(source="column", key="conversation_id")],
        ),
        ["conv-a"],
        [
            AgentSpanGroupDistributionSpec(
                alias="env_distribution",
                value=AgentSpanValueRef(source="custom_attrs_string", key="env"),
                top_n=2,
            ),
            AgentSpanGroupDistributionSpec(
                alias="cached_distribution",
                value=AgentSpanValueRef(source="custom_attrs_bool", key="cached"),
                top_n=2,
            ),
        ],
    )

    expected = """
        WITH
          value_counts AS (
            SELECT group_key,
                   alias,
                   raw_value,
                   top_n,
                   count() AS value_count
            FROM (
              SELECT toString(s.conversation_id) AS group_key,
                     tupleElement(spec, 1) AS alias,
                     tupleElement(spec, 4) AS top_n,
                     multiIf(tupleElement(spec, 2) = 'custom_attrs_bool', if(s.custom_attrs_bool[tupleElement(spec, 3)] = 1, 'true', 'false'), tupleElement(spec, 2) = 'custom_attrs_string', toString(s.custom_attrs_string[tupleElement(spec, 3)]), '') AS raw_value
              FROM spans s
              ARRAY JOIN array(tuple({genai_2:String}, {genai_3:String}, {genai_4:String}, {genai_5:UInt64}), tuple({genai_6:String}, {genai_7:String}, {genai_8:String}, {genai_9:UInt64})) AS spec
              WHERE s.project_id = {genai_0:String}
                AND toString(s.conversation_id) IN {genai_1:Array(String)}
                AND multiIf(tupleElement(spec, 2) = 'custom_attrs_string', mapContains(s.custom_attrs_string, tupleElement(spec, 3)), tupleElement(spec, 2) = 'custom_attrs_bool', mapContains(s.custom_attrs_bool, tupleElement(spec, 3)), false)
            )
            GROUP BY group_key, alias, raw_value, top_n
          ),
          ranked AS (
            SELECT group_key,
                   alias,
                   raw_value,
                   top_n,
                   value_count,
                   sum(value_count) OVER (
                     PARTITION BY group_key, alias
                   ) AS present_count,
                   row_number() OVER (
                     PARTITION BY group_key, alias
                     ORDER BY value_count DESC, raw_value ASC
                   ) AS value_rank
            FROM value_counts
          )
        SELECT group_key,
               alias,
               substring(raw_value, 1, 256) AS value,
               value_count AS count,
               present_count
        FROM ranked
        WHERE value_rank <= top_n
        ORDER BY group_key ASC, alias ASC, count DESC, raw_value ASC
    """
    expected_params = {
        "genai_0": "p1",
        "genai_1": ["conv-a"],
        "genai_2": "env_distribution",
        "genai_3": "custom_attrs_string",
        "genai_4": "env",
        "genai_5": 2,
        "genai_6": "cached_distribution",
        "genai_7": "custom_attrs_bool",
        "genai_8": "cached",
        "genai_9": 2,
    }
    assert_sql(expected, expected_params, query, pb.get_params())


# ============================================================================
# resolve_group_by validation
# ============================================================================


@pytest.mark.parametrize(
    ("refs", "expected_match"),
    [
        pytest.param(
            [AgentGroupByRef(source="column", key="raw_span_dump")],
            "not in the allowlist",
            id="non_allowlisted_column",
        ),
        pytest.param(
            [
                AgentGroupByRef(source="field", key="agent.name"),
                AgentGroupByRef(source="column", key="agent_name"),
            ],
            "duplicate group_by alias",
            id="duplicate_alias",
        ),
        pytest.param(
            [
                AgentGroupByRef(
                    source="custom_attrs_string",
                    key="has spaces",
                    alias="bad alias",
                )
            ],
            "must match",
            id="invalid_alias",
        ),
    ],
)
def test_resolve_group_by_rejects(
    refs: list[AgentGroupByRef], expected_match: str
) -> None:
    pb = ParamBuilder("genai")
    with pytest.raises(ValueError, match=expected_match):
        resolve_group_by(pb, refs)


@pytest.mark.parametrize(
    ("refs", "expected"),
    [
        pytest.param(
            [AgentGroupByRef(source="field", key="agent.name")],
            [("s.agent_name", "agent_name")],
            id="field_source_resolves_semconv_key",
        ),
        pytest.param(
            [AgentGroupByRef(source="custom_attrs_string", key="env")],
            [
                (
                    "if(mapContains(s.custom_attrs_string, {genai_0:String}), "
                    "s.custom_attrs_string[{genai_0:String}], NULL)",
                    "env",
                )
            ],
            id="defaults_alias_to_key_when_valid",
        ),
        pytest.param(
            [
                AgentGroupByRef(
                    source="custom_attrs_string",
                    key="has spaces",
                    alias="spaced_attr",
                )
            ],
            [
                (
                    "if(mapContains(s.custom_attrs_string, {genai_0:String}), "
                    "s.custom_attrs_string[{genai_0:String}], NULL)",
                    "spaced_attr",
                )
            ],
            id="custom_alias_used_when_key_non_identifier",
        ),
    ],
)
def test_resolve_group_by_success(
    refs: list[AgentGroupByRef], expected: list[tuple[str, str]]
) -> None:
    pb = ParamBuilder("genai")
    assert resolve_group_by(pb, refs) == expected


# ============================================================================
# make_trace_detail_spans_query (internal helper — chat view only)
# ============================================================================


def test_make_trace_detail_spans_query() -> None:
    pb = ParamBuilder("genai")
    query = make_trace_detail_spans_query(pb, "p1", "t1")

    expected = f"""
        SELECT {CHAT_VIEW_COLS} FROM spans s
        WHERE s.project_id = {{genai_0:String}}
        AND s.trace_id = {{genai_1:String}}
        ORDER BY s.started_at ASC
    """
    assert_sql(
        expected,
        {"genai_0": "p1", "genai_1": "t1"},
        query,
        pb.get_params(),
    )


# ============================================================================
# make_agents_count_query / make_agents_list_query
# ============================================================================

_AGENTS_LIST_SELECT = """SELECT agent_name,
               sum(invocation_count) AS invocation_count,
               sum(span_count) AS span_count,
               sum(total_input_tokens) AS total_input_tokens,
               sum(total_output_tokens) AS total_output_tokens,
               sum(total_duration_ms) AS total_duration_ms,
               sum(error_count) AS error_count,
               min(first_seen) AS first_seen,
               max(last_seen) AS last_seen"""


@pytest.mark.parametrize(
    ("builder", "req", "expected", "expected_params"),
    [
        pytest.param(
            make_agents_count_query,
            AgentsQueryReq(project_id="p1"),
            """
            SELECT count() FROM (
                SELECT agent_name FROM agents
                WHERE project_id = {genai_0:String}
                GROUP BY agent_name
            )
        """,
            {"genai_0": "p1"},
            id="count_basic",
        ),
        pytest.param(
            make_agents_list_query,
            AgentsQueryReq(project_id="p1"),
            f"""
            {_AGENTS_LIST_SELECT}
            FROM agents
            WHERE project_id = {{genai_0:String}}
            GROUP BY agent_name
            ORDER BY last_seen DESC, agent_name
            LIMIT {{genai_1:UInt64}} OFFSET {{genai_2:UInt64}}
        """,
            {"genai_0": "p1", "genai_1": 100, "genai_2": 0},
            id="list_basic",
        ),
        pytest.param(
            make_agents_list_query,
            AgentsQueryReq(
                project_id="p1",
                filters=AgentsQueryFilters(agent_name="my-agent"),
            ),
            f"""
            {_AGENTS_LIST_SELECT}
            FROM agents
            WHERE project_id = {{genai_0:String}}
            AND agent_name = {{genai_1:String}}
            GROUP BY agent_name
            ORDER BY last_seen DESC, agent_name
            LIMIT {{genai_2:UInt64}} OFFSET {{genai_3:UInt64}}
        """,
            {
                "genai_0": "p1",
                "genai_1": "my-agent",
                "genai_2": 100,
                "genai_3": 0,
            },
            id="list_with_filter",
        ),
    ],
)
def test_make_agents_queries(
    builder: Callable[[ParamBuilder, AgentsQueryReq], str],
    req: AgentsQueryReq,
    expected: str,
    expected_params: dict,
) -> None:
    pb = ParamBuilder("genai")
    query = builder(pb, req)
    assert_sql(expected, expected_params, query, pb.get_params())


# ============================================================================
# make_custom_attrs_schema_query
# ============================================================================


@pytest.mark.parametrize(
    ("req", "where_clause", "expected_params"),
    [
        pytest.param(
            AgentCustomAttrsSchemaReq(project_id="p1"),
            "WHERE s.project_id = {genai_0:String}",
            {"genai_0": "p1", "genai_1": 201, "genai_2": 0},
            id="basic",
        ),
        pytest.param(
            AgentCustomAttrsSchemaReq(
                project_id="p1",
                query=Query.model_validate(
                    {
                        "$expr": {
                            "$eq": [
                                {"$getField": "agent.name"},
                                {"$literal": "bot"},
                            ]
                        }
                    }
                ),
                started_after=_START,
                limit=10,
                offset=20,
            ),
            """WHERE s.project_id = {genai_0:String}
                AND s.started_at >= {genai_1:DateTime64(6)}
                AND (s.agent_name = {genai_2:String})""",
            {
                "genai_0": "p1",
                "genai_1": _START,
                "genai_2": "bot",
                "genai_3": 11,
                "genai_4": 20,
            },
            id="reuses_spans_filters",
        ),
    ],
)
def test_make_custom_attrs_schema_query(
    req: AgentCustomAttrsSchemaReq, where_clause: str, expected_params: dict
) -> None:
    pb = ParamBuilder("genai")
    query = make_custom_attrs_schema_query(pb, req)
    limit_idx = len(expected_params) - 2
    expected = f"""
        {_CUSTOM_ATTRS_SCHEMA_SELECT}
        FROM (
            SELECT s.custom_attrs_string.keys AS custom_attrs_string_keys,
                   s.custom_attrs_int.keys AS custom_attrs_int_keys,
                   s.custom_attrs_float.keys AS custom_attrs_float_keys,
                   s.custom_attrs_bool.keys AS custom_attrs_bool_keys
            FROM spans s
            {where_clause}
        ) filtered
        {_CUSTOM_ATTRS_SCHEMA_ARRAY_JOIN}
        LIMIT {{genai_{limit_idx}:UInt64}} OFFSET {{genai_{limit_idx + 1}:UInt64}}
    """
    assert_sql(expected, expected_params, query, pb.get_params())


# ============================================================================
# make_agent_versions_{count,list}_query
# ============================================================================


@pytest.mark.parametrize(
    ("builder", "expected", "expected_params"),
    [
        pytest.param(
            make_agent_versions_count_query,
            """
            SELECT count() FROM (
                SELECT agent_version FROM agent_versions
                WHERE project_id = {genai_0:String}
                AND agent_name = {genai_1:String}
                GROUP BY agent_version
            )
        """,
            {"genai_0": "p1", "genai_1": "a1"},
            id="count_basic",
        ),
        pytest.param(
            make_agent_versions_list_query,
            """
            SELECT agent_version,
                   sum(invocation_count) AS invocation_count,
                   sum(span_count) AS span_count,
                   sum(total_input_tokens) AS total_input_tokens,
                   sum(total_output_tokens) AS total_output_tokens,
                   sum(total_duration_ms) AS total_duration_ms,
                   sum(error_count) AS error_count,
                   min(first_seen) AS first_seen,
                   max(last_seen) AS last_seen
            FROM agent_versions
            WHERE project_id = {genai_0:String}
            AND agent_name = {genai_1:String}
            GROUP BY agent_version
            ORDER BY last_seen DESC
            LIMIT {genai_2:UInt64} OFFSET {genai_3:UInt64}
        """,
            {
                "genai_0": "p1",
                "genai_1": "a1",
                "genai_2": 100,
                "genai_3": 0,
            },
            id="list_basic",
        ),
    ],
)
def test_make_agent_versions_queries(
    builder: Callable[[ParamBuilder, AgentVersionsQueryReq], str],
    expected: str,
    expected_params: dict,
) -> None:
    pb = ParamBuilder("genai")
    query = builder(pb, AgentVersionsQueryReq(project_id="p1", agent_name="a1"))
    assert_sql(expected, expected_params, query, pb.get_params())


# ============================================================================
# make_message_search_query
# ============================================================================


@pytest.mark.parametrize(
    ("req", "where_tail", "expected_params"),
    [
        pytest.param(
            AgentSearchReq(project_id="p1", query="hello"),
            "AND content LIKE {genai_1:String}",
            {
                "genai_0": "p1",
                "genai_1": "%hello%",
                "genai_2": 20,
                "genai_3": 0,
            },
            id="basic",
        ),
        pytest.param(
            AgentSearchReq(
                project_id="p1",
                query="test",
                roles=["user", "assistant"],
                agent_name="bot",
                conversation_id="conv-1",
            ),
            """AND content LIKE {genai_1:String}
              AND role IN {genai_2:Array(String)}
              AND agent_name = {genai_3:String}
              AND conversation_id = {genai_4:String}""",
            {
                "genai_0": "p1",
                "genai_1": "%test%",
                "genai_2": ["user", "assistant"],
                "genai_3": "bot",
                "genai_4": "conv-1",
                "genai_5": 20,
                "genai_6": 0,
            },
            id="with_filters",
        ),
        pytest.param(
            AgentSearchReq(project_id="p1", query="test", roles=["tool"]),
            """AND content LIKE {genai_1:String}
              AND role IN {genai_2:Array(String)}""",
            {
                "genai_0": "p1",
                "genai_1": "%test%",
                "genai_2": ["tool_call", "tool_result"],
                "genai_3": 20,
                "genai_4": 0,
            },
            id="tool_role_alias_expands_to_tool_message_roles",
        ),
    ],
)
def test_make_message_search_query(
    req: AgentSearchReq, where_tail: str, expected_params: dict
) -> None:
    pb = ParamBuilder("genai")
    query = make_message_search_query(pb, req)
    limit_idx = len(expected_params) - 2
    expected = f"""
        {_MESSAGE_SEARCH_SELECT}
        FROM messages
        WHERE project_id = {{genai_0:String}}
        {where_tail}
        ORDER BY started_at DESC
        LIMIT {{genai_{limit_idx}:UInt64}} OFFSET {{genai_{limit_idx + 1}:UInt64}}
    """
    assert_sql(expected, expected_params, query, pb.get_params())


def test_message_search_escapes_like_wildcards() -> None:
    pb = ParamBuilder("genai")
    make_message_search_query(
        pb, AgentSearchReq(project_id="p1", query=r"88%_off\sale")
    )

    assert pb.get_params()["genai_1"] == r"%88\%\_off\\sale%"


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({"limit": 5000}, id="limit_above_max"),
        pytest.param({"limit": -1}, id="limit_negative"),
        pytest.param({"offset": -1}, id="offset_negative"),
    ],
)
def test_agent_search_req_rejects_limit_offset(kwargs: dict) -> None:
    with pytest.raises(ValidationError):
        AgentSearchReq(project_id="p1", query="x", **kwargs)


# ============================================================================
# make_conversation_chat_spans_query
# ============================================================================


@pytest.mark.parametrize(
    ("req", "expected_params"),
    [
        pytest.param(
            AgentConversationChatReq(project_id="p1", conversation_id="c1"),
            {"genai_0": "p1", "genai_1": "c1", "genai_2": 50, "genai_3": 0},
            id="basic",
        ),
        pytest.param(
            AgentConversationChatReq(
                project_id="p1", conversation_id="c1", limit=10, offset=20
            ),
            {"genai_0": "p1", "genai_1": "c1", "genai_2": 10, "genai_3": 20},
            id="with_pagination",
        ),
    ],
)
def test_make_conversation_chat_spans_query(
    req: AgentConversationChatReq, expected_params: dict
) -> None:
    pb = ParamBuilder("genai")
    query = make_conversation_chat_spans_query(pb, req)
    expected = f"""
        SELECT {", ".join(f"s.{c} AS {c}" for c in CHAT_VIEW_COLS.split(", "))}
        FROM spans s
        INNER JOIN (
            SELECT trace_id, min(started_at) AS turn_started_at
            FROM spans
            WHERE project_id = {{genai_0:String}}
            AND conversation_id = {{genai_1:String}}
            GROUP BY trace_id
            ORDER BY turn_started_at DESC, trace_id DESC
            LIMIT {{genai_2:UInt64}} OFFSET {{genai_3:UInt64}}
        ) t ON s.trace_id = t.trace_id
        WHERE s.project_id = {{genai_0:String}}
        ORDER BY t.turn_started_at ASC, t.trace_id ASC, s.started_at ASC
    """
    assert_sql(expected, expected_params, query, pb.get_params())


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({"limit": 51}, id="limit_above_max_turns"),
        pytest.param({"offset": -1}, id="offset_negative"),
    ],
)
def test_conversation_chat_req_rejects_limit_offset(kwargs: dict) -> None:
    with pytest.raises(ValidationError):
        AgentConversationChatReq(project_id="p1", conversation_id="c1", **kwargs)


def test_make_conversation_chat_turns_count_query() -> None:
    pb = ParamBuilder("genai")
    query = make_conversation_chat_turns_count_query(
        pb,
        AgentConversationChatReq(project_id="p1", conversation_id="c1"),
    )

    expected = """
        SELECT count() FROM (
            SELECT trace_id
            FROM spans s
            WHERE s.project_id = {genai_0:String}
            AND s.conversation_id = {genai_1:String}
            GROUP BY trace_id
        )
    """
    assert_sql(
        expected,
        {"genai_0": "p1", "genai_1": "c1"},
        query,
        pb.get_params(),
    )


# ============================================================================
# build_order_by
# ============================================================================


@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        pytest.param(None, "started_at DESC", id="default"),
        pytest.param(
            [AgentSortBy(field="input_tokens", direction="asc")],
            "input_tokens asc",
            id="valid_single",
        ),
        pytest.param(
            [
                AgentSortBy(field="started_at", direction="desc"),
                AgentSortBy(field="input_tokens", direction="asc"),
            ],
            "started_at desc, input_tokens asc",
            id="valid_multiple",
        ),
    ],
)
def test_build_order_by_success(sort: list[AgentSortBy] | None, expected: str) -> None:
    fallback = "started_at DESC" if sort is None else "fallback"
    assert build_order_by(sort, SPAN_SORTABLE_COLS, fallback) == expected


@pytest.mark.parametrize(
    ("sort", "expected_match"),
    [
        pytest.param(
            [AgentSortBy(field="'; DROP TABLE--", direction="asc")],
            "Invalid sort field",
            id="invalid_field_injection_guard",
        ),
        pytest.param(
            [AgentSortBy.model_construct(field="input_tokens", direction="sideways")],
            "Invalid sort direction",
            id="invalid_direction",
        ),
    ],
)
def test_build_order_by_rejects(sort: list[AgentSortBy], expected_match: str) -> None:
    with pytest.raises(ValueError, match=expected_match):
        build_order_by(sort, SPAN_SORTABLE_COLS, "started_at DESC")


def assert_sql(
    expected_query: str, expected_params: dict, query: str, params: dict
) -> None:
    expected_formatted = sqlparse.format(expected_query, reindent=True).strip()
    found_formatted = sqlparse.format(query, reindent=True).strip()

    assert expected_formatted == found_formatted, (
        f"\nExpected:\n{expected_formatted}\n\nGot:\n{found_formatted}"
    )
    assert expected_params == params, (
        f"\nExpected params: {expected_params}\n\nGot params: {params}"
    )
