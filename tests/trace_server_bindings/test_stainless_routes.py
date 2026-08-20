"""Tests for the requests StainlessRemoteHTTPTraceServer sends.

These tests drive the binding through the vendored generated client over an
httpx.MockTransport, so they cover both the request the generated resource
builds and the way the binding reads the response back.
"""

from __future__ import annotations

import json

import httpx

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.stainless_remote_http_trace_server import (
    StainlessRemoteHTTPTraceServer,
)
from weave.vendor.weave_server_sdk import Client as StainlessClient

BASE_URL = "http://example.com"


def _mock_server(
    response: httpx.Response,
) -> tuple[StainlessRemoteHTTPTraceServer, list[httpx.Request]]:
    """Return a server that answers every request with `response`.

    The binding builds its own generated client and takes no transport, so the
    test swaps in one backed by an httpx.MockTransport.
    """
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return response

    server = StainlessRemoteHTTPTraceServer(BASE_URL, should_batch=False)
    server._stainless_client = StainlessClient(
        base_url=BASE_URL,
        username="",
        password="",
        http_client=httpx.Client(transport=httpx.MockTransport(handle)),
    )
    return server, requests


def test_op_create_posts_to_the_flat_v2_route():
    """Test that a v2 method reaches its route with entity and project filled in."""
    server, requests = _mock_server(
        httpx.Response(
            200, json={"object_id": "my-op", "digest": "abc123", "version_index": 0}
        )
    )

    res = server.op_create(
        tsi.OpCreateReq(
            project_id="entity/project", name="my-op", source_code="def f(): pass"
        )
    )

    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/v2/entity/project/ops"
    assert res.digest == "abc123"


def test_call_end_reads_an_empty_response_body():
    """Test that a route generated as returning a bare `object` is read back."""
    server, requests = _mock_server(httpx.Response(200, json={}))

    res = server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id="entity/project",
                id="call-id",
                ended_at="2026-08-20T00:00:00Z",
                summary={},
            )
        )
    )

    assert len(requests) == 1
    assert requests[0].url.path == "/call/end"
    assert res == tsi.CallEndRes()


def test_obj_add_tags_omits_wb_user_id():
    """Test that the server-populated wb_user_id stays out of the tags request."""
    server, requests = _mock_server(httpx.Response(200, json={}))

    server.obj_add_tags(
        tsi.ObjAddTagsReq(
            project_id="entity/project",
            object_id="my-obj",
            digest="abc123",
            tags=["production"],
            wb_user_id="user-id",
        )
    )

    assert len(requests) == 1
    assert requests[0].method == "PUT"
    assert requests[0].url.path == "/objs/my-obj/versions/abc123/tags"
    assert json.loads(requests[0].content) == {
        "project_id": "entity/project",
        "tags": ["production"],
    }


def test_file_content_read_keeps_bytes():
    """Test that a non-text file comes back as the bytes the server sent."""
    content = b"\x89PNG\r\n\x1a\n\xff\xfe"
    server, requests = _mock_server(
        httpx.Response(
            200, content=content, headers={"content-type": "application/octet-stream"}
        )
    )

    res = server.file_content_read(
        tsi.FileContentReadReq(project_id="entity/project", digest="abc123")
    )

    assert len(requests) == 1
    assert requests[0].url.path == "/file/content"
    assert res.content == content
