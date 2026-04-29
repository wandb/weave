"""SQL shape assertions for every ``make_*_query`` function in the agent
query builder.

Each test builds a ``ParamBuilder``, calls the builder, and compares the full
formatted SQL + param dict against an expected value, matching the style of
``test_annotation_queues_query_builder.py`` etc.
"""

import datetime

import pytest
import sqlparse
from pydantic import ValidationError

from weave.trace_server.agents.types import (
    AgentConversationChatReq,
    AgentGroupByRef,
    AgentSearchReq,
    AgentSortBy,
    AgentSpansQueryReq,
    AgentsQueryFilters,
    AgentsQueryReq,
    AgentVersionsQueryReq,
)
from weave.trace_server.interface.query import Query
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
    make_conversation_chat_turns_count_query,
    make_message_search_query,
    make_spans_count_query,
    make_spans_list_query,
    make_trace_detail_spans_query,
    resolve_group_by,
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

        expected = """
            SELECT count() FROM spans s
            WHERE s.project_id = {genai_0:String}
              AND s.started_at >= {genai_1:DateTime64(6)}
              AND s.started_at < {genai_2:DateTime64(6)}
              AND ((s.agent_name = {genai_3:String}) AND (s.custom_attrs_string[{genai_4:String}] = {genai_5:String}))
        """
        expected_params = {
            "genai_0": "p1",
            "genai_1": start,
            "genai_2": end,
            "genai_3": "bot",
            "genai_4": "env",
            "genai_5": "prod",
        }
        assert_sql(expected, expected_params, query, pb.get_params())


# ============================================================================
# make_spans_list_query (ungrouped)
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


# ============================================================================
# make_spans_count_query (grouped)
# ============================================================================


#: The fixed aggregate tail emitted by the grouped list query, as it would
#: appear after ``SELECT <group_cols>,``. Used to keep test expected SQL
#: readable without duplicating the bundle across every test.
_GROUPED_AGG_TAIL = """count() AS span_count,
               countIf(s.operation_name = 'invoke_agent') AS invocation_count,
               uniqExact(s.conversation_id) AS conversation_count,
               sum(s.input_tokens) AS total_input_tokens,
               sum(s.output_tokens) AS total_output_tokens,
               sum(toUnixTimestamp64Milli(s.ended_at) - toUnixTimestamp64Milli(s.started_at)) AS total_duration_ms,
               countIf(s.status_code = 'ERROR') AS error_count,
               groupUniqArray(s.agent_name) AS agent_names,
               groupUniqArray(s.agent_version) AS agent_versions,
               groupUniqArray(s.provider_name) AS provider_names,
               groupUniqArray(s.request_model) AS request_models,
               groupUniqArray(s.conversation_name) AS conversation_names,
               min(s.started_at) AS first_seen,
               max(s.started_at) AS last_seen"""


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
                SELECT s.custom_attrs_string[{genai_1:String}] FROM spans s
                WHERE s.project_id = {genai_0:String}
                GROUP BY s.custom_attrs_string[{genai_1:String}]
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

        expected = f"""
            SELECT s.trace_id AS trace_id,
                   {_GROUPED_AGG_TAIL}
            FROM spans s
            WHERE s.project_id = {{genai_0:String}}
            GROUP BY trace_id
            ORDER BY last_seen DESC
            LIMIT {{genai_1:UInt64}} OFFSET {{genai_2:UInt64}}
        """
        expected_params = {"genai_0": "p1", "genai_1": 100, "genai_2": 0}
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

        expected = f"""
            SELECT s.conversation_id AS conversation_id,
                   {_GROUPED_AGG_TAIL}
            FROM spans s
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

        expected = f"""
            SELECT s.custom_attrs_string[{{genai_3:String}}] AS env,
                   {_GROUPED_AGG_TAIL}
            FROM spans s
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
        }
        assert_sql(expected, expected_params, query, pb.get_params())

    def test_group_by_multi_column_and_sort_by_alias(self) -> None:
        pb = ParamBuilder("genai")
        query = make_spans_list_query(
            pb,
            AgentSpansQueryReq(
                project_id="p1",
                group_by=[
                    AgentGroupByRef(source="column", key="agent_name"),
                    AgentGroupByRef(source="column", key="request_model"),
                ],
                sort_by=[AgentSortBy(field="agent_name", direction="asc")],
            ),
        )

        expected = f"""
            SELECT s.agent_name AS agent_name,
                   s.request_model AS request_model,
                   {_GROUPED_AGG_TAIL}
            FROM spans s
            WHERE s.project_id = {{genai_0:String}}
            GROUP BY agent_name, request_model
            ORDER BY agent_name asc
            LIMIT {{genai_1:UInt64}} OFFSET {{genai_2:UInt64}}
        """
        expected_params = {"genai_0": "p1", "genai_1": 100, "genai_2": 0}
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
                    AgentGroupByRef(source="column", key="agent_name"),
                    AgentGroupByRef(source="column", key="agent_name"),
                ],
            )

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
        assert out == [("s.custom_attrs_string[{genai_0:String}]", "env")]

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
        assert out == [("s.custom_attrs_string[{genai_0:String}]", "spaced_attr")]


# ============================================================================
# make_trace_detail_spans_query (internal helper — chat view only)
# ============================================================================


class TestMakeTraceDetailSpansQuery:
    def test_basic(self) -> None:
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
        assert_sql(
            expected,
            {"genai_0": "p1", "genai_1": "c1", "genai_2": 50, "genai_3": 0},
            query,
            pb.get_params(),
        )

    def test_with_pagination(self) -> None:
        pb = ParamBuilder("genai")
        query = make_conversation_chat_spans_query(
            pb,
            AgentConversationChatReq(
                project_id="p1", conversation_id="c1", limit=10, offset=20
            ),
        )

        assert "LIMIT {genai_2:UInt64} OFFSET {genai_3:UInt64}" in query
        assert pb.get_params() == {
            "genai_0": "p1",
            "genai_1": "c1",
            "genai_2": 10,
            "genai_3": 20,
        }

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
