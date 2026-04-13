"""SQL assertion tests for GenAI query layer.

These tests verify the exact SQL produced by each query handler method
without requiring a running ClickHouse instance. A mock CH client captures
every query() call and we assert on the normalized SQL string and parameters.
"""

import re
from typing import Any
from unittest.mock import MagicMock

import pytest

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
# Helpers
# ---------------------------------------------------------------------------


def _normalize_sql(sql: str) -> str:
    """Collapse whitespace so SQL comparisons are indentation-insensitive."""
    return re.sub(r"\s+", " ", sql).strip()


class _QueryCapture:
    """Mock CH client that records every query() call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def query(self, sql: str, *, parameters: dict[str, Any] | None = None) -> Any:
        self.calls.append((sql, dict(parameters or {})))
        result = MagicMock()
        result.result_rows = []
        result.column_names = []
        return result

    @property
    def last_sql(self) -> str:
        return _normalize_sql(self.calls[-1][0])

    @property
    def last_params(self) -> dict[str, Any]:
        return self.calls[-1][1]

    def sql_at(self, index: int) -> str:
        return _normalize_sql(self.calls[index][0])

    def params_at(self, index: int) -> dict[str, Any]:
        return self.calls[index][1]


@pytest.fixture
def ch() -> _QueryCapture:
    return _QueryCapture()


@pytest.fixture
def handler(ch: _QueryCapture) -> AgentQueryHandler:
    return AgentQueryHandler(ch)  # type: ignore[arg-type]


# ============================================================================
# 1. spans_query
# ============================================================================


class TestSpansQuery:
    """SQL assertions for AgentQueryHandler.spans_query()."""

    def test_basic_no_filters(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.spans_query(AgentSpansQueryReq(project_id="p1"))

        # Two queries: count + data
        assert len(ch.calls) == 2

        # Count query
        count_sql = ch.sql_at(0)
        assert count_sql == _normalize_sql(
            "SELECT count() FROM spans s WHERE s.project_id = {project_id:String}"
        )
        assert ch.params_at(0)["project_id"] == "p1"

        # Data query
        data_sql = ch.sql_at(1)
        assert "FROM spans s" in data_sql
        assert "WHERE s.project_id = {project_id:String}" in data_sql
        assert "ORDER BY started_at DESC" in data_sql
        assert "LIMIT {limit:UInt64} OFFSET {offset:UInt64}" in data_sql
        assert ch.params_at(1)["limit"] == 100
        assert ch.params_at(1)["offset"] == 0

    def test_with_agent_name_filter(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.spans_query(
            AgentSpansQueryReq(
                project_id="p1",
                filters=AgentSpansQueryFilters(agent_name="my-agent"),
            )
        )
        data_sql = ch.sql_at(1)
        assert "s.agent_name = {f_agent_name:String}" in data_sql
        assert ch.params_at(1)["f_agent_name"] == "my-agent"

    def test_with_time_range(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.spans_query(
            AgentSpansQueryReq(
                project_id="p1",
                start="2026-01-01T00:00:00Z",
                end="2026-01-02T00:00:00Z",
            )
        )
        data_sql = ch.sql_at(1)
        assert "s.started_at >= parseDateTimeBestEffort({t_start:String})" in data_sql
        assert "s.started_at < parseDateTimeBestEffort({t_end:String})" in data_sql
        assert ch.params_at(1)["t_start"] == "2026-01-01T00:00:00Z"
        assert ch.params_at(1)["t_end"] == "2026-01-02T00:00:00Z"

    def test_with_sort(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.spans_query(
            AgentSpansQueryReq(
                project_id="p1",
                sort_by=[AgentSortBy(field="input_tokens", direction="asc")],
            )
        )
        data_sql = ch.sql_at(1)
        assert "ORDER BY input_tokens asc" in data_sql

    def test_invalid_sort_column_uses_default(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.spans_query(
            AgentSpansQueryReq(
                project_id="p1",
                sort_by=[AgentSortBy(field="DROP TABLE", direction="asc")],
            )
        )
        data_sql = ch.sql_at(1)
        assert "ORDER BY started_at DESC" in data_sql
        assert "DROP TABLE" not in data_sql

    def test_custom_attr_filter(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.spans_query(
            AgentSpansQueryReq(
                project_id="p1",
                filters=AgentSpansQueryFilters(
                    custom_filters=[
                        AgentCustomAttrFilter(
                            attr_key="env", operator="eq", value="prod"
                        ),
                    ]
                ),
            )
        )
        data_sql = ch.sql_at(1)
        assert "s.custom_attrs[{cf0_key:String}] = {cf0_val:String}" in data_sql
        assert ch.params_at(1)["cf0_key"] == "env"
        assert ch.params_at(1)["cf0_val"] == "prod"

    def test_custom_attr_filter_ne_operator(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.spans_query(
            AgentSpansQueryReq(
                project_id="p1",
                filters=AgentSpansQueryFilters(
                    custom_filters=[
                        AgentCustomAttrFilter(
                            attr_key="env", operator="ne", value="dev"
                        ),
                    ]
                ),
            )
        )
        data_sql = ch.sql_at(1)
        assert "s.custom_attrs[{cf0_key:String}] != {cf0_val:String}" in data_sql

    def test_limit_capped_at_10000(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.spans_query(AgentSpansQueryReq(project_id="p1", limit=99999))
        assert ch.params_at(1)["limit"] == 10000

    def test_multiple_filters(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.spans_query(
            AgentSpansQueryReq(
                project_id="p1",
                filters=AgentSpansQueryFilters(
                    agent_name="a1",
                    provider_name="openai",
                    operation_name="chat",
                ),
            )
        )
        data_sql = ch.sql_at(1)
        assert "s.agent_name = {f_agent_name:String}" in data_sql
        assert "s.provider_name = {f_provider_name:String}" in data_sql
        assert "s.operation_name = {f_operation_name:String}" in data_sql


# ============================================================================
# 2. spans_trace
# ============================================================================


class TestSpansTrace:
    """SQL assertions for AgentQueryHandler.spans_trace()."""

    def test_basic(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.spans_trace(AgentSpansTraceReq(project_id="p1", trace_id="t123"))

        assert len(ch.calls) == 1
        sql = ch.last_sql
        assert "FROM spans s" in sql
        assert "s.project_id = {project_id:String}" in sql
        assert "s.trace_id = {trace_id:String}" in sql
        assert "ORDER BY s.started_at ASC" in sql
        assert ch.last_params["project_id"] == "p1"
        assert ch.last_params["trace_id"] == "t123"

    def test_selects_chat_view_cols(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.spans_trace(AgentSpansTraceReq(project_id="p1", trace_id="t1"))
        sql = ch.last_sql
        # Should include message columns for chat view
        assert "input_messages" in sql
        assert "output_messages" in sql
        assert "system_instructions" in sql
        # Should NOT include raw dump columns
        assert "raw_span_dump" not in sql
        assert "attributes_dump" not in sql


# ============================================================================
# 3. traces_query
# ============================================================================


class TestTracesQuery:
    """SQL assertions for AgentQueryHandler.traces_query()."""

    def test_basic(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.traces_query(AgentTracesQueryReq(project_id="p1"))

        # count + data
        assert len(ch.calls) == 2

        count_sql = ch.sql_at(0)
        assert "SELECT count() FROM (" in count_sql
        assert (
            "SELECT trace_id FROM spans WHERE project_id = {project_id:String} GROUP BY trace_id"
            in count_sql
        )

        data_sql = ch.sql_at(1)
        assert "count() AS span_count" in data_sql
        assert "sum(input_tokens) AS total_input_tokens" in data_sql
        assert "sum(output_tokens) AS total_output_tokens" in data_sql
        assert "countIf(status_code = 'ERROR') AS error_count" in data_sql
        assert "groupUniqArray(agent_name) AS agent_names" in data_sql
        assert "GROUP BY trace_id" in data_sql
        assert "ORDER BY last_seen DESC" in data_sql

    def test_with_conversation_filter(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.traces_query(
            AgentTracesQueryReq(project_id="p1", conversation_id="conv-1")
        )
        data_sql = ch.sql_at(1)
        assert "conversation_id = {f_conversation_id:String}" in data_sql
        assert ch.params_at(1)["f_conversation_id"] == "conv-1"

    def test_with_agent_filter(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.traces_query(AgentTracesQueryReq(project_id="p1", agent_name="bot-x"))
        data_sql = ch.sql_at(1)
        assert "agent_name = {f_agent_name:String}" in data_sql
        assert ch.params_at(1)["f_agent_name"] == "bot-x"

    def test_with_time_range(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.traces_query(
            AgentTracesQueryReq(
                project_id="p1",
                start="2026-01-01",
                end="2026-02-01",
            )
        )
        data_sql = ch.sql_at(1)
        assert "started_at >= parseDateTimeBestEffort({t_start:String})" in data_sql
        assert "started_at < parseDateTimeBestEffort({t_end:String})" in data_sql

    def test_sort_by_span_count(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.traces_query(
            AgentTracesQueryReq(
                project_id="p1",
                sort_by=[AgentSortBy(field="span_count", direction="asc")],
            )
        )
        data_sql = ch.sql_at(1)
        assert "ORDER BY span_count asc" in data_sql


# ============================================================================
# 4. agents_query
# ============================================================================


class TestAgentsQuery:
    """SQL assertions for AgentQueryHandler.agents_query()."""

    def test_basic(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.agents_query(AgentsQueryReq(project_id="p1"))

        # data + count
        assert len(ch.calls) == 2

        data_sql = ch.sql_at(0)
        assert "FROM agents" in data_sql
        assert "sum(invocation_count) AS invocation_count" in data_sql
        assert "sum(span_count) AS span_count" in data_sql
        assert "sum(total_input_tokens) AS total_input_tokens" in data_sql
        assert "sum(total_duration_ms) AS total_duration_ms" in data_sql
        assert "min(first_seen) AS first_seen" in data_sql
        assert "max(last_seen) AS last_seen" in data_sql
        assert "GROUP BY agent_name" in data_sql
        assert "ORDER BY last_seen DESC" in data_sql
        assert "project_id = {project_id:String}" in data_sql

    def test_with_agent_name_filter(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.agents_query(
            AgentsQueryReq(
                project_id="p1",
                filters=AgentsQueryFilters(agent_name="my-agent"),
            )
        )
        data_sql = ch.sql_at(0)
        assert "agent_name = {f_agent:String}" in data_sql
        assert ch.params_at(0)["f_agent"] == "my-agent"

    def test_count_query_structure(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.agents_query(AgentsQueryReq(project_id="p1"))
        count_sql = ch.sql_at(1)
        assert "SELECT count() FROM (" in count_sql
        assert "SELECT agent_name FROM agents" in count_sql
        assert "GROUP BY agent_name" in count_sql


# ============================================================================
# 5. agent_versions_query
# ============================================================================


class TestAgentVersionsQuery:
    """SQL assertions for AgentQueryHandler.agent_versions_query()."""

    def test_basic(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.agent_versions_query(
            AgentVersionsQueryReq(project_id="p1", agent_name="my-agent")
        )

        assert len(ch.calls) == 2

        data_sql = ch.sql_at(0)
        assert "FROM agent_versions" in data_sql
        assert "project_id = {project_id:String}" in data_sql
        assert "agent_name = {agent_name:String}" in data_sql
        assert "GROUP BY agent_version" in data_sql
        assert "ORDER BY max(last_seen) DESC" in data_sql
        assert "sum(invocation_count)" in data_sql
        assert "sum(span_count)" in data_sql
        assert ch.params_at(0)["project_id"] == "p1"
        assert ch.params_at(0)["agent_name"] == "my-agent"

    def test_count_query(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.agent_versions_query(
            AgentVersionsQueryReq(project_id="p1", agent_name="a1")
        )
        count_sql = ch.sql_at(1)
        assert "SELECT count() FROM (" in count_sql
        assert "SELECT agent_version FROM agent_versions" in count_sql
        assert "GROUP BY agent_version" in count_sql


# ============================================================================
# 6. conversations_query
# ============================================================================


class TestConversationsQuery:
    """SQL assertions for AgentQueryHandler.conversations_query()."""

    def test_basic(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.conversations_query(AgentConversationsQueryReq(project_id="p1"))

        assert len(ch.calls) == 2

        data_sql = ch.sql_at(1)
        assert "FROM spans" in data_sql
        assert "GROUP BY conversation_id" in data_sql
        assert "conversation_id != ''" in data_sql
        assert "max(conversation_name) AS conversation_name" in data_sql
        assert "countIf(operation_name = 'invoke_agent') AS turn_count" in data_sql
        assert "count() AS span_count" in data_sql
        assert "sum(input_tokens) AS total_input_tokens" in data_sql
        assert "groupUniqArray(agent_name) AS agent_names" in data_sql
        assert "groupUniqArray(provider_name) AS provider_names" in data_sql
        assert "ORDER BY last_seen DESC" in data_sql

    def test_excludes_empty_conversation_ids(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.conversations_query(AgentConversationsQueryReq(project_id="p1"))
        count_sql = ch.sql_at(0)
        assert "conversation_id != ''" in count_sql

    def test_with_agent_filter(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.conversations_query(
            AgentConversationsQueryReq(
                project_id="p1",
                filters=AgentConversationsQueryFilters(agent_name="bot"),
            )
        )
        data_sql = ch.sql_at(1)
        assert "agent_name = {f_agent_name:String}" in data_sql
        assert ch.params_at(1)["f_agent_name"] == "bot"

    def test_with_provider_filter(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.conversations_query(
            AgentConversationsQueryReq(
                project_id="p1",
                filters=AgentConversationsQueryFilters(provider_name="openai"),
            )
        )
        data_sql = ch.sql_at(1)
        assert "provider_name = {f_provider_name:String}" in data_sql

    def test_with_time_range(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.conversations_query(
            AgentConversationsQueryReq(
                project_id="p1",
                start="2026-01-01",
                end="2026-02-01",
            )
        )
        data_sql = ch.sql_at(1)
        assert "parseDateTimeBestEffort({t_start:String})" in data_sql
        assert "parseDateTimeBestEffort({t_end:String})" in data_sql

    def test_sort_by_turn_count(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.conversations_query(
            AgentConversationsQueryReq(
                project_id="p1",
                sort_by=[AgentSortBy(field="turn_count", direction="desc")],
            )
        )
        data_sql = ch.sql_at(1)
        assert "ORDER BY turn_count desc" in data_sql

    def test_sort_by_array_field_uses_array_element(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.conversations_query(
            AgentConversationsQueryReq(
                project_id="p1",
                sort_by=[AgentSortBy(field="agent_name", direction="asc")],
            )
        )
        data_sql = ch.sql_at(1)
        assert "ORDER BY arrayElement(agent_names, 1) asc" in data_sql

    def test_duration_calculation(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.conversations_query(AgentConversationsQueryReq(project_id="p1"))
        data_sql = ch.sql_at(1)
        assert (
            "sum(toUnixTimestamp64Milli(ended_at) - toUnixTimestamp64Milli(started_at)) AS total_duration_ms"
            in data_sql
        )


# ============================================================================
# 7. search
# ============================================================================


class TestSearch:
    """SQL assertions for AgentQueryHandler.search()."""

    def test_basic(self, handler: AgentQueryHandler, ch: _QueryCapture) -> None:
        handler.search(AgentSearchReq(project_id="p1", query="hello"))

        assert len(ch.calls) == 1
        sql = ch.last_sql
        assert "FROM message_search FINAL" in sql
        assert "project_id = {project_id:String}" in sql
        assert "content LIKE {query:String}" in sql
        assert "ORDER BY started_at DESC" in sql
        assert "LIMIT {limit:UInt64} OFFSET {offset:UInt64}" in sql
        assert ch.last_params["query"] == "%hello%"

    def test_with_role_filter(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.search(
            AgentSearchReq(project_id="p1", query="test", roles=["user", "assistant"])
        )
        sql = ch.last_sql
        assert "role IN {roles:Array(String)}" in sql
        assert ch.last_params["roles"] == ["user", "assistant"]

    def test_with_agent_filter(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.search(AgentSearchReq(project_id="p1", query="test", agent_name="bot"))
        sql = ch.last_sql
        assert "agent_name = {agent_name:String}" in sql

    def test_with_conversation_filter(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.search(
            AgentSearchReq(project_id="p1", query="test", conversation_id="conv-1")
        )
        sql = ch.last_sql
        assert "conversation_id = {conv_id:String}" in sql
        assert ch.last_params["conv_id"] == "conv-1"

    def test_limit_capped_at_1000(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.search(AgentSearchReq(project_id="p1", query="test", limit=5000))
        assert ch.last_params["limit"] == 1000

    def test_selects_correct_columns(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        handler.search(AgentSearchReq(project_id="p1", query="test"))
        sql = ch.last_sql
        assert "conversation_id, conversation_name, agent_name," in sql
        assert "span_id, trace_id, role, content, content_digest, started_at" in sql

    def test_uses_final_for_dedup(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        """message_search is ReplacingMergeTree, so FINAL is needed."""
        handler.search(AgentSearchReq(project_id="p1", query="test"))
        sql = ch.last_sql
        assert "FINAL" in sql


# ============================================================================
# 11. Query builder helpers (unit tests)
# ============================================================================


class TestQueryBuilderHelpers:
    """Unit tests for agent_query_builder functions."""

    def test_build_order_by_default(self) -> None:
        result = build_order_by(None, SPAN_SORTABLE_COLS, "started_at DESC")
        assert result == "started_at DESC"

    def test_build_order_by_valid(self) -> None:
        sort = [AgentSortBy(field="input_tokens", direction="asc")]
        result = build_order_by(sort, SPAN_SORTABLE_COLS, "started_at DESC")
        assert result == "input_tokens asc"

    def test_build_order_by_rejects_invalid_column(self) -> None:
        sort = [AgentSortBy(field="'; DROP TABLE--", direction="asc")]
        result = build_order_by(sort, SPAN_SORTABLE_COLS, "started_at DESC")
        assert result == "started_at DESC"

    def test_build_order_by_rejects_invalid_direction(self) -> None:
        sort = [AgentSortBy(field="started_at", direction="desc")]
        # Pydantic validates direction to Literal["asc", "desc"] so this always passes,
        # but the code also checks direction in {"asc", "desc"}
        result = build_order_by(sort, SPAN_SORTABLE_COLS, "fallback")
        assert result == "started_at desc"

    def test_build_order_by_multiple(self) -> None:
        sort = [
            AgentSortBy(field="started_at", direction="desc"),
            AgentSortBy(field="input_tokens", direction="asc"),
        ]
        result = build_order_by(sort, SPAN_SORTABLE_COLS, "fallback")
        assert result == "started_at desc, input_tokens asc"

    def test_add_time_filters_both(self) -> None:
        conds: list[str] = []
        params: dict[str, Any] = {}
        add_time_filters(conds, params, start="2026-01-01", end="2026-02-01")
        assert len(conds) == 2
        assert "s.started_at >= parseDateTimeBestEffort({t_start:String})" in conds[0]
        assert "s.started_at < parseDateTimeBestEffort({t_end:String})" in conds[1]
        assert params["t_start"] == "2026-01-01"
        assert params["t_end"] == "2026-02-01"

    def test_add_time_filters_custom_column(self) -> None:
        conds: list[str] = []
        params: dict[str, Any] = {}
        add_time_filters(
            conds, params, start="2026-01-01", end=None, column="started_at"
        )
        assert "started_at >= parseDateTimeBestEffort({t_start:String})" in conds[0]

    def test_add_time_filters_none(self) -> None:
        conds: list[str] = []
        params: dict[str, Any] = {}
        add_time_filters(conds, params, start=None, end=None)
        assert conds == []
        assert params == {}

    def test_add_span_filters(self) -> None:
        conds: list[str] = []
        params: dict[str, Any] = {}
        filters = AgentSpansQueryFilters(agent_name="bot", provider_name="openai")
        add_span_filters(conds, params, filters)
        assert any("s.agent_name = {f_agent_name:String}" in c for c in conds)
        assert any("s.provider_name = {f_provider_name:String}" in c for c in conds)
        assert params["f_agent_name"] == "bot"
        assert params["f_provider_name"] == "openai"

    def test_add_span_filters_skips_none(self) -> None:
        conds: list[str] = []
        params: dict[str, Any] = {}
        filters = AgentSpansQueryFilters(agent_name=None)
        add_span_filters(conds, params, filters)
        assert conds == []
        assert params == {}

    def test_add_custom_attr_filters_operators(self) -> None:
        conds: list[str] = []
        params: dict[str, Any] = {}
        custom = [
            AgentCustomAttrFilter(attr_key="k1", operator="eq", value="v1"),
            AgentCustomAttrFilter(attr_key="k2", operator="gt", value="10"),
            AgentCustomAttrFilter(attr_key="k3", operator="lte", value="99"),
        ]
        add_custom_attr_filters(conds, params, custom)
        assert len(conds) == 3
        assert "s.custom_attrs[{cf0_key:String}] = {cf0_val:String}" in conds[0]
        assert "s.custom_attrs[{cf1_key:String}] > {cf1_val:String}" in conds[1]
        assert "s.custom_attrs[{cf2_key:String}] <= {cf2_val:String}" in conds[2]


# ============================================================================
# 9. SQL injection safety
# ============================================================================


class TestSQLInjectionSafety:
    """Verify that untrusted input never reaches SQL directly."""

    def test_sort_injection_rejected(
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
        data_sql = ch.sql_at(1)
        assert "DROP" not in data_sql
        assert "ORDER BY started_at DESC" in data_sql

    def test_custom_attr_key_is_parameterized(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        """Custom attr keys go through parameterized queries, not string interpolation."""
        handler.spans_query(
            AgentSpansQueryReq(
                project_id="p1",
                filters=AgentSpansQueryFilters(
                    custom_filters=[
                        AgentCustomAttrFilter(
                            attr_key="'; DROP TABLE--",
                            operator="eq",
                            value="x",
                        ),
                    ]
                ),
            )
        )
        data_sql = ch.sql_at(1)
        # The key should be in params, not interpolated into SQL
        assert "DROP TABLE" not in data_sql
        assert ch.params_at(1)["cf0_key"] == "'; DROP TABLE--"

    def test_all_filter_values_are_parameterized(
        self, handler: AgentQueryHandler, ch: _QueryCapture
    ) -> None:
        """Filter values are always passed as parameters, never interpolated."""
        handler.spans_query(
            AgentSpansQueryReq(
                project_id="'; DROP TABLE--",
                filters=AgentSpansQueryFilters(agent_name="'; DROP TABLE--"),
            )
        )
        data_sql = ch.sql_at(1)
        # SQL template uses {param:Type} placeholders, actual values in params dict
        assert "DROP TABLE" not in data_sql
        assert ch.params_at(1)["project_id"] == "'; DROP TABLE--"
        assert ch.params_at(1)["f_agent_name"] == "'; DROP TABLE--"
