"""Tests for agent observability read routes in RemoteHTTPTraceServer.

These tests verify that the agent read methods send the correct HTTP method,
URL path, and request body through the RemoteHTTPTraceServer client, and that
the response is parsed back into the correct typed model.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
from pydantic import BaseModel

from weave.trace_server.agents import types as agent_types
from weave.trace_server.interface.query import Query
from weave.trace_server_bindings.remote_http_trace_server import (
    RemoteHTTPTraceServer,
)

BASE_URL = "http://example.com"


@pytest.fixture
def server():
    """Create a RemoteHTTPTraceServer with mocked HTTP methods."""
    srv = RemoteHTTPTraceServer(BASE_URL, should_batch=False)
    yield srv
    if srv.call_processor:
        srv.call_processor.stop_accepting_new_work_and_flush_queue()
    if srv.feedback_processor:
        srv.feedback_processor.stop_accepting_new_work_and_flush_queue()


def _mock_response(json_data: dict | None = None) -> MagicMock:
    """Create a mock httpx.Response with the given JSON data."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = json_data or {}
    return resp


@pytest.mark.parametrize(
    ("method_name", "req", "expected_url", "res_type", "res_json"),
    [
        pytest.param(
            "agent_spans_query",
            agent_types.AgentSpansQueryReq(project_id="entity/project"),
            "/agents/spans/query",
            agent_types.AgentSpansQueryRes,
            {"spans": [], "groups": [], "total_count": 0},
            id="agent_spans_query",
        ),
        pytest.param(
            "agent_traces_chat",
            agent_types.AgentTraceChatReq(
                project_id="entity/project",
                trace_id="trace-123",
                include_feedback=True,
            ),
            "/agents/traces/chat",
            agent_types.AgentTraceChatRes,
            {"trace_id": "trace-123"},
            id="agent_traces_chat",
        ),
        pytest.param(
            "agent_conversation_chat",
            agent_types.AgentConversationChatReq(
                project_id="entity/project",
                conversation_id="conv-123",
                limit=10,
                offset=2,
            ),
            "/agents/conversations/chat",
            agent_types.AgentConversationChatRes,
            {"conversation_id": "conv-123"},
            id="agent_conversation_chat",
        ),
    ],
)
def test_agent_read_route_posts_request_and_parses_response(
    server,
    method_name: str,
    req: BaseModel,
    expected_url: str,
    res_type: type[BaseModel],
    res_json: dict,
):
    mock_resp = _mock_response(res_json)
    with patch.object(server, "post", return_value=mock_resp) as mock_post:
        result = getattr(server, method_name)(req)

    # Posts to the documented endpoint.
    mock_post.assert_called_once()
    assert mock_post.call_args[0][0] == expected_url

    # Sends the complete serialized request body (no fields dropped or renamed).
    sent_data = mock_post.call_args[1]["data"]
    assert json.loads(sent_data) == json.loads(req.model_dump_json(by_alias=True))

    # Parses the response into the correct typed model.
    assert isinstance(result, res_type)


def test_agent_spans_query_serializes_mongo_query_with_aliases(server):
    """The embedded Mongo-style `query` must keep its `$`-aliased operators on
    the wire — the one behavior that differs from a trivial passthrough.
    """
    req = agent_types.AgentSpansQueryReq(
        project_id="entity/project",
        query=Query.model_validate(
            {"$expr": {"$gt": [{"$getField": "retries"}, {"$literal": 3}]}}
        ),
    )
    mock_resp = _mock_response({"spans": [], "groups": [], "total_count": 0})
    with patch.object(server, "post", return_value=mock_resp) as mock_post:
        server.agent_spans_query(req)

    mock_post.assert_called_once()
    body = json.loads(mock_post.call_args[1]["data"])
    assert body["query"] == {
        "$expr": {"$gt": [{"$getField": "retries"}, {"$literal": 3}]}
    }
