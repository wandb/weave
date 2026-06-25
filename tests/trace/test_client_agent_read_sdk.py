"""Tests for WeaveClient agent observability read convenience methods.

These assert the SDK methods build the correct request (project_id inference,
agent_name -> query translation, defaults, pass-through) and return the
server's response. They mirror test_client_annotation_queue_sdk.py: a minimal
fake server captures the request the client sends, which is client-side logic
(not the server-side logic CLAUDE.md reserves for the real client fixture).
"""

from __future__ import annotations

import datetime

import pytest

from weave.trace.weave_client import WeaveClient
from weave.trace_server.agents.types import (
    DEFAULT_AGENT_CUSTOM_ATTR_SCHEMA_LIMIT,
    DEFAULT_AGENT_QUERY_LIMIT,
    DEFAULT_SEARCH_LIMIT,
    AgentConversationChatRes,
    AgentCustomAttrsSchemaRes,
    AgentSearchRes,
    AgentSortBy,
    AgentSpansQueryRes,
    AgentSpanStatsMetricSpec,
    AgentSpanStatsRes,
    AgentSpanValueRef,
    AgentsQueryRes,
    AgentTraceChatRes,
    AgentVersionsQueryRes,
)
from weave.trace_server.interface.query import Query

AGENT_NAME_EXPR = {"$eq": [{"$getField": "agent_name"}, {"$literal": "my-agent"}]}
GT_EXPR = {"$gt": [{"$getField": "input_tokens"}, {"$literal": 100}]}


class FakeAgentReadServer:
    """Captures the request each agent read method sends and returns canned data."""

    def __init__(self) -> None:
        self.requests: dict = {}
        self.agents_res = AgentsQueryRes(agents=[], total_count=0)
        self.versions_res = AgentVersionsQueryRes(versions=[], total_count=0)
        self.spans_res = AgentSpansQueryRes(spans=[], groups=[], total_count=0)
        self.turn_res = AgentTraceChatRes(trace_id="trace-123")
        self.turns_res = AgentConversationChatRes(conversation_id="conv-123")
        self.stats_res = AgentSpanStatsRes(
            start=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            end=datetime.datetime(2024, 1, 1, 1, tzinfo=datetime.timezone.utc),
            timezone="UTC",
        )
        self.schema_res = AgentCustomAttrsSchemaRes()
        self.search_res = AgentSearchRes(results=[])

    def agent_agents_query(self, req):
        self.requests["agents"] = req
        return self.agents_res

    def agent_versions_query(self, req):
        self.requests["versions"] = req
        return self.versions_res

    def agent_spans_query(self, req):
        self.requests["spans"] = req
        return self.spans_res

    def agent_traces_chat(self, req):
        self.requests["turn"] = req
        return self.turn_res

    def agent_conversation_chat(self, req):
        self.requests["turns"] = req
        return self.turns_res

    def agent_spans_stats(self, req):
        self.requests["stats"] = req
        return self.stats_res

    def agent_custom_attrs_schema(self, req):
        self.requests["schema"] = req
        return self.schema_res

    def agent_search(self, req):
        self.requests["search"] = req
        return self.search_res


def _make_client(server: FakeAgentReadServer) -> WeaveClient:
    return WeaveClient(
        "entity",
        "project",
        server,  # type: ignore[arg-type]
        ensure_project_exists=False,
    )


def test_agent_read_sdk_methods_build_requests():
    server = FakeAgentReadServer()
    client = _make_client(server)
    sort_by = [AgentSortBy(field="last_seen", direction="desc")]

    agents_res = client.get_agents(
        agent_name="my-agent", limit=20, offset=5, sort_by=sort_by
    )
    assert agents_res is server.agents_res
    req = server.requests["agents"]
    assert req.project_id == "entity/project"
    assert req.filters.agent_name == "my-agent"
    assert req.limit == 20
    assert req.offset == 5
    assert req.sort_by == sort_by

    versions_res = client.get_agent_versions(
        agent_name="my-agent", limit=7, offset=1, sort_by=sort_by
    )
    assert versions_res is server.versions_res
    req = server.requests["versions"]
    assert req.project_id == "entity/project"
    assert req.agent_name == "my-agent"
    assert req.limit == 7
    assert req.offset == 1
    assert req.sort_by == sort_by

    turn_res = client.get_agent_turn(trace_id="trace-123", include_feedback=True)
    assert turn_res is server.turn_res
    req = server.requests["turn"]
    assert req.project_id == "entity/project"
    assert req.trace_id == "trace-123"
    assert req.include_feedback is True

    turns_res = client.get_agent_turns(
        conversation_id="conv-123", limit=10, offset=2, include_feedback=True
    )
    assert turns_res is server.turns_res
    req = server.requests["turns"]
    assert req.project_id == "entity/project"
    assert req.conversation_id == "conv-123"
    assert req.limit == 10
    assert req.offset == 2
    assert req.include_feedback is True


def test_get_agents_without_agent_name_omits_filters():
    server = FakeAgentReadServer()
    client = _make_client(server)

    client.get_agents()

    req = server.requests["agents"]
    assert req.project_id == "entity/project"
    assert req.filters is None
    assert req.limit == DEFAULT_AGENT_QUERY_LIMIT
    assert req.offset == 0


@pytest.mark.parametrize(
    ("agent_name", "query", "expected_query"),
    [
        pytest.param(None, None, None, id="neither"),
        pytest.param(
            "my-agent",
            None,
            Query.model_validate({"$expr": AGENT_NAME_EXPR}),
            id="agent_name_only",
        ),
        pytest.param(
            None,
            Query.model_validate({"$expr": GT_EXPR}),
            Query.model_validate({"$expr": GT_EXPR}),
            id="query_only",
        ),
        pytest.param(
            "my-agent",
            Query.model_validate({"$expr": GT_EXPR}),
            Query.model_validate({"$expr": {"$and": [AGENT_NAME_EXPR, GT_EXPR]}}),
            id="agent_name_and_query_combined_with_and",
        ),
    ],
)
def test_get_agent_spans_query_translation(agent_name, query, expected_query):
    server = FakeAgentReadServer()
    client = _make_client(server)

    spans_res = client.get_agent_spans(agent_name=agent_name, query=query)

    assert spans_res is server.spans_res
    req = server.requests["spans"]
    assert req.project_id == "entity/project"
    assert req.query == expected_query


def test_agent_read_sdk_stats_schema_search_build_requests():
    server = FakeAgentReadServer()
    client = _make_client(server)

    metric = AgentSpanStatsMetricSpec(
        alias="input_tokens",
        value_type="number",
        value=AgentSpanValueRef(source="field", key="usage.input_tokens"),
        aggregations=["sum"],
    )
    start = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    stats_res = client.get_agent_span_stats(
        start=start, metrics=[metric], granularity=3600
    )
    assert stats_res is server.stats_res
    req = server.requests["stats"]
    assert req.project_id == "entity/project"
    assert req.start == start
    assert req.metrics == [metric]
    assert req.granularity == 3600
    assert req.timezone == "UTC"

    schema_res = client.get_agent_custom_attrs_schema(limit=25, offset=5)
    assert schema_res is server.schema_res
    req = server.requests["schema"]
    assert req.project_id == "entity/project"
    assert req.limit == 25
    assert req.offset == 5

    search_res = client.search_agents(query="boom", agent_name="my-agent", limit=10)
    assert search_res is server.search_res
    req = server.requests["search"]
    assert req.project_id == "entity/project"
    assert req.query == "boom"
    assert req.agent_name == "my-agent"
    assert req.limit == 10


def test_agent_read_sdk_search_and_schema_defaults():
    server = FakeAgentReadServer()
    client = _make_client(server)

    client.search_agents()
    req = server.requests["search"]
    assert req.project_id == "entity/project"
    assert req.query == ""
    assert req.limit == DEFAULT_SEARCH_LIMIT
    assert req.offset == 0

    client.get_agent_custom_attrs_schema()
    req = server.requests["schema"]
    assert req.project_id == "entity/project"
    assert req.limit == DEFAULT_AGENT_CUSTOM_ATTR_SCHEMA_LIMIT
    assert req.offset == 0
