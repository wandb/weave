"""Tests for WeaveClient agent observability read convenience methods.

These assert the SDK methods build the correct request (project_id inference,
agent_name -> query translation, defaults, pass-through) and return the
server's response. They mirror test_client_annotation_queue_sdk.py: a minimal
fake server captures the request the client sends, which is client-side logic
(not the server-side logic CLAUDE.md reserves for the real client fixture).

get_agents / get_agent_versions / get_agent_spans return a PaginatedIterator
(like get_calls), so they are exercised against a paging fake server below.
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


# ---------------------------------------------------------------------------
# Single-response methods (turn / turns / span_stats / custom_attributes / search)
# ---------------------------------------------------------------------------


class FakeAgentReadServer:
    """Captures the request each non-iterator read method sends, returns canned data."""

    def __init__(self) -> None:
        self.requests: dict = {}
        self.turn_res = agent_types.AgentTraceChatRes(trace_id="trace-123")
        self.turns_res = agent_types.AgentConversationChatRes(
            conversation_id="conv-123"
        )
        self.stats_res = agent_types.AgentSpanStatsRes(
            start=START, end=START + datetime.timedelta(hours=1), timezone="UTC"
        )
        self.schema_res = agent_types.AgentCustomAttrsSchemaRes()
        self.search_res = agent_types.AgentSearchRes(results=[])

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


def _make_client(server: FakeAgentReadServer | FakePagingAgentServer) -> WeaveClient:
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


# ---------------------------------------------------------------------------
# Paginated iterator methods (get_agents / get_agent_versions / get_agent_spans)
# ---------------------------------------------------------------------------


def _agent(i: int) -> agent_types.AgentSchema:
    return agent_types.AgentSchema(
        project_id="entity/project",
        agent_name=f"agent-{i}",
        invocation_count=0,
        span_count=0,
        total_input_tokens=0,
        total_output_tokens=0,
        total_duration_ms=0,
        error_count=0,
        first_seen=None,
        last_seen=None,
    )


def _agent_version(i: int) -> agent_types.AgentVersionSchema:
    return agent_types.AgentVersionSchema(
        project_id="entity/project",
        agent_name="agent-0",
        agent_version=f"v{i}",
        invocation_count=0,
        span_count=0,
        total_input_tokens=0,
        total_output_tokens=0,
        total_duration_ms=0,
        error_count=0,
        first_seen=None,
        last_seen=None,
    )


def _agent_span(i: int) -> agent_types.AgentSpanSchema:
    return agent_types.AgentSpanSchema(
        project_id="entity/project",
        trace_id="trace-0",
        span_id=f"span-{i}",
    )


class FakePagingAgentServer:
    """Serves offset/limit pages and records the request each iterator fetch sends."""

    def __init__(
        self,
        *,
        agents: list | None = None,
        versions: list | None = None,
        spans: list | None = None,
    ) -> None:
        self._agents = agents or []
        self._versions = versions or []
        self._spans = spans or []
        self.requests: dict = {}  # last request per kind
        self.fetches: list[tuple[int, int]] = []  # (offset, limit) per request

    def agent_agents_query(self, req):
        self.requests["agents"] = req
        self.fetches.append((req.offset, req.limit))
        page = self._agents[req.offset : req.offset + req.limit]
        return agent_types.AgentsQueryRes(agents=page, total_count=len(self._agents))

    def agent_versions_query(self, req):
        self.requests["versions"] = req
        self.fetches.append((req.offset, req.limit))
        page = self._versions[req.offset : req.offset + req.limit]
        return agent_types.AgentVersionsQueryRes(
            versions=page, total_count=len(self._versions)
        )

    def agent_spans_query(self, req):
        self.requests["spans"] = req
        self.fetches.append((req.offset, req.limit))
        page = self._spans[req.offset : req.offset + req.limit]
        return agent_types.AgentSpansQueryRes(
            spans=page, groups=[], total_count=len(self._spans)
        )


@pytest.mark.parametrize(
    ("method", "kwargs", "kind", "builder", "key_attr"),
    [
        pytest.param("get_agents", {}, "agents", _agent, "agent_name", id="get_agents"),
        pytest.param(
            "get_agent_versions",
            {"agent_name": "agent-0"},
            "versions",
            _agent_version,
            "agent_version",
            id="get_agent_versions",
        ),
        pytest.param(
            "get_agent_spans", {}, "spans", _agent_span, "span_id", id="get_agent_spans"
        ),
    ],
)
def test_iterator_method_pages_through_all_items(
    method, kwargs, kind, builder, key_attr
):
    items = [builder(i) for i in range(5)]
    server = FakePagingAgentServer(**{kind: items})
    client = _make_client(server)

    iterator = getattr(client, method)(page_size=2, **kwargs)

    # Iterates every item, in order, transparently fetching each page.
    collected = list(iterator)
    assert [getattr(x, key_attr) for x in collected] == [
        getattr(x, key_attr) for x in items
    ]
    # Fetched in pages of page_size (2) at increasing offsets, not one request.
    # (list()/len() also issue a cheap limit=1 size probe, excluded by filter.)
    page_fetches = [f for f in server.fetches if f[1] == 2]
    assert page_fetches == [(0, 2), (2, 2), (4, 2)]
    # project_id is inferred on every request.
    assert server.requests[kind].project_id == "entity/project"
    # len() reports the server total_count.
    assert len(iterator) == 5


def test_get_agents_respects_limit():
    server = FakePagingAgentServer(agents=[_agent(i) for i in range(10)])
    client = _make_client(server)

    iterator = client.get_agents(limit=3, page_size=2)

    # Yields only `limit` items even though the server holds 10...
    assert [a.agent_name for a in iterator] == ["agent-0", "agent-1", "agent-2"]
    # ...and len() reflects the cap, not the raw total_count.
    assert len(iterator) == 3


def test_get_agents_respects_offset():
    server = FakePagingAgentServer(agents=[_agent(i) for i in range(5)])
    client = _make_client(server)

    iterator = client.get_agents(offset=2, page_size=2)

    assert [a.agent_name for a in iterator] == ["agent-2", "agent-3", "agent-4"]
    assert len(iterator) == 3  # 5 total - 2 skipped


@pytest.mark.parametrize(
    ("method", "kind", "builder", "kwargs", "expected"),
    [
        pytest.param(
            "get_agents",
            "agents",
            _agent,
            {"agent_name": "agent-0", "sort_by": SORT_BY},
            {
                "filters": agent_types.AgentsQueryFilters(agent_name="agent-0"),
                "sort_by": SORT_BY,
            },
            id="get_agents",
        ),
        pytest.param(
            "get_agent_versions",
            "versions",
            _agent_version,
            {"agent_name": "agent-0", "sort_by": SORT_BY},
            {"agent_name": "agent-0", "sort_by": SORT_BY},
            id="get_agent_versions",
        ),
    ],
)
def test_iterator_method_builds_request(method, kind, builder, kwargs, expected):
    server = FakePagingAgentServer(**{kind: [builder(0)]})
    client = _make_client(server)

    list(getattr(client, method)(**kwargs))

    req = server.requests[kind]
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
    server = FakePagingAgentServer(spans=[_agent_span(0)])
    client = _make_client(server)

    list(client.get_agent_spans(agent_name=agent_name, query=query))

    req = server.requests["spans"]
    assert req.project_id == "entity/project"
    assert req.query == expected_query
