"""Tests for RESTful tags and aliases routes in StainlessRemoteHTTPTraceServer.

These tests verify that the tag/alias methods send the correct HTTP method,
URL path, and request body. Requests are observed at the httpx transport
boundary, so the SDK routing and conversion layers are exercised for real.
"""

from __future__ import annotations

import json

import httpx
import pytest
from weave_server_sdk import models as sdk_models

from tests.trace_server_bindings.conftest import SpyTransport
from weave.trace_server_bindings import models as bindings_models
from weave.trace_server_bindings.stainless_remote_http_trace_server import (
    StainlessRemoteHTTPTraceServer,
)

BASE_URL = "http://example.com"


@pytest.fixture
def transport():
    return SpyTransport()


@pytest.fixture
def server(transport):
    """Create a StainlessRemoteHTTPTraceServer over a spy transport."""
    srv = StainlessRemoteHTTPTraceServer(
        BASE_URL, should_batch=False, transport=transport
    )
    yield srv
    if srv.call_processor:
        srv.call_processor.stop_accepting_new_work_and_flush_queue()
    if srv.feedback_processor:
        srv.feedback_processor.stop_accepting_new_work_and_flush_queue()


class TestObjAddTags:
    def test_sends_correct_request(self, server, transport):
        server.obj_add_tags(
            bindings_models.ObjAddTagsReq(
                project_id="entity/project",
                object_id="my-obj",
                digest="abc123",
                tags=["production", "reviewed"],
            )
        )

        request = transport.requests[0]
        assert request.method == "PUT"
        assert str(request.url) == f"{BASE_URL}/objs/my-obj/versions/abc123/tags"

        body = json.loads(request.content)
        assert body["project_id"] == "entity/project"
        assert body["tags"] == ["production", "reviewed"]
        # object_id and digest should NOT be in the body (they're in the URL)
        assert "object_id" not in body
        assert "digest" not in body


class TestObjRemoveTags:
    def test_sends_correct_request(self, server, transport):
        server.obj_remove_tags(
            bindings_models.ObjRemoveTagsReq(
                project_id="entity/project",
                object_id="my-obj",
                digest="abc123",
                tags=["staging"],
            )
        )

        request = transport.requests[0]
        assert request.method == "POST"
        assert str(request.url) == f"{BASE_URL}/objs/my-obj/versions/abc123/tags/remove"

        body = json.loads(request.content)
        assert body["project_id"] == "entity/project"
        assert body["tags"] == ["staging"]
        assert "object_id" not in body
        assert "digest" not in body


class TestObjSetAliases:
    def test_sends_correct_request(self, server, transport):
        server.obj_set_aliases(
            bindings_models.ObjSetAliasesReq(
                project_id="entity/project",
                object_id="my-obj",
                digest="abc123",
                aliases=["staging", "candidate"],
            )
        )

        request = transport.requests[0]
        assert request.method == "PUT"
        assert str(request.url) == f"{BASE_URL}/objs/my-obj/aliases"

        body = json.loads(request.content)
        assert body["project_id"] == "entity/project"
        assert body["digest"] == "abc123"
        assert body["aliases"] == ["staging", "candidate"]
        assert "object_id" not in body


class TestObjRemoveAliases:
    def test_sends_correct_request(self, server, transport):
        server.obj_remove_aliases(
            bindings_models.ObjRemoveAliasesReq(
                project_id="entity/project",
                object_id="my-obj",
                aliases=["staging"],
            )
        )

        request = transport.requests[0]
        assert request.method == "POST"
        assert str(request.url) == f"{BASE_URL}/objs/my-obj/aliases/remove"

        body = json.loads(request.content)
        assert body["project_id"] == "entity/project"
        assert body["aliases"] == ["staging"]
        assert "object_id" not in body


class TestTagsList:
    def test_sends_get_with_project_id_param(self, server, transport):
        transport.queue.append(httpx.Response(200, json={"tags": ["prod", "staging"]}))
        result = server.tags_list(
            bindings_models.TagsListReq(project_id="entity/project")
        )

        request = transport.requests[0]
        assert request.method == "GET"
        assert request.url.path == "/tags"
        assert request.url.params["project_id"] == "entity/project"
        assert isinstance(result, sdk_models.TagsListRes)
        assert result.tags == ["prod", "staging"]


class TestAliasesList:
    def test_sends_get_with_project_id_param(self, server, transport):
        transport.queue.append(
            httpx.Response(200, json={"aliases": ["deploy", "staging"]})
        )
        result = server.aliases_list(
            bindings_models.AliasesListReq(project_id="entity/project")
        )

        request = transport.requests[0]
        assert request.method == "GET"
        assert request.url.path == "/aliases"
        assert request.url.params["project_id"] == "entity/project"
        assert isinstance(result, sdk_models.AliasesListRes)
        assert result.aliases == ["deploy", "staging"]
