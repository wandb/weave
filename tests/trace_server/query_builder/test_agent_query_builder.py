"""SQL shape assertions for every ``make_*_query`` function in the agent
query builder.

Each test builds a ``ParamBuilder``, calls the builder, and compares the full
formatted SQL + param dict against an expected value, matching the style of
``test_annotation_queues_query_builder.py`` etc.
"""

import sqlparse

from weave.trace_server.agent_types import (
    AgentConversationChatReq,
    AgentConversationsQueryFilters,
    AgentConversationsQueryReq,
    AgentCustomAttrFilter,
    AgentSearchReq,
    AgentSortBy,
    AgentSpansQueryFilters,
    AgentSpansQueryReq,
    AgentSpansTraceReq,
    AgentsQueryFilters,
    AgentsQueryReq,
    AgentTracesQueryReq,
    AgentVersionsQueryReq,
)
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.agent_query_builder import (
    CHAT_VIEW_COLS,
    SPAN_SORTABLE_COLS,
    SPANS_LIST_COLS,
    build_order_by,
    make_agent_versions_count_query,
    make_agent_versions_list_query,
    make_agents_count_query,
    make_agents_list_query,
    make_conversation_chat_spans_query,
    make_conversations_count_query,
    make_conversations_list_query,
    make_message_search_query,
    make_spans_count_query,
    make_spans_list_query,
    make_spans_trace_query,
    make_traces_count_query,
    make_traces_list_query,
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


# ============================================================================
# make_spans_count_query
# ============================================================================


class TestMakeSpansCountQuery:
    def test_basic(self) -> None:
        pb = ParamBuilder("genai")
        query = make_spans_count_query(pb, AgentSpansQueryReq(project_id="p1"))

        expected = "SELECT count() FROM spans s WHERE s.project_id = {genai_0:String}"
        assert_sql(expected, {"genai_0": "p1"}, query, pb.get_params())

    def test_with_filters_and_time(self) -> None:
        pb = ParamBuilder("genai")
        query = make_spans_count_query(
            pb,
            AgentSpansQueryReq(
                project_id="p1",
                filters=AgentSpansQueryFilters(
                    agent_name="bot",
                    custom_filters=[
                        AgentCustomAttrFilter(
                            attr_key="env", operator="eq", value="prod"
                        )
                    ],
                ),
                start="2026-01-01",
                end="2026-02-01",
            ),
        )

        expected = """
            SELECT count() FROM spans s
            WHERE s.project_id = {genai_0:String}
              AND s.started_at >= parseDateTimeBestEffort({genai_1:String})
              AND s.started_at < parseDateTimeBestEffort({genai_2:String})
              AND s.agent_name = {genai_3:String}
              AND s.custom_attrs[{genai_4:String}] = {genai_5:String}
        """
        expected_params = {
            "genai_0": "p1",
            "genai_1": "2026-01-01",
            "genai_2": "2026-02-01",
            "genai_3": "bot",
            "genai_4": "env",
            "genai_5": "prod",
        }
        assert_sql(expected, expected_params, query, pb.get_params())


# ============================================================================
# make_spans_list_query
# ============================================================================


class TestMakeSpansListQuery:
    def test_basic(self) -> None:
        pb = ParamBuilder("genai")
        query = make_spans_list_query(pb, AgentSpansQueryReq(project_id="p1"))

        expected = f"""
            SELECT {SPANS_LIST_COLS}
            FROM spans s
            WHERE s.project_id = {{genai_0:String}}
            ORDER BY started_at DESC
            LIMIT {{genai_1:UInt64}} OFFSET {{genai_2:UInt64}}
        """
        expected_params = {"genai_0": "p1", "genai_1": 100, "genai_2": 0}
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

        expected = f"""
            SELECT {SPANS_LIST_COLS}
            FROM spans s
            WHERE s.project_id = {{genai_0:String}}
            ORDER BY input_tokens asc
            LIMIT {{genai_1:UInt64}} OFFSET {{genai_2:UInt64}}
        """
        expected_params = {"genai_0": "p1", "genai_1": 100, "genai_2": 0}
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_limit_capped_to_max(self) -> None:
        pb = ParamBuilder("genai")
        make_spans_list_query(
            pb, AgentSpansQueryReq(project_id="p1", limit=99999)
        )
        assert pb.get_params()["genai_1"] == 10000

    def test_rejects_sort_injection(self) -> None:
        """Unknown sort columns fall back to the default, preventing injection."""
        pb = ParamBuilder("genai")
        query = make_spans_list_query(
            pb,
            AgentSpansQueryReq(
                project_id="p1",
                sort_by=[
                    AgentSortBy(
                        field="started_at; DROP TABLE spans--", direction="desc"
                    )
                ],
            ),
        )
        assert "DROP" not in query
        assert "ORDER BY started_at DESC" in query


# ============================================================================
# make_spans_trace_query
# ============================================================================


class TestMakeSpansTraceQuery:
    def test_basic(self) -> None:
        pb = ParamBuilder("genai")
        query = make_spans_trace_query(
            pb, AgentSpansTraceReq(project_id="p1", trace_id="t1")
        )

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
# make_traces_count_query
# ============================================================================


class TestMakeTracesCountQuery:
    def test_basic(self) -> None:
        pb = ParamBuilder("genai")
        query = make_traces_count_query(pb, AgentTracesQueryReq(project_id="p1"))

        expected = """
            SELECT count() FROM (
                SELECT trace_id FROM spans
                WHERE project_id = {genai_0:String}
                GROUP BY trace_id
            )
        """
        assert_sql(expected, {"genai_0": "p1"}, query, pb.get_params())

    def test_with_filters(self) -> None:
        pb = ParamBuilder("genai")
        query = make_traces_count_query(
            pb,
            AgentTracesQueryReq(
                project_id="p1",
                conversation_id="conv-1",
                agent_name="bot",
                agent_version="v2",
                start="2026-01-01",
                end="2026-02-01",
            ),
        )

        expected = """
            SELECT count() FROM (
                SELECT trace_id FROM spans
                WHERE project_id = {genai_0:String}
                  AND conversation_id = {genai_1:String}
                  AND agent_name = {genai_2:String}
                  AND agent_version = {genai_3:String}
                  AND started_at >= parseDateTimeBestEffort({genai_4:String})
                  AND started_at < parseDateTimeBestEffort({genai_5:String})
                GROUP BY trace_id
            )
        """
        expected_params = {
            "genai_0": "p1",
            "genai_1": "conv-1",
            "genai_2": "bot",
            "genai_3": "v2",
            "genai_4": "2026-01-01",
            "genai_5": "2026-02-01",
        }
        assert_sql(expected, expected_params, query, pb.get_params())


# ============================================================================
# make_traces_list_query
# ============================================================================


class TestMakeTracesListQuery:
    def test_basic(self) -> None:
        pb = ParamBuilder("genai")
        query = make_traces_list_query(pb, AgentTracesQueryReq(project_id="p1"))

        expected = """
            SELECT trace_id,
                   count() AS span_count,
                   sum(input_tokens) AS total_input_tokens,
                   sum(output_tokens) AS total_output_tokens,
                   countIf(status_code = 'ERROR') AS error_count,
                   max(conversation_id) AS conversation_id,
                   groupUniqArray(agent_name) AS agent_names,
                   groupUniqArray(agent_version) AS agent_versions,
                   groupUniqArray(request_model) AS request_models,
                   min(started_at) AS first_seen,
                   max(started_at) AS last_seen
            FROM spans
            WHERE project_id = {genai_0:String}
            GROUP BY trace_id
            ORDER BY last_seen DESC, trace_id
            LIMIT {genai_1:UInt64} OFFSET {genai_2:UInt64}
        """
        expected_params = {"genai_0": "p1", "genai_1": 100, "genai_2": 0}
        assert_sql(expected, expected_params, query, pb.get_params())


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
# make_conversations_{count,list}_query
# ============================================================================


class TestMakeConversationsQueries:
    def test_count_basic(self) -> None:
        pb = ParamBuilder("genai")
        query = make_conversations_count_query(
            pb, AgentConversationsQueryReq(project_id="p1")
        )

        expected = """
            SELECT count() FROM (
                SELECT conversation_id FROM spans
                WHERE project_id = {genai_0:String}
                  AND conversation_id != ''
                GROUP BY conversation_id
            )
        """
        assert_sql(expected, {"genai_0": "p1"}, query, pb.get_params())

    def test_list_basic(self) -> None:
        pb = ParamBuilder("genai")
        query = make_conversations_list_query(
            pb, AgentConversationsQueryReq(project_id="p1")
        )

        expected = """
            SELECT conversation_id,
                   max(conversation_name) AS conversation_name,
                   countIf(operation_name = 'invoke_agent') AS turn_count,
                   count() AS span_count,
                   sum(input_tokens) AS total_input_tokens,
                   sum(output_tokens) AS total_output_tokens,
                   sum(toUnixTimestamp64Milli(ended_at) - toUnixTimestamp64Milli(started_at)) AS total_duration_ms,
                   countIf(status_code = 'ERROR') AS error_count,
                   groupUniqArray(agent_name) AS agent_names,
                   groupUniqArray(agent_version) AS agent_versions,
                   groupUniqArray(provider_name) AS provider_names,
                   groupUniqArray(request_model) AS request_models,
                   min(started_at) AS first_seen,
                   max(started_at) AS last_seen
            FROM spans
            WHERE project_id = {genai_0:String}
              AND conversation_id != ''
            GROUP BY conversation_id
            ORDER BY last_seen DESC, conversation_id
            LIMIT {genai_1:UInt64} OFFSET {genai_2:UInt64}
        """
        expected_params = {"genai_0": "p1", "genai_1": 100, "genai_2": 0}
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_list_sort_by_array_alias(self) -> None:
        """Sorting by ``agent_name`` must emit ``arrayElement(agent_names, 1)``."""
        pb = ParamBuilder("genai")
        query = make_conversations_list_query(
            pb,
            AgentConversationsQueryReq(
                project_id="p1",
                filters=AgentConversationsQueryFilters(agent_name="bot"),
                sort_by=[AgentSortBy(field="agent_name", direction="asc")],
            ),
        )
        assert "ORDER BY arrayElement(agent_names, 1) asc" in query
        assert pb.get_params() == {
            "genai_0": "p1",
            "genai_1": "bot",
            "genai_2": 100,
            "genai_3": 0,
        }


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
                   span_id, trace_id, role, content, content_digest, started_at
            FROM message_search FINAL
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
                   span_id, trace_id, role, content, content_digest, started_at
            FROM message_search FINAL
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

    def test_limit_capped_to_max(self) -> None:
        pb = ParamBuilder("genai")
        make_message_search_query(
            pb, AgentSearchReq(project_id="p1", query="x", limit=5000)
        )
        assert pb.get_params()["genai_2"] == 1000


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

        expected = f"""
            SELECT {CHAT_VIEW_COLS} FROM spans s
            WHERE s.project_id = {{genai_0:String}}
              AND s.conversation_id = {{genai_1:String}}
            ORDER BY s.started_at ASC
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
        assert (
            build_order_by(sort, SPAN_SORTABLE_COLS, "started_at DESC")
            == "started_at DESC"
        )

    def test_valid_multiple(self) -> None:
        sort = [
            AgentSortBy(field="started_at", direction="desc"),
            AgentSortBy(field="input_tokens", direction="asc"),
        ]
        assert (
            build_order_by(sort, SPAN_SORTABLE_COLS, "fallback")
            == "started_at desc, input_tokens asc"
        )


# ============================================================================
# Parameterization safety (values never inlined into SQL)
# ============================================================================


class TestParameterization:
    def test_custom_attr_key_is_parameterized(self) -> None:
        """Custom-attribute keys go through ParamBuilder, not string interpolation."""
        pb = ParamBuilder("genai")
        query = make_spans_list_query(
            pb,
            AgentSpansQueryReq(
                project_id="p1",
                filters=AgentSpansQueryFilters(
                    custom_filters=[
                        AgentCustomAttrFilter(
                            attr_key="'; DROP TABLE--", operator="eq", value="x"
                        )
                    ]
                ),
            ),
        )
        assert "DROP TABLE" not in query
        assert "'; DROP TABLE--" in pb.get_params().values()

    def test_filter_values_are_parameterized(self) -> None:
        pb = ParamBuilder("genai")
        query = make_spans_list_query(
            pb,
            AgentSpansQueryReq(
                project_id="'; DROP TABLE--",
                filters=AgentSpansQueryFilters(agent_name="'; DROP TABLE--"),
            ),
        )
        assert "DROP TABLE" not in query
