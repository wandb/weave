"""SQL shape assertions for every `make_*_query` function in the agent
query builder.

Each test builds a `ParamBuilder`, calls the builder, and compares the full
formatted SQL + param dict against an expected value, matching the style of
`test_annotation_queues_query_builder.py` etc.
"""

import datetime
import re

import pytest
import sqlparse
from pydantic import ValidationError

from weave.trace_server.agents.span_costs import cost_augmented_source_sql
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
    QUALIFIED_CHAT_VIEW_COLS,
    QUALIFIED_SPANS_COST_COLS,
    SPAN_SORTABLE_COLS,
    SPANS_COST_COLS,
    SPANS_LIST_COLS,
    build_order_by,
    make_agent_versions_count_query,
    make_agent_versions_list_query,
    make_agents_count_query,
    make_agents_list_query,
    make_conversation_chat_spans_query,
    make_conversation_chat_turns_count_query,
    make_conversation_previews_query,
    make_conversation_spans_query,
    make_custom_attrs_schema_query,
    make_message_search_query,
    make_span_group_categorical_distributions_query,
    make_span_group_numeric_distributions_query,
    make_spans_count_query,
    make_spans_list_query,
    make_trace_detail_spans_query,
    resolve_group_by,
)
from weave.trace_server.query_builder.agent_trace_attribution import (
    attributed_spans_source,
)


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


class _AttrSrc:
    """Expected FROM source + params for queries that read attributed spans.

    Reuses the real `attributed_spans_source` so these tests assert the builder
    wires it in (the source SQL itself is golden-tested in
    `test_agent_trace_attribution.py`). The builder allocates the source params
    *last*, so `offset` shifts the helper's `genai_0`-based slots to where they
    land in the full query.
    """

    def __init__(
        self,
        offset: int,
        *,
        project_id: str = "p1",
        started_after: datetime.datetime | None = None,
        started_before: datetime.datetime | None = None,
        base_relation: str = "spans",
        fallback_trace_id_scope: str | None = None,
    ) -> None:
        pb = ParamBuilder("genai")
        sql = attributed_spans_source(
            pb,
            project_id=project_id,
            started_after=started_after,
            started_before=started_before,
            base_relation=base_relation,
            fallback_trace_id_scope=fallback_trace_id_scope,
        )
        self.sql = re.sub(
            r"genai_(\d+)", lambda m: f"genai_{int(m.group(1)) + offset}", sql
        )
        self.params = {
            f"genai_{int(k.split('_')[1]) + offset}": v
            for k, v in pb.get_params().items()
        }


#: trace_id scope the two-pass list read passes to the fallback rollup.
_PAGE_SCOPE = "SELECT trace_id FROM page"


def _two_pass_expected(
    *,
    base: str,
    where: str,
    order_by: str,
    projection: str,
    attr_sql: str,
    limit_slot: str = "{genai_1:UInt64}",
    offset_slot: str = "{genai_2:UInt64}",
) -> str:
    """Expected SQL for the page-prefetch two-pass ungrouped list read."""
    return f"""
        WITH page AS (
            SELECT * FROM {base} s
            WHERE {where}
            ORDER BY {order_by}
            LIMIT {limit_slot} OFFSET {offset_slot}
        )
        SELECT {projection}
        FROM {attr_sql} s
        ORDER BY {order_by}
    """


# ============================================================================
# make_spans_count_query (ungrouped)
# ============================================================================


class TestMakeSpansCountQuery:
    def test_basic(self) -> None:
        pb = ParamBuilder("genai")
        query = make_spans_count_query(pb, AgentSpansQueryReq(project_id="p1"))

        expected = "SELECT count() FROM spans s WHERE s.project_id = {genai_0:String}"
        assert_sql(expected, {"genai_0": "p1"}, query, pb.get_params())

    def test_with_query_and_time(self) -> None:
        pb = ParamBuilder("genai")
        start = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2026, 2, 1, tzinfo=datetime.timezone.utc)
        query = make_spans_count_query(
            pb,
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
                started_after=start,
                started_before=end,
            ),
        )

        # Filtering on agent.name (identity) reads the attributed source.
        src = _AttrSrc(6, started_after=start, started_before=end)
        expected = f"""
            SELECT count() FROM {src.sql} s
            WHERE s.project_id = {{genai_0:String}}
              AND s.started_at >= {{genai_1:DateTime64(6)}}
              AND s.started_at < {{genai_2:DateTime64(6)}}
            AND ((s.agent_name = {{genai_3:String}}) AND (if(mapContains(s.custom_attrs_string, {{genai_4:String}}), s.custom_attrs_string[{{genai_4:String}}], NULL) = {{genai_5:String}}))
        """
        expected_params = {
            "genai_0": "p1",
            "genai_1": start,
            "genai_2": end,
            "genai_3": "bot",
            "genai_4": "env",
            "genai_5": "prod",
            **src.params,
        }
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_rejects_empty_not(self) -> None:
        pb = ParamBuilder("genai")
        query = Query.model_construct(
            expr_=tsi_query.NotOperation.model_construct(not_=())
        )

        with pytest.raises(ValueError, match="Empty \\$not"):
            make_spans_count_query(pb, AgentSpansQueryReq(project_id="p1", query=query))

    def test_rejects_null_non_eq_comparison(self) -> None:
        pb = ParamBuilder("genai")
        query = Query.model_validate(
            {
                "$expr": {
                    "$gt": [
                        {"$getField": "input_tokens"},
                        {"$literal": None},
                    ]
                }
            }
        )

        with pytest.raises(ValueError, match="Null values are not allowed"):
            make_spans_count_query(pb, AgentSpansQueryReq(project_id="p1", query=query))

    def test_rejects_mixed_in_literal_types(self) -> None:
        pb = ParamBuilder("genai")
        query = Query.model_validate(
            {
                "$expr": {
                    "$in": [
                        {"$getField": "agent_name"},
                        [{"$literal": "bot"}, {"$literal": 1}],
                    ]
                }
            }
        )

        with pytest.raises(ValueError, match="same type"):
            make_spans_count_query(pb, AgentSpansQueryReq(project_id="p1", query=query))


# ============================================================================
# make_spans_list_query (ungrouped)
# ============================================================================


class TestMakeSpansListQuery:
    def test_basic_uses_two_pass(self) -> None:
        # Default list (no group_by, non-identity sort/filter): the page is
        # limited first on the bare `spans` table, then only that page is
        # attributed with the fallback rollup scoped to the page's traces.
        pb = ParamBuilder("genai")
        query = make_spans_list_query(pb, AgentSpansQueryReq(project_id="p1"))

        src = _AttrSrc(3, base_relation="page", fallback_trace_id_scope=_PAGE_SCOPE)
        expected = _two_pass_expected(
            base="spans",
            where="s.project_id = {genai_0:String}",
            order_by="started_at DESC",
            projection=SPANS_LIST_COLS,
            attr_sql=src.sql,
        )
        expected_params = {"genai_0": "p1", "genai_1": 100, "genai_2": 0, **src.params}
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_with_custom_sort(self) -> None:
        pb = ParamBuilder("genai")
        query = make_spans_list_query(
            pb,
            AgentSpansQueryReq(
                project_id="p1",
                sort_by=[AgentSortBy(field="input_tokens", direction="asc")],
            ),
        )

        src = _AttrSrc(3, base_relation="page", fallback_trace_id_scope=_PAGE_SCOPE)
        expected = _two_pass_expected(
            base="spans",
            where="s.project_id = {genai_0:String}",
            order_by="input_tokens asc",
            projection=SPANS_LIST_COLS,
            attr_sql=src.sql,
        )
        expected_params = {"genai_0": "p1", "genai_1": 100, "genai_2": 0, **src.params}
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_projects_and_sorts_selected_custom_attr_columns(self) -> None:
        pb = ParamBuilder("genai")
        query = make_spans_list_query(
            pb,
            AgentSpansQueryReq(
                project_id="p1",
                custom_attr_columns=[
                    AgentSpanValueRef(source="custom_attrs_float", key="score")
                ],
                sort_by=[
                    AgentSortBy(field="custom_attrs_float.score", direction="desc")
                ],
            ),
        )

        src = _AttrSrc(5, base_relation="page", fallback_trace_id_scope=_PAGE_SCOPE)
        order_by = "if(mapContains(s.custom_attrs_float, {genai_3:String}), toFloat64(s.custom_attrs_float[{genai_3:String}]), NULL) desc"
        expected = _two_pass_expected(
            base="spans",
            where="s.project_id = {genai_0:String}",
            order_by=order_by,
            projection=f"{SPANS_LIST_COLS}, mapFilter((k, v) -> has({{genai_4:Array(String)}}, k), s.custom_attrs_float) AS custom_attrs_float",
            attr_sql=src.sql,
        )
        expected_params = {
            "genai_0": "p1",
            "genai_1": 100,
            "genai_2": 0,
            "genai_3": "score",
            "genai_4": ["score"],
            **src.params,
        }
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_limit_rejected_when_above_max(self) -> None:
        with pytest.raises(ValidationError):
            AgentSpansQueryReq(project_id="p1", limit=99999)

    def test_limit_rejected_when_negative(self) -> None:
        with pytest.raises(ValidationError):
            AgentSpansQueryReq(project_id="p1", limit=-1)

    def test_offset_rejected_when_negative(self) -> None:
        with pytest.raises(ValidationError):
            AgentSpansQueryReq(project_id="p1", offset=-1)

    def test_limit_zero_is_honored(self) -> None:
        pb = ParamBuilder("genai")
        make_spans_list_query(pb, AgentSpansQueryReq(project_id="p1", limit=0))
        assert pb.get_params()["genai_1"] == 0

    def test_custom_attr_columns_rejected_with_group_by(self) -> None:
        """custom_attr_columns project per-span maps and are silently dropped in
        the grouped path. The validator should reject this combination instead
        of accepting it and quietly ignoring the projection, symmetric with
        the existing rule that grouped-only fields (measures, group_filters)
        require group_by.
        """
        with pytest.raises(ValidationError):
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[AgentGroupByRef(source="column", key="agent_name")],
                custom_attr_columns=[
                    AgentSpanValueRef(source="custom_attrs_string", key="env")
                ],
            )

    def test_include_details_projects_detail_columns(self) -> None:
        from weave.trace_server.query_builder.agent_query_builder import (
            SPANS_DETAILS_COLS,
        )

        pb = ParamBuilder("genai")
        query = make_spans_list_query(
            pb, AgentSpansQueryReq(project_id="p1", include_details=True)
        )

        src = _AttrSrc(3, base_relation="page", fallback_trace_id_scope=_PAGE_SCOPE)
        expected = _two_pass_expected(
            base="spans",
            where="s.project_id = {genai_0:String}",
            order_by="started_at DESC",
            projection=f"{SPANS_LIST_COLS}, {SPANS_DETAILS_COLS}",
            attr_sql=src.sql,
        )
        expected_params = {"genai_0": "p1", "genai_1": 100, "genai_2": 0, **src.params}
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_identity_sort_keeps_full_attribution(self) -> None:
        # Sorting by an attributed identity column makes the page depend on
        # attribution, so the two-pass does not apply: the whole source is
        # attributed before the ORDER BY / LIMIT (current path, unchanged).
        pb = ParamBuilder("genai")
        query = make_spans_list_query(
            pb,
            AgentSpansQueryReq(
                project_id="p1",
                sort_by=[AgentSortBy(field="agent_name", direction="asc")],
            ),
        )

        src = _AttrSrc(3)
        expected = f"""
            SELECT {SPANS_LIST_COLS}
            FROM {src.sql} s
            WHERE s.project_id = {{genai_0:String}}
            ORDER BY agent_name asc
            LIMIT {{genai_1:UInt64}} OFFSET {{genai_2:UInt64}}
        """
        expected_params = {"genai_0": "p1", "genai_1": 100, "genai_2": 0, **src.params}
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_identity_filter_keeps_full_attribution(self) -> None:
        # Filtering on an attributed identity column makes page membership
        # depend on attribution -> current path, unchanged.
        pb = ParamBuilder("genai")
        query = make_spans_list_query(
            pb,
            AgentSpansQueryReq(
                project_id="p1",
                query=Query(
                    **{
                        "$expr": {
                            "$eq": [{"$getField": "agent_name"}, {"$literal": "claude"}]
                        }
                    }
                ),
            ),
        )

        src = _AttrSrc(4)
        expected = f"""
            SELECT {SPANS_LIST_COLS}
            FROM {src.sql} s
            WHERE s.project_id = {{genai_0:String}} AND (s.agent_name = {{genai_1:String}})
            ORDER BY started_at DESC
            LIMIT {{genai_2:UInt64}} OFFSET {{genai_3:UInt64}}
        """
        expected_params = {
            "genai_0": "p1",
            "genai_1": "claude",
            "genai_2": 100,
            "genai_3": 0,
            **src.params,
        }
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_trace_id_filter_keeps_full_attribution(self) -> None:
        # A trace_id filter is pushed into the fallback rollup by ClickHouse, so
        # the current path is already optimal -> two-pass falls back (avoids the
        # redundant scan that regresses the single-trace read).
        pb = ParamBuilder("genai")
        query = make_spans_list_query(
            pb,
            AgentSpansQueryReq(
                project_id="p1",
                query=Query(
                    **{
                        "$expr": {
                            "$eq": [{"$getField": "trace_id"}, {"$literal": "t1"}]
                        }
                    }
                ),
            ),
        )

        src = _AttrSrc(4)
        expected = f"""
            SELECT {SPANS_LIST_COLS}
            FROM {src.sql} s
            WHERE s.project_id = {{genai_0:String}} AND (s.trace_id = {{genai_1:String}})
            ORDER BY started_at DESC
            LIMIT {{genai_2:UInt64}} OFFSET {{genai_3:UInt64}}
        """
        expected_params = {
            "genai_0": "p1",
            "genai_1": "t1",
            "genai_2": 100,
            "genai_3": 0,
            **src.params,
        }
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_non_identity_filter_uses_two_pass(self) -> None:
        pb = ParamBuilder("genai")
        query = make_spans_list_query(
            pb,
            AgentSpansQueryReq(
                project_id="p1",
                query=Query(
                    **{
                        "$expr": {
                            "$eq": [
                                {"$getField": "operation_name"},
                                {"$literal": "invoke_agent"},
                            ]
                        }
                    }
                ),
            ),
        )

        src = _AttrSrc(4, base_relation="page", fallback_trace_id_scope=_PAGE_SCOPE)
        expected = _two_pass_expected(
            base="spans",
            where="s.project_id = {genai_0:String} AND (s.operation_name = {genai_1:String})",
            order_by="started_at DESC",
            projection=SPANS_LIST_COLS,
            attr_sql=src.sql,
            limit_slot="{genai_2:UInt64}",
            offset_slot="{genai_3:UInt64}",
        )
        expected_params = {
            "genai_0": "p1",
            "genai_1": "invoke_agent",
            "genai_2": 100,
            "genai_3": 0,
            **src.params,
        }
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_include_costs_uses_two_pass_over_cost_source(self) -> None:
        # The page CTE reads the cost-augmented source (per-span price JOIN),
        # then only the page is attributed. Compose the expected from the same
        # helpers so the snapshot stays exact without copying the price-JOIN SQL.
        pb = ParamBuilder("genai")
        query = make_spans_list_query(
            pb, AgentSpansQueryReq(project_id="p1", include_costs=True)
        )

        expected_pb = ParamBuilder("genai")
        expected_pb.add("p1", param_type="String")  # genai_0: page project filter
        expected_pb.add(100, param_type="UInt64")  # genai_1: limit
        expected_pb.add(0, param_type="UInt64")  # genai_2: offset
        cost_source = cost_augmented_source_sql(expected_pb, "p1")  # genai_3, genai_4
        attributed = attributed_spans_source(
            expected_pb,
            project_id="p1",
            started_after=None,
            started_before=None,
            base_relation="page",
            fallback_trace_id_scope=_PAGE_SCOPE,
        )  # genai_5
        expected = _two_pass_expected(
            base=cost_source,
            where="s.project_id = {genai_0:String}",
            order_by="started_at DESC",
            projection=f"{SPANS_LIST_COLS}, {SPANS_COST_COLS}",
            attr_sql=attributed,
        )
        assert_sql(expected, expected_pb.get_params(), query, pb.get_params())

    def test_include_details_rejected_with_group_by(self) -> None:
        """SPANS_DETAILS_COLS is only projected on the ungrouped path. The
        grouped branch ignores `include_details`, so the validator rejects
        the combination instead of accepting it and quietly dropping the
        heavy-fields projection.
        """
        with pytest.raises(ValidationError):
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[AgentGroupByRef(source="column", key="agent_name")],
                include_details=True,
            )


# ============================================================================
# make_spans_count_query (grouped)
# ============================================================================


#: The fixed aggregate tail emitted by the grouped list query, as it would
#: appear after `SELECT <group_cols>,`. Used to keep test expected SQL
#: readable without duplicating the bundle across every test.
_GROUPED_AGG_TAIL = """count() AS span_count,
               countIf(s.operation_name = 'invoke_agent') AS invocation_count,
               uniq(s.conversation_id) AS conversation_count,
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


class TestMakeConversationPreviewsQuery:
    def test_scoped_to_conversation_ids(self) -> None:
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

    def test_applies_time_range(self) -> None:
        pb = ParamBuilder("genai")
        start = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc)
        query = make_conversation_previews_query(
            pb, "p1", ["conv-a"], started_after=start, started_before=end
        )
        # Time bounds let ClickHouse prune partitions / primary-key ranges so the
        # wide message columns are read for an even smaller slice.
        expected = """
            SELECT s.conversation_id AS conversation_id,
                   argMinIf(s.input_messages, s.started_at, length(s.input_messages) > 0) AS first_input_messages,
                   argMaxIf(s.output_messages, s.ended_at, length(s.output_messages) > 0) AS last_output_messages
            FROM spans s
            WHERE s.project_id = {genai_0:String} AND s.conversation_id IN {genai_1:Array(String)} AND s.started_at >= {genai_2:DateTime64(6)} AND s.started_at < {genai_3:DateTime64(6)}
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


def test_make_conversation_spans_query() -> None:
    # Scoped to the page's conversation_ids (like the previews query), reading
    # only narrow scalar columns: an ordered, capped array of per-span tuples
    # aliased `spans`. Kind is classified from operation_name; ERROR comes from
    # status_code.
    pb = ParamBuilder("genai")
    query = make_conversation_spans_query(pb, "p1", ["conv-a", "conv-b"])
    expected = """
        SELECT s.conversation_id AS conversation_id,
               arraySlice(arraySort(x -> (x.1, x.4), groupArray(tuple(s.started_at, s.operation_name, s.trace_id, s.span_id, s.status_code, if(s.ended_at > s.started_at, toUnixTimestamp64Milli(s.ended_at) - toUnixTimestamp64Milli(s.started_at), 0)))), -200) AS spans
        FROM spans s
        WHERE s.project_id = {genai_0:String}
          AND s.conversation_id IN {genai_1:Array(String)}
        GROUP BY conversation_id
    """
    assert_sql(
        expected,
        {"genai_0": "p1", "genai_1": ["conv-a", "conv-b"]},
        query,
        pb.get_params(),
    )


def test_make_conversation_spans_query_with_time_range() -> None:
    pb = ParamBuilder("genai")
    start = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    end = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc)
    query = make_conversation_spans_query(
        pb, "p1", ["conv-a", "conv-b"], started_after=start, started_before=end
    )
    expected = """
        SELECT s.conversation_id AS conversation_id,
               arraySlice(arraySort(x -> (x.1, x.4), groupArray(tuple(s.started_at, s.operation_name, s.trace_id, s.span_id, s.status_code, if(s.ended_at > s.started_at, toUnixTimestamp64Milli(s.ended_at) - toUnixTimestamp64Milli(s.started_at), 0)))), -200) AS spans
        FROM spans s
        WHERE s.project_id = {genai_0:String}
          AND s.conversation_id IN {genai_1:Array(String)}
          AND s.started_at >= {genai_2:DateTime64(6)}
          AND s.started_at < {genai_3:DateTime64(6)}
        GROUP BY conversation_id
    """
    assert_sql(
        expected,
        {
            "genai_0": "p1",
            "genai_1": ["conv-a", "conv-b"],
            "genai_2": start,
            "genai_3": end,
        },
        query,
        pb.get_params(),
    )


class TestMakeGroupedSpansCountQuery:
    def test_group_by_column(self) -> None:
        pb = ParamBuilder("genai")
        query = make_spans_count_query(
            pb,
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[AgentGroupByRef(source="column", key="trace_id")],
            ),
        )

        expected = """
            SELECT count() FROM (
                SELECT s.trace_id FROM spans s
                WHERE s.project_id = {genai_0:String}
                GROUP BY s.trace_id
            )
        """
        assert_sql(expected, {"genai_0": "p1"}, query, pb.get_params())

    def test_group_by_custom_attr(self) -> None:
        pb = ParamBuilder("genai")
        query = make_spans_count_query(
            pb,
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[AgentGroupByRef(source="custom_attrs_string", key="env")],
            ),
        )

        expected = """
            SELECT count() FROM (
                SELECT if(mapContains(s.custom_attrs_string, {genai_1:String}), s.custom_attrs_string[{genai_1:String}], NULL) FROM spans s
                WHERE s.project_id = {genai_0:String}
                GROUP BY if(mapContains(s.custom_attrs_string, {genai_1:String}), s.custom_attrs_string[{genai_1:String}], NULL)
            )
        """
        expected_params = {"genai_0": "p1", "genai_1": "env"}
        assert_sql(expected, expected_params, query, pb.get_params())


# ============================================================================
# make_spans_list_query (grouped)
# ============================================================================


class TestMakeGroupedSpansListQuery:
    def test_group_by_trace_id(self) -> None:
        pb = ParamBuilder("genai")
        query = make_spans_list_query(
            pb,
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[AgentGroupByRef(source="column", key="trace_id")],
            ),
        )

        src = _AttrSrc(3)
        expected = f"""
            SELECT s.trace_id AS trace_id,
                   {_GROUPED_AGG_TAIL}
            FROM {src.sql} s
            WHERE s.project_id = {{genai_0:String}}
            GROUP BY trace_id
            ORDER BY last_seen DESC
            LIMIT {{genai_1:UInt64}} OFFSET {{genai_2:UInt64}}
        """
        expected_params = {"genai_0": "p1", "genai_1": 100, "genai_2": 0, **src.params}
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_group_by_conversation_id_with_time(self) -> None:
        pb = ParamBuilder("genai")
        start = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2026, 2, 1, tzinfo=datetime.timezone.utc)
        query = make_spans_list_query(
            pb,
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[
                    AgentGroupByRef(source="column", key="conversation_id"),
                ],
                started_after=start,
                started_before=end,
            ),
        )

        src = _AttrSrc(5, started_after=start, started_before=end)
        expected = f"""
            SELECT s.conversation_id AS conversation_id,
                   {_GROUPED_AGG_TAIL}
            FROM {src.sql} s
            WHERE s.project_id = {{genai_0:String}}
              AND s.started_at >= {{genai_1:DateTime64(6)}}
              AND s.started_at < {{genai_2:DateTime64(6)}}
            GROUP BY conversation_id
            ORDER BY last_seen DESC
            LIMIT {{genai_3:UInt64}} OFFSET {{genai_4:UInt64}}
        """
        expected_params = {
            "genai_0": "p1",
            "genai_1": start,
            "genai_2": end,
            "genai_3": 100,
            "genai_4": 0,
            **src.params,
        }
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_group_by_custom_attr(self) -> None:
        pb = ParamBuilder("genai")
        query = make_spans_list_query(
            pb,
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[
                    AgentGroupByRef(source="custom_attrs_string", key="env"),
                ],
            ),
        )

        src = _AttrSrc(4)
        expected = f"""
            SELECT if(mapContains(s.custom_attrs_string, {{genai_3:String}}), s.custom_attrs_string[{{genai_3:String}}], NULL) AS env,
                   {_GROUPED_AGG_TAIL}
            FROM {src.sql} s
            WHERE s.project_id = {{genai_0:String}}
            GROUP BY env
            ORDER BY last_seen DESC
            LIMIT {{genai_1:UInt64}} OFFSET {{genai_2:UInt64}}
        """
        expected_params = {
            "genai_0": "p1",
            "genai_1": 100,
            "genai_2": 0,
            "genai_3": "env",
            **src.params,
        }
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_group_by_multi_column_and_sort_by_alias(self) -> None:
        pb = ParamBuilder("genai")
        query = make_spans_list_query(
            pb,
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[
                    AgentGroupByRef(source="field", key="agent.name"),
                    AgentGroupByRef(source="column", key="request_model"),
                ],
                sort_by=[AgentSortBy(field="agent_name", direction="asc")],
            ),
        )

        src = _AttrSrc(3)
        expected = f"""
            SELECT s.agent_name AS agent_name,
                   s.request_model AS request_model,
                   {_GROUPED_AGG_TAIL}
            FROM {src.sql} s
            WHERE s.project_id = {{genai_0:String}}
            GROUP BY agent_name, request_model
            ORDER BY agent_name asc
            LIMIT {{genai_1:UInt64}} OFFSET {{genai_2:UInt64}}
        """
        expected_params = {"genai_0": "p1", "genai_1": 100, "genai_2": 0, **src.params}
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_group_by_with_dynamic_measures_filter_and_sort(self) -> None:
        pb = ParamBuilder("genai")
        query = make_spans_list_query(
            pb,
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
        )

        expected = """
            SELECT s.conversation_id AS conversation_id,
                   {_GROUPED_AGG_TAIL},
                   count() AS spans,
                   countIf(((s.operation_name = {genai_3:String}))) AS tool_calls,
                   avgOrNull(if((mapContains(s.custom_attrs_float, {genai_4:String})), toFloat64(s.custom_attrs_float[{genai_4:String}]), NULL)) AS avg_score
            FROM {_ATTR_SRC} s
            WHERE s.project_id = {genai_0:String}
            GROUP BY conversation_id
            HAVING avgOrNull(if((mapContains(s.custom_attrs_float, {genai_5:String})), toFloat64(s.custom_attrs_float[{genai_5:String}]), NULL)) >= {genai_6:Float64}
            ORDER BY avg_score desc
            LIMIT {genai_1:UInt64} OFFSET {genai_2:UInt64}
        """
        src = _AttrSrc(7)
        expected = expected.replace("{_GROUPED_AGG_TAIL}", _GROUPED_AGG_TAIL).replace(
            "{_ATTR_SRC}", src.sql
        )
        expected_params = {
            "genai_0": "p1",
            "genai_1": 100,
            "genai_2": 0,
            "genai_3": "execute_tool",
            "genai_4": "score",
            "genai_5": "score",
            "genai_6": 0.5,
            **src.params,
        }
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_dynamic_measure_rejects_invalid_resolved_aggregation(self) -> None:
        pb = ParamBuilder("genai")
        with pytest.raises(ValueError, match="not valid for value_type 'string'"):
            make_spans_list_query(
                pb,
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
            )

    def test_dynamic_measure_infers_boolean_count_true(self) -> None:
        pb = ParamBuilder("genai")
        query = make_spans_list_query(
            pb,
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
        )

        expected = """
            SELECT s.conversation_id AS conversation_id,
                   {_GROUPED_AGG_TAIL},
                   countIf((mapContains(s.custom_attrs_bool, {genai_3:String})) AND s.custom_attrs_bool[{genai_3:String}] = 1) AS flagged_count
            FROM {_ATTR_SRC} s
            WHERE s.project_id = {genai_0:String}
            GROUP BY conversation_id
            ORDER BY flagged_count DESC
            LIMIT {genai_1:UInt64} OFFSET {genai_2:UInt64}
        """
        src = _AttrSrc(4)
        expected = expected.replace("{_GROUPED_AGG_TAIL}", _GROUPED_AGG_TAIL).replace(
            "{_ATTR_SRC}", src.sql
        )
        expected_params = {
            "genai_0": "p1",
            "genai_1": 100,
            "genai_2": 0,
            "genai_3": "flagged",
            **src.params,
        }
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_dynamic_measure_rejects_fixed_field_alias_collision(self) -> None:
        with pytest.raises(
            ValidationError,
            match="measure aliases collide with grouped row fields: \\['span_count'\\]",
        ):
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[AgentGroupByRef(source="column", key="conversation_id")],
                measures=[
                    AgentSpanMeasureSpec(
                        alias="span_count",
                        aggregation="count",
                    )
                ],
            )

    def test_dynamic_measure_rejects_group_key_alias_collision(self) -> None:
        with pytest.raises(
            ValidationError,
            match=(
                "measure aliases collide with grouped row fields: "
                "\\['conversation_id'\\]"
            ),
        ):
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[AgentGroupByRef(source="column", key="conversation_id")],
                measures=[
                    AgentSpanMeasureSpec(
                        alias="conversation_id",
                        aggregation="count",
                    )
                ],
            )

    def test_group_filter_rejects_mismatched_datetime_bound(self) -> None:
        pb = ParamBuilder("genai")
        with pytest.raises(
            ValueError,
            match="datetime group filter bounds require a datetime measure",
        ):
            make_spans_list_query(
                pb,
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
            )

    def test_group_filter_rejects_mismatched_group_by(self) -> None:
        pb = ParamBuilder("genai")
        with pytest.raises(
            ValueError,
            match="spans list group_filters must use the same group_by",
        ):
            make_spans_list_query(
                pb,
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
            )


# ============================================================================
# make_span_group_*_distribution_query
# ============================================================================


class TestMakeSpanGroupDistributionQueries:
    def test_numeric_distributions_query_batches_specs(self) -> None:
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
                  FROM {_ATTR_SRC} s
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
        src = _AttrSrc(10)
        expected = expected.replace("{_ATTR_SRC}", src.sql)
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
            **src.params,
        }
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_categorical_distributions_query_batches_specs(self) -> None:
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
                  FROM {_ATTR_SRC} s
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
        src = _AttrSrc(10)
        expected = expected.replace("{_ATTR_SRC}", src.sql)
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
            **src.params,
        }
        assert_sql(expected, expected_params, query, pb.get_params())


# ============================================================================
# resolve_group_by validation
# ============================================================================


class TestResolveGroupBy:
    def test_rejects_non_allowlisted_column(self) -> None:
        pb = ParamBuilder("genai")
        with pytest.raises(ValueError, match="not in the allowlist"):
            resolve_group_by(
                pb, [AgentGroupByRef(source="column", key="raw_span_dump")]
            )

    def test_rejects_duplicate_alias(self) -> None:
        pb = ParamBuilder("genai")
        with pytest.raises(ValueError, match="duplicate group_by alias"):
            resolve_group_by(
                pb,
                [
                    AgentGroupByRef(source="field", key="agent.name"),
                    AgentGroupByRef(source="column", key="agent_name"),
                ],
            )

    def test_field_source_resolves_semconv_key(self) -> None:
        pb = ParamBuilder("genai")
        out = resolve_group_by(pb, [AgentGroupByRef(source="field", key="agent.name")])
        assert out == [("s.agent_name", "agent_name")]

    def test_rejects_invalid_alias(self) -> None:
        pb = ParamBuilder("genai")
        with pytest.raises(ValueError, match="must match"):
            resolve_group_by(
                pb,
                [
                    AgentGroupByRef(
                        source="custom_attrs_string",
                        key="has spaces",
                        alias="bad alias",
                    )
                ],
            )

    def test_defaults_alias_to_key_when_valid(self) -> None:
        pb = ParamBuilder("genai")
        out = resolve_group_by(
            pb, [AgentGroupByRef(source="custom_attrs_string", key="env")]
        )
        assert out == [
            (
                "if(mapContains(s.custom_attrs_string, {genai_0:String}), "
                "s.custom_attrs_string[{genai_0:String}], NULL)",
                "env",
            )
        ]

    def test_custom_alias_used_when_key_non_identifier(self) -> None:
        pb = ParamBuilder("genai")
        out = resolve_group_by(
            pb,
            [
                AgentGroupByRef(
                    source="custom_attrs_string",
                    key="has spaces",
                    alias="spaced_attr",
                )
            ],
        )
        assert out == [
            (
                "if(mapContains(s.custom_attrs_string, {genai_0:String}), "
                "s.custom_attrs_string[{genai_0:String}], NULL)",
                "spaced_attr",
            )
        ]


# ============================================================================
# make_trace_detail_spans_query (internal helper — chat view only)
# ============================================================================


class TestMakeTraceDetailSpansQuery:
    def test_basic(self) -> None:
        pb = ParamBuilder("genai")
        query = make_trace_detail_spans_query(pb, "p1", "t1")

        # Always cost-augmented (the chat/detail views render per-message and
        # per-trace cost). Compose the expected cost source from the same
        # helper so the snapshot stays exact without copying the price-JOIN SQL.
        expected_pb = ParamBuilder("genai")
        expected_pb.add("p1", param_type="String")  # genai_0: project filter
        expected_pb.add("t1", param_type="String")  # genai_1: trace filter
        source = cost_augmented_source_sql(expected_pb, "p1")
        expected = f"""
            SELECT {CHAT_VIEW_COLS}, {SPANS_COST_COLS} FROM {source} s
            WHERE s.project_id = {{genai_0:String}}
            AND s.trace_id = {{genai_1:String}}
            ORDER BY s.started_at ASC
        """
        assert_sql(expected, expected_pb.get_params(), query, pb.get_params())


# ============================================================================
# make_agents_count_query / make_agents_list_query
# ============================================================================


class TestMakeAgentsQueries:
    def test_count_basic(self) -> None:
        pb = ParamBuilder("genai")
        query = make_agents_count_query(pb, AgentsQueryReq(project_id="p1"))

        expected = """
            SELECT count() FROM (
                SELECT agent_name FROM agents
                WHERE project_id = {genai_0:String}
                GROUP BY agent_name
            )
        """
        assert_sql(expected, {"genai_0": "p1"}, query, pb.get_params())

    def test_list_basic(self) -> None:
        pb = ParamBuilder("genai")
        query = make_agents_list_query(pb, AgentsQueryReq(project_id="p1"))

        expected = """
            SELECT agent_name,
                   sum(invocation_count) AS invocation_count,
                   sum(span_count) AS span_count,
                   sum(total_input_tokens) AS total_input_tokens,
                   sum(total_output_tokens) AS total_output_tokens,
                   sum(total_duration_ms) AS total_duration_ms,
                   sum(error_count) AS error_count,
                   min(first_seen) AS first_seen,
                   max(last_seen) AS last_seen
            FROM agents
            WHERE project_id = {genai_0:String}
            GROUP BY agent_name
            ORDER BY last_seen DESC, agent_name
            LIMIT {genai_1:UInt64} OFFSET {genai_2:UInt64}
        """
        expected_params = {"genai_0": "p1", "genai_1": 100, "genai_2": 0}
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_list_with_filter(self) -> None:
        pb = ParamBuilder("genai")
        query = make_agents_list_query(
            pb,
            AgentsQueryReq(
                project_id="p1",
                filters=AgentsQueryFilters(agent_name="my-agent"),
            ),
        )

        expected = """
            SELECT agent_name,
                   sum(invocation_count) AS invocation_count,
                   sum(span_count) AS span_count,
                   sum(total_input_tokens) AS total_input_tokens,
                   sum(total_output_tokens) AS total_output_tokens,
                   sum(total_duration_ms) AS total_duration_ms,
                   sum(error_count) AS error_count,
                   min(first_seen) AS first_seen,
                   max(last_seen) AS last_seen
            FROM agents
            WHERE project_id = {genai_0:String}
            AND agent_name = {genai_1:String}
            GROUP BY agent_name
            ORDER BY last_seen DESC, agent_name
            LIMIT {genai_2:UInt64} OFFSET {genai_3:UInt64}
        """
        expected_params = {
            "genai_0": "p1",
            "genai_1": "my-agent",
            "genai_2": 100,
            "genai_3": 0,
        }
        assert_sql(expected, expected_params, query, pb.get_params())


# ============================================================================
# make_custom_attrs_schema_query
# ============================================================================


class TestMakeCustomAttrsSchemaQuery:
    def test_basic(self) -> None:
        pb = ParamBuilder("genai")
        query = make_custom_attrs_schema_query(
            pb,
            AgentCustomAttrsSchemaReq(project_id="p1"),
        )

        expected = """
            SELECT tupleElement(attr, 1) AS source,
                   tupleElement(attr, 2) AS key,
                   tupleElement(attr, 3) AS value_type,
                   count() AS span_count
            FROM (
                SELECT s.custom_attrs_string.keys AS custom_attrs_string_keys,
                       s.custom_attrs_int.keys AS custom_attrs_int_keys,
                       s.custom_attrs_float.keys AS custom_attrs_float_keys,
                       s.custom_attrs_bool.keys AS custom_attrs_bool_keys
                FROM spans s
                WHERE s.project_id = {genai_0:String}
            ) filtered
            ARRAY JOIN arrayConcat(
                arrayMap(k -> tuple('custom_attrs_string', k, 'string'), filtered.custom_attrs_string_keys),
                arrayMap(k -> tuple('custom_attrs_int', k, 'int'), filtered.custom_attrs_int_keys),
                arrayMap(k -> tuple('custom_attrs_float', k, 'float'), filtered.custom_attrs_float_keys),
                arrayMap(k -> tuple('custom_attrs_bool', k, 'bool'), filtered.custom_attrs_bool_keys)
            ) AS attr
            GROUP BY source, key, value_type
            ORDER BY span_count DESC, key ASC, source ASC
            LIMIT {genai_1:UInt64} OFFSET {genai_2:UInt64}
        """
        assert_sql(
            expected,
            {"genai_0": "p1", "genai_1": 201, "genai_2": 0},
            query,
            pb.get_params(),
        )

    def test_reuses_spans_filters(self) -> None:
        pb = ParamBuilder("genai")
        start = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
        query = make_custom_attrs_schema_query(
            pb,
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
                started_after=start,
                limit=10,
                offset=20,
            ),
        )

        expected = """
            SELECT tupleElement(attr, 1) AS source,
                   tupleElement(attr, 2) AS key,
                   tupleElement(attr, 3) AS value_type,
                   count() AS span_count
            FROM (
                SELECT s.custom_attrs_string.keys AS custom_attrs_string_keys,
                       s.custom_attrs_int.keys AS custom_attrs_int_keys,
                       s.custom_attrs_float.keys AS custom_attrs_float_keys,
                       s.custom_attrs_bool.keys AS custom_attrs_bool_keys
                FROM spans s
                WHERE s.project_id = {genai_0:String}
                AND s.started_at >= {genai_1:DateTime64(6)}
                AND (s.agent_name = {genai_2:String})
            ) filtered
            ARRAY JOIN arrayConcat(
                arrayMap(k -> tuple('custom_attrs_string', k, 'string'), filtered.custom_attrs_string_keys),
                arrayMap(k -> tuple('custom_attrs_int', k, 'int'), filtered.custom_attrs_int_keys),
                arrayMap(k -> tuple('custom_attrs_float', k, 'float'), filtered.custom_attrs_float_keys),
                arrayMap(k -> tuple('custom_attrs_bool', k, 'bool'), filtered.custom_attrs_bool_keys)
            ) AS attr
            GROUP BY source, key, value_type
            ORDER BY span_count DESC, key ASC, source ASC
            LIMIT {genai_3:UInt64} OFFSET {genai_4:UInt64}
        """
        expected_params = {
            "genai_0": "p1",
            "genai_1": start,
            "genai_2": "bot",
            "genai_3": 11,
            "genai_4": 20,
        }
        assert_sql(expected, expected_params, query, pb.get_params())


# ============================================================================
# make_agent_versions_{count,list}_query
# ============================================================================


class TestMakeAgentVersionsQueries:
    def test_count_basic(self) -> None:
        pb = ParamBuilder("genai")
        query = make_agent_versions_count_query(
            pb, AgentVersionsQueryReq(project_id="p1", agent_name="a1")
        )

        expected = """
            SELECT count() FROM (
                SELECT agent_version FROM agent_versions
                WHERE project_id = {genai_0:String}
                AND agent_name = {genai_1:String}
                GROUP BY agent_version
            )
        """
        assert_sql(
            expected,
            {"genai_0": "p1", "genai_1": "a1"},
            query,
            pb.get_params(),
        )

    def test_list_basic(self) -> None:
        pb = ParamBuilder("genai")
        query = make_agent_versions_list_query(
            pb, AgentVersionsQueryReq(project_id="p1", agent_name="a1")
        )

        expected = """
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
        """
        expected_params = {
            "genai_0": "p1",
            "genai_1": "a1",
            "genai_2": 100,
            "genai_3": 0,
        }
        assert_sql(expected, expected_params, query, pb.get_params())


# ============================================================================
# make_message_search_query
# ============================================================================


class TestMakeMessageSearchQuery:
    def test_basic(self) -> None:
        pb = ParamBuilder("genai")
        query = make_message_search_query(
            pb, AgentSearchReq(project_id="p1", query="hello")
        )

        expected = """
            SELECT conversation_id, conversation_name, agent_name,
                   span_id, trace_id, role,
                   substring(content, 1, 500) AS content,
                   lower(hex(content_digest)) AS content_digest, started_at
            FROM messages
            WHERE project_id = {genai_0:String}
            AND content LIKE {genai_1:String}
            ORDER BY started_at DESC
            LIMIT {genai_2:UInt64} OFFSET {genai_3:UInt64}
        """
        expected_params = {
            "genai_0": "p1",
            "genai_1": "%hello%",
            "genai_2": 20,
            "genai_3": 0,
        }
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_with_filters(self) -> None:
        pb = ParamBuilder("genai")
        query = make_message_search_query(
            pb,
            AgentSearchReq(
                project_id="p1",
                query="test",
                roles=["user", "assistant"],
                agent_name="bot",
                conversation_id="conv-1",
            ),
        )

        expected = """
            SELECT conversation_id, conversation_name, agent_name,
                   span_id, trace_id, role,
                   substring(content, 1, 500) AS content,
                   lower(hex(content_digest)) AS content_digest, started_at
            FROM messages
            WHERE project_id = {genai_0:String}
            AND content LIKE {genai_1:String}
              AND role IN {genai_2:Array(String)}
              AND agent_name = {genai_3:String}
              AND conversation_id = {genai_4:String}
            ORDER BY started_at DESC
            LIMIT {genai_5:UInt64} OFFSET {genai_6:UInt64}
        """
        expected_params = {
            "genai_0": "p1",
            "genai_1": "%test%",
            "genai_2": ["user", "assistant"],
            "genai_3": "bot",
            "genai_4": "conv-1",
            "genai_5": 20,
            "genai_6": 0,
        }
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_tool_role_alias_expands_to_tool_message_roles(self) -> None:
        pb = ParamBuilder("genai")
        query = make_message_search_query(
            pb,
            AgentSearchReq(project_id="p1", query="test", roles=["tool"]),
        )

        expected = """
            SELECT conversation_id, conversation_name, agent_name,
                   span_id, trace_id, role,
                   substring(content, 1, 500) AS content,
                   lower(hex(content_digest)) AS content_digest, started_at
            FROM messages
            WHERE project_id = {genai_0:String}
            AND content LIKE {genai_1:String}
              AND role IN {genai_2:Array(String)}
            ORDER BY started_at DESC
            LIMIT {genai_3:UInt64} OFFSET {genai_4:UInt64}
        """
        expected_params = {
            "genai_0": "p1",
            "genai_1": "%test%",
            "genai_2": ["tool_call", "tool_result"],
            "genai_3": 20,
            "genai_4": 0,
        }
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_escapes_like_wildcards(self) -> None:
        pb = ParamBuilder("genai")
        make_message_search_query(
            pb, AgentSearchReq(project_id="p1", query=r"88%_off\sale")
        )

        assert pb.get_params()["genai_1"] == r"%88\%\_off\\sale%"

    def test_trace_id_full_content_no_query(self) -> None:
        """Empty query drops the content LIKE; trace_id + full_content drive
        structured retrieval (used by the agent scoring fallback).
        """
        pb = ParamBuilder("genai")
        query = make_message_search_query(
            pb,
            AgentSearchReq(
                project_id="p1",
                query="",
                trace_id="t1",
                roles=["user", "assistant", "system"],
                truncate_content=False,
            ),
        )

        expected = """
            SELECT conversation_id, conversation_name, agent_name,
                   span_id, trace_id, role,
                   content AS content,
                   lower(hex(content_digest)) AS content_digest, started_at
            FROM messages
            WHERE project_id = {genai_0:String}
              AND trace_id = {genai_1:String}
              AND role IN {genai_2:Array(String)}
            ORDER BY started_at DESC
            LIMIT {genai_3:UInt64} OFFSET {genai_4:UInt64}
        """
        expected_params = {
            "genai_0": "p1",
            "genai_1": "t1",
            "genai_2": ["user", "assistant", "system"],
            "genai_3": 20,
            "genai_4": 0,
        }
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_limit_rejected_when_above_max(self) -> None:
        with pytest.raises(ValidationError):
            AgentSearchReq(project_id="p1", query="x", limit=5000)

    def test_limit_rejected_when_negative(self) -> None:
        with pytest.raises(ValidationError):
            AgentSearchReq(project_id="p1", query="x", limit=-1)

    def test_offset_rejected_when_negative(self) -> None:
        with pytest.raises(ValidationError):
            AgentSearchReq(project_id="p1", query="x", offset=-1)


# ============================================================================
# make_conversation_chat_spans_query
# ============================================================================


class TestMakeConversationChatSpansQuery:
    def test_basic(self) -> None:
        pb = ParamBuilder("genai")
        query = make_conversation_chat_spans_query(
            pb,
            AgentConversationChatReq(project_id="p1", conversation_id="c1"),
        )

        # Always cost-augmented (per-message + per-turn cost in the multi-turn
        # chat view). Compose the expected cost source from the same helper.
        expected_pb = ParamBuilder("genai")
        expected_pb.add("p1", param_type="String")  # genai_0: project
        expected_pb.add("c1", param_type="String")  # genai_1: conversation
        expected_pb.add(50, param_type="UInt64")  # genai_2: limit (default)
        expected_pb.add(0, param_type="UInt64")  # genai_3: offset
        source = cost_augmented_source_sql(expected_pb, "p1")
        expected = f"""
            SELECT {QUALIFIED_CHAT_VIEW_COLS}, {QUALIFIED_SPANS_COST_COLS}
            FROM {source} s
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
        assert_sql(expected, expected_pb.get_params(), query, pb.get_params())

    def test_with_pagination(self) -> None:
        pb = ParamBuilder("genai")
        query = make_conversation_chat_spans_query(
            pb,
            AgentConversationChatReq(
                project_id="p1", conversation_id="c1", limit=10, offset=20
            ),
        )

        expected_pb = ParamBuilder("genai")
        expected_pb.add("p1", param_type="String")  # genai_0: project
        expected_pb.add("c1", param_type="String")  # genai_1: conversation
        expected_pb.add(10, param_type="UInt64")  # genai_2: limit
        expected_pb.add(20, param_type="UInt64")  # genai_3: offset
        source = cost_augmented_source_sql(expected_pb, "p1")
        expected = f"""
            SELECT {QUALIFIED_CHAT_VIEW_COLS}, {QUALIFIED_SPANS_COST_COLS}
            FROM {source} s
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
        assert_sql(expected, expected_pb.get_params(), query, pb.get_params())

    def test_limit_rejected_above_max_turns(self) -> None:
        with pytest.raises(ValidationError):
            AgentConversationChatReq(project_id="p1", conversation_id="c1", limit=51)

    def test_offset_rejected_when_negative(self) -> None:
        with pytest.raises(ValidationError):
            AgentConversationChatReq(project_id="p1", conversation_id="c1", offset=-1)


class TestMakeConversationChatTurnsCountQuery:
    def test_basic(self) -> None:
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


class TestBuildOrderBy:
    def test_default(self) -> None:
        assert (
            build_order_by(None, SPAN_SORTABLE_COLS, "started_at DESC")
            == "started_at DESC"
        )

    def test_valid_single(self) -> None:
        sort = [AgentSortBy(field="input_tokens", direction="asc")]
        assert (
            build_order_by(sort, SPAN_SORTABLE_COLS, "fallback") == "input_tokens asc"
        )

    def test_rejects_invalid_field(self) -> None:
        sort = [AgentSortBy(field="'; DROP TABLE--", direction="asc")]
        with pytest.raises(ValueError, match="Invalid sort field"):
            build_order_by(sort, SPAN_SORTABLE_COLS, "started_at DESC")

    def test_rejects_invalid_direction(self) -> None:
        sort = [AgentSortBy.model_construct(field="input_tokens", direction="sideways")]
        with pytest.raises(ValueError, match="Invalid sort direction"):
            build_order_by(sort, SPAN_SORTABLE_COLS, "started_at DESC")

    def test_valid_multiple(self) -> None:
        sort = [
            AgentSortBy(field="started_at", direction="desc"),
            AgentSortBy(field="input_tokens", direction="asc"),
        ]
        assert (
            build_order_by(sort, SPAN_SORTABLE_COLS, "fallback")
            == "started_at desc, input_tokens asc"
        )
