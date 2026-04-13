"""SQL assertion tests for GenAI query layer.

Each test verifies the exact SQL and parameters produced by a query handler
method. Uses sqlparse to normalize whitespace so expected SQL can be written
as readable multi-line strings.
"""

import copy
from typing import Any
from unittest.mock import MagicMock

import pytest
import sqlparse

from weave.trace_server.agent_clickhouse import AgentQueryHandler
from weave.trace_server.agent_query_builder import (
    SPAN_SORTABLE_COLS,
    add_custom_attr_filters,
    add_span_filters,
    add_time_filters,
    build_order_by,
)
from weave.trace_server.agent_types import (
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

# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------


def _assert_sql(
    expected_query: str,
    expected_params: dict,
    actual_query: str,
    actual_params: dict,
) -> None:
    """Assert SQL and params match, using sqlparse to normalize formatting."""
    expected_formatted = sqlparse.format(expected_query, reindent=True).strip()
    actual_formatted = sqlparse.format(actual_query, reindent=True).strip()
    assert expected_formatted == actual_formatted, (
        f"\nExpected:\n{expected_formatted}\n\nGot:\n{actual_formatted}"
    )
    assert expected_params == actual_params, (
        f"\nExpected params: {expected_params}\n\nGot params: {actual_params}"
    )


class _QueryCapture:
    """Mock CH client that records every query() call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def query(self, sql: str, *, parameters: dict[str, Any] | None = None) -> Any:
        self.calls.append((sql, copy.deepcopy(parameters or {})))
        result = MagicMock()
        result.result_rows = []
        result.column_names = []
        return result


@pytest.fixture
def ch() -> _QueryCapture:
    return _QueryCapture()


@pytest.fixture
def handler(ch: _QueryCapture) -> AgentQueryHandler:
    return AgentQueryHandler(ch)  # type: ignore[arg-type]


# ============================================================================
# spans_query
# ============================================================================


class TestSpansQuery:
    def test_basic(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.spans_query(AgentSpansQueryReq(project_id="p1"))

        assert len(ch.calls) == 2

        _assert_sql(
            "SELECT count() FROM spans s WHERE s.project_id = {project_id:String}",
            {"project_id": "p1"},
            ch.calls[0][0],
            ch.calls[0][1],
        )

        _assert_sql(
            """
            SELECT project_id, trace_id, span_id, parent_span_id, span_name,
                   span_kind, started_at, ended_at, created_at,
                   status_code, status_message, operation_name, provider_name,
                   agent_name, agent_id, agent_description, agent_version,
                   request_model, response_model, response_id,
                   input_tokens, output_tokens, total_tokens, reasoning_tokens,
                   cache_creation_input_tokens, cache_read_input_tokens,
                   conversation_id, conversation_name,
                   tool_name, tool_type, tool_call_id,
                   finish_reasons, error_type, custom_attrs,
                   wb_user_id, wb_run_id
            FROM spans s
            WHERE s.project_id = {project_id:String}
            ORDER BY started_at DESC
            LIMIT {limit:UInt64} OFFSET {offset:UInt64}
            """,
            {"project_id": "p1", "limit": 100, "offset": 0},
            ch.calls[1][0],
            ch.calls[1][1],
        )

    def test_with_filters_time_sort(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.spans_query(
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
                sort_by=[AgentSortBy(field="input_tokens", direction="asc")],
            )
        )

        _assert_sql(
            """
            SELECT project_id, trace_id, span_id, parent_span_id, span_name,
                   span_kind, started_at, ended_at, created_at,
                   status_code, status_message, operation_name, provider_name,
                   agent_name, agent_id, agent_description, agent_version,
                   request_model, response_model, response_id,
                   input_tokens, output_tokens, total_tokens, reasoning_tokens,
                   cache_creation_input_tokens, cache_read_input_tokens,
                   conversation_id, conversation_name,
                   tool_name, tool_type, tool_call_id,
                   finish_reasons, error_type, custom_attrs,
                   wb_user_id, wb_run_id
            FROM spans s
            WHERE s.project_id = {project_id:String}
              AND s.started_at >= parseDateTimeBestEffort({t_start:String})
              AND s.started_at < parseDateTimeBestEffort({t_end:String})
              AND s.agent_name = {f_agent_name:String}
              AND s.custom_attrs[{cf0_key:String}] = {cf0_val:String}
            ORDER BY input_tokens asc
            LIMIT {limit:UInt64} OFFSET {offset:UInt64}
            """,
            {
                "project_id": "p1",
                "t_start": "2026-01-01",
                "t_end": "2026-02-01",
                "f_agent_name": "bot",
                "cf0_key": "env",
                "cf0_val": "prod",
                "limit": 100,
                "offset": 0,
            },
            ch.calls[1][0],
            ch.calls[1][1],
        )

    def test_invalid_sort_uses_default(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.spans_query(
            AgentSpansQueryReq(
                project_id="p1",
                sort_by=[AgentSortBy(field="DROP TABLE", direction="asc")],
            )
        )
        assert "DROP TABLE" not in ch.calls[1][0]
        assert "ORDER BY started_at DESC" in ch.calls[1][0]

    def test_limit_capped(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.spans_query(AgentSpansQueryReq(project_id="p1", limit=99999))
        assert ch.calls[1][1]["limit"] == 10000


# ============================================================================
# spans_trace
# ============================================================================


class TestSpansTrace:
    def test_basic(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.spans_trace(AgentSpansTraceReq(project_id="p1", trace_id="t1"))

        assert len(ch.calls) == 1
        sql = ch.calls[0][0]
        params = ch.calls[0][1]

        assert "FROM spans s" in sql
        assert "s.project_id = {project_id:String}" in sql
        assert "s.trace_id = {trace_id:String}" in sql
        assert "ORDER BY s.started_at ASC" in sql
        # Chat view cols present
        assert "input_messages" in sql
        assert "output_messages" in sql
        # Raw dumps not present
        assert "raw_span_dump" not in sql
        assert "attributes_dump" not in sql
        assert params == {"project_id": "p1", "trace_id": "t1"}


# ============================================================================
# traces_query
# ============================================================================


class TestTracesQuery:
    def test_basic(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.traces_query(AgentTracesQueryReq(project_id="p1"))

        assert len(ch.calls) == 2

        _assert_sql(
            """
            SELECT count() FROM (
                SELECT trace_id FROM spans
                WHERE project_id = {project_id:String}
                GROUP BY trace_id
            )
            """,
            {"project_id": "p1"},
            ch.calls[0][0],
            ch.calls[0][1],
        )

        _assert_sql(
            """
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
            WHERE project_id = {project_id:String}
            GROUP BY trace_id
            ORDER BY last_seen DESC
            LIMIT {limit:UInt64} OFFSET {offset:UInt64}
            """,
            {"project_id": "p1", "limit": 100, "offset": 0},
            ch.calls[1][0],
            ch.calls[1][1],
        )

    def test_with_filters(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.traces_query(
            AgentTracesQueryReq(
                project_id="p1",
                conversation_id="conv-1",
                agent_name="bot",
                start="2026-01-01",
                end="2026-02-01",
            )
        )
        sql = ch.calls[1][0]
        params = ch.calls[1][1]
        assert "conversation_id = {f_conversation_id:String}" in sql
        assert "agent_name = {f_agent_name:String}" in sql
        assert "parseDateTimeBestEffort({t_start:String})" in sql
        assert params["f_conversation_id"] == "conv-1"
        assert params["f_agent_name"] == "bot"


# ============================================================================
# agents_query
# ============================================================================


class TestAgentsQuery:
    def test_basic(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.agents_query(AgentsQueryReq(project_id="p1"))

        assert len(ch.calls) == 2

        _assert_sql(
            """
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
            WHERE project_id = {project_id:String}
            GROUP BY agent_name
            ORDER BY last_seen DESC
            LIMIT {limit:UInt64} OFFSET {offset:UInt64}
            """,
            {"project_id": "p1", "limit": 100, "offset": 0},
            ch.calls[0][0],
            ch.calls[0][1],
        )

        _assert_sql(
            """
            SELECT count() FROM (
                SELECT agent_name FROM agents
                WHERE project_id = {project_id:String}
                GROUP BY agent_name
            )
            """,
            {"project_id": "p1", "limit": 100, "offset": 0},
            ch.calls[1][0],
            ch.calls[1][1],
        )

    def test_with_filter(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.agents_query(
            AgentsQueryReq(
                project_id="p1",
                filters=AgentsQueryFilters(agent_name="my-agent"),
            )
        )
        assert "agent_name = {f_agent:String}" in ch.calls[0][0]
        assert ch.calls[0][1]["f_agent"] == "my-agent"


# ============================================================================
# agent_versions_query
# ============================================================================


class TestAgentVersionsQuery:
    def test_basic(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.agent_versions_query(
            AgentVersionsQueryReq(project_id="p1", agent_name="a1")
        )

        assert len(ch.calls) == 2

        _assert_sql(
            """
            SELECT agent_version,
                   sum(invocation_count), sum(span_count),
                   sum(total_input_tokens), sum(total_output_tokens),
                   sum(total_duration_ms), sum(error_count),
                   min(first_seen), max(last_seen)
            FROM agent_versions
            WHERE project_id = {project_id:String}
              AND agent_name = {agent_name:String}
            GROUP BY agent_version
            ORDER BY max(last_seen) DESC
            LIMIT {limit:UInt64} OFFSET {offset:UInt64}
            """,
            {"project_id": "p1", "agent_name": "a1", "limit": 100, "offset": 0},
            ch.calls[0][0],
            ch.calls[0][1],
        )

        _assert_sql(
            """
            SELECT count() FROM (
                SELECT agent_version FROM agent_versions
                WHERE project_id = {project_id:String}
                  AND agent_name = {agent_name:String}
                GROUP BY agent_version
            )
            """,
            {"project_id": "p1", "agent_name": "a1", "limit": 100, "offset": 0},
            ch.calls[1][0],
            ch.calls[1][1],
        )


# ============================================================================
# conversations_query
# ============================================================================


class TestConversationsQuery:
    def test_basic(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.conversations_query(AgentConversationsQueryReq(project_id="p1"))

        assert len(ch.calls) == 2

        _assert_sql(
            """
            SELECT count() FROM (
                SELECT conversation_id FROM spans
                WHERE project_id = {project_id:String}
                  AND conversation_id != ''
                GROUP BY conversation_id
            )
            """,
            {"project_id": "p1"},
            ch.calls[0][0],
            ch.calls[0][1],
        )

        _assert_sql(
            """
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
            WHERE project_id = {project_id:String}
              AND conversation_id != ''
            GROUP BY conversation_id
            ORDER BY last_seen DESC
            LIMIT {limit:UInt64} OFFSET {offset:UInt64}
            """,
            {"project_id": "p1", "limit": 100, "offset": 0},
            ch.calls[1][0],
            ch.calls[1][1],
        )

    def test_with_filter_and_array_sort(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.conversations_query(
            AgentConversationsQueryReq(
                project_id="p1",
                filters=AgentConversationsQueryFilters(agent_name="bot"),
                sort_by=[AgentSortBy(field="agent_name", direction="asc")],
            )
        )
        sql = ch.calls[1][0]
        params = ch.calls[1][1]
        assert "agent_name = {f_agent_name:String}" in sql
        assert "ORDER BY arrayElement(agent_names, 1) asc" in sql
        assert params["f_agent_name"] == "bot"


# ============================================================================
# search
# ============================================================================


class TestSearch:
    def test_basic(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.search(AgentSearchReq(project_id="p1", query="hello"))

        assert len(ch.calls) == 1

        _assert_sql(
            """
            SELECT conversation_id, conversation_name, agent_name,
                   span_id, trace_id, role, content, content_digest, started_at
            FROM message_search FINAL
            WHERE project_id = {project_id:String}
              AND content LIKE {query:String}
            ORDER BY started_at DESC
            LIMIT {limit:UInt64} OFFSET {offset:UInt64}
            """,
            {"project_id": "p1", "query": "%hello%", "limit": 20, "offset": 0},
            ch.calls[0][0],
            ch.calls[0][1],
        )

    def test_with_filters(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.search(
            AgentSearchReq(
                project_id="p1",
                query="test",
                agent_name="bot",
                roles=["user", "assistant"],
            )
        )

        _assert_sql(
            """
            SELECT conversation_id, conversation_name, agent_name,
                   span_id, trace_id, role, content, content_digest, started_at
            FROM message_search FINAL
            WHERE project_id = {project_id:String}
              AND content LIKE {query:String}
              AND role IN {roles:Array(String)}
              AND agent_name = {agent_name:String}
            ORDER BY started_at DESC
            LIMIT {limit:UInt64} OFFSET {offset:UInt64}
            """,
            {
                "project_id": "p1",
                "query": "%test%",
                "roles": ["user", "assistant"],
                "agent_name": "bot",
                "limit": 20,
                "offset": 0,
            },
            ch.calls[0][0],
            ch.calls[0][1],
        )

    def test_limit_capped(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.search(AgentSearchReq(project_id="p1", query="x", limit=5000))
        assert ch.calls[0][1]["limit"] == 1000


# ============================================================================
# Query builder helpers
# ============================================================================


class TestQueryBuilderHelpers:
    def test_build_order_by_default(self) -> None:
        assert (
            build_order_by(None, SPAN_SORTABLE_COLS, "started_at DESC")
            == "started_at DESC"
        )

    def test_build_order_by_valid(self) -> None:
        sort = [AgentSortBy(field="input_tokens", direction="asc")]
        assert (
            build_order_by(sort, SPAN_SORTABLE_COLS, "fallback") == "input_tokens asc"
        )

    def test_build_order_by_rejects_invalid(self) -> None:
        sort = [AgentSortBy(field="'; DROP TABLE--", direction="asc")]
        assert (
            build_order_by(sort, SPAN_SORTABLE_COLS, "started_at DESC")
            == "started_at DESC"
        )

    def test_build_order_by_multiple(self) -> None:
        sort = [
            AgentSortBy(field="started_at", direction="desc"),
            AgentSortBy(field="input_tokens", direction="asc"),
        ]
        assert (
            build_order_by(sort, SPAN_SORTABLE_COLS, "fallback")
            == "started_at desc, input_tokens asc"
        )

    def test_add_time_filters(self) -> None:
        conds: list[str] = []
        params: dict[str, Any] = {}
        add_time_filters(conds, params, start="2026-01-01", end="2026-02-01")
        assert len(conds) == 2
        assert params == {"t_start": "2026-01-01", "t_end": "2026-02-01"}

    def test_add_time_filters_none(self) -> None:
        conds: list[str] = []
        params: dict[str, Any] = {}
        add_time_filters(conds, params, start=None, end=None)
        assert conds == []

    def test_add_span_filters(self) -> None:
        conds: list[str] = []
        params: dict[str, Any] = {}
        add_span_filters(
            conds,
            params,
            AgentSpansQueryFilters(agent_name="bot", provider_name="openai"),
        )
        assert params["f_agent_name"] == "bot"
        assert params["f_provider_name"] == "openai"

    def test_add_span_filters_skips_none(self) -> None:
        conds: list[str] = []
        params: dict[str, Any] = {}
        add_span_filters(conds, params, AgentSpansQueryFilters())
        assert conds == []

    def test_add_custom_attr_filters(self) -> None:
        conds: list[str] = []
        params: dict[str, Any] = {}
        add_custom_attr_filters(
            conds,
            params,
            [
                AgentCustomAttrFilter(attr_key="k1", operator="eq", value="v1"),
                AgentCustomAttrFilter(attr_key="k2", operator="gt", value="10"),
                AgentCustomAttrFilter(attr_key="k3", operator="lte", value="99"),
            ],
        )
        assert len(conds) == 3
        assert "= {cf0_val:String}" in conds[0]
        assert "> {cf1_val:String}" in conds[1]
        assert "<= {cf2_val:String}" in conds[2]


# ============================================================================
# SQL injection safety
# ============================================================================


class TestSQLInjectionSafety:
    def test_sort_injection(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.spans_query(
            AgentSpansQueryReq(
                project_id="p1",
                sort_by=[
                    AgentSortBy(
                        field="started_at; DROP TABLE spans--", direction="desc"
                    )
                ],
            )
        )
        assert "DROP" not in ch.calls[1][0]

    def test_custom_attr_key_parameterized(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.spans_query(
            AgentSpansQueryReq(
                project_id="p1",
                filters=AgentSpansQueryFilters(
                    custom_filters=[
                        AgentCustomAttrFilter(
                            attr_key="'; DROP TABLE--", operator="eq", value="x"
                        )
                    ]
                ),
            )
        )
        assert "DROP TABLE" not in ch.calls[1][0]
        assert ch.calls[1][1]["cf0_key"] == "'; DROP TABLE--"

    def test_filter_values_parameterized(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.spans_query(
            AgentSpansQueryReq(
                project_id="'; DROP TABLE--",
                filters=AgentSpansQueryFilters(agent_name="'; DROP TABLE--"),
            )
        )
        assert "DROP TABLE" not in ch.calls[1][0]
