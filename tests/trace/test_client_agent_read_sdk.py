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
from weave.trace_server.interface.query import Query
from weave.trace_server.trace_server_interface import agent_types

AGENT_NAME_EXPR = {"$eq": [{"$getField": "agent_name"}, {"$literal": "my-agent"}]}
GT_EXPR = {"$gt": [{"$getField": "input_tokens"}, {"$literal": 100}]}

SORT_BY = [agent_types.AgentSortBy(field="last_seen", direction="desc")]
METRIC = agent_types.AgentSpanStatsMetricSpec(
    alias="input_tokens",
    value_type="number",
    value=agent_types.AgentSpanValueRef(source="field", key="usage.input_tokens"),
    aggregations=["sum"],
)
START = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)


class FakeAgentReadServer:
    """Captures the request each agent read method sends and returns canned data."""

    def __init__(self) -> None:
        self.requests: dict = {}
        self.agents_res = agent_types.AgentsQueryRes(agents=[], total_count=0)
        self.versions_res = agent_types.AgentVersionsQueryRes(
            versions=[], total_count=0
        )
        self.spans_res = agent_types.AgentSpansQueryRes(
            spans=[], groups=[], total_count=0
        )
        self.turn_res = agent_types.AgentTraceChatRes(trace_id="trace-123")
        self.turns_res = agent_types.AgentConversationChatRes(
            conversation_id="conv-123"
        )
        self.stats_res = agent_types.AgentSpanStatsRes(
            start=START, end=START + datetime.timedelta(hours=1), timezone="UTC"
        )
        self.schema_res = agent_types.AgentCustomAttrsSchemaRes()
        self.search_res = agent_types.AgentSearchRes(results=[])

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


@pytest.mark.parametrize(
    ("method", "kwargs", "key", "res_attr", "expected"),
    [
        pytest.param(
            "get_agents",
            {"agent_name": "my-agent", "limit": 20, "offset": 5, "sort_by": SORT_BY},
            "agents",
            "agents_res",
            {
                "filters": agent_types.AgentsQueryFilters(agent_name="my-agent"),
                "limit": 20,
                "offset": 5,
                "sort_by": SORT_BY,
            },
            id="get_agents",
        ),
        pytest.param(
            "get_agents",
            {},
            "agents",
            "agents_res",
            {
                "filters": None,
                "limit": agent_types.DEFAULT_AGENT_QUERY_LIMIT,
                "offset": 0,
            },
            id="get_agents_defaults",
        ),
        pytest.param(
            "get_agent_versions",
            {"agent_name": "my-agent", "limit": 7, "offset": 1, "sort_by": SORT_BY},
            "versions",
            "versions_res",
            {"agent_name": "my-agent", "limit": 7, "offset": 1, "sort_by": SORT_BY},
            id="get_agent_versions",
        ),
        pytest.param(
            "get_agent_turn",
            {"trace_id": "trace-123", "include_feedback": True},
            "turn",
            "turn_res",
            {"trace_id": "trace-123", "include_feedback": True},
            id="get_agent_turn",
        ),
        pytest.param(
            "get_agent_turns",
            {
                "conversation_id": "conv-123",
                "limit": 10,
                "offset": 2,
                "include_feedback": True,
            },
            "turns",
            "turns_res",
            {
                "conversation_id": "conv-123",
                "limit": 10,
                "offset": 2,
                "include_feedback": True,
            },
            id="get_agent_turns",
        ),
        pytest.param(
            "get_agent_span_stats",
            {"start": START, "metrics": [METRIC], "granularity": 3600},
            "stats",
            "stats_res",
            {
                "start": START,
                "metrics": [METRIC],
                "granularity": 3600,
                "timezone": "UTC",
            },
            id="get_agent_span_stats",
        ),
        pytest.param(
            "get_agent_custom_attributes",
            {"limit": 25, "offset": 5},
            "schema",
            "schema_res",
            {"limit": 25, "offset": 5},
            id="get_agent_custom_attributes",
        ),
        pytest.param(
            "get_agent_custom_attributes",
            {},
            "schema",
            "schema_res",
            {"limit": agent_types.DEFAULT_AGENT_CUSTOM_ATTR_SCHEMA_LIMIT, "offset": 0},
            id="get_agent_custom_attributes_defaults",
        ),
        pytest.param(
            "search_agents",
            {"query": "boom", "agent_name": "my-agent", "limit": 10},
            "search",
            "search_res",
            {"query": "boom", "agent_name": "my-agent", "limit": 10},
            id="search_agents",
        ),
        pytest.param(
            "search_agents",
            {},
            "search",
            "search_res",
            {"query": "", "limit": agent_types.DEFAULT_SEARCH_LIMIT, "offset": 0},
            id="search_agents_defaults",
        ),
    ],
)
def test_method_builds_request(method, kwargs, key, res_attr, expected):
    server = FakeAgentReadServer()
    client = _make_client(server)

    res = getattr(client, method)(**kwargs)

    assert res is getattr(server, res_attr)
    req = server.requests[key]
    assert req.project_id == "entity/project"
    for attr, value in expected.items():
        assert getattr(req, attr) == value


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
