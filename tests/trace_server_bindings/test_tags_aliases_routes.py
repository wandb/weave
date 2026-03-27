"""Tests for RESTful tags and aliases routes in RemoteHTTPTraceServer.

These tests verify that the tag/alias methods send the correct HTTP method,
URL path, and request body through the RemoteHTTPTraceServer client.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from weave.trace_server import trace_server_interface as tsi
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


class TestObjAddTags:
    def test_sends_correct_request(self, server):
        mock_resp = _mock_response()
        with patch.object(server, "put", return_value=mock_resp) as mock_put:
            server.obj_add_tags(
                tsi.ObjAddTagsReq(
                    project_id="entity/project",
                    object_id="my-obj",
                    digest="abc123",
                    tags=["production", "reviewed"],
                )
            )

            mock_put.assert_called_once()
            call_url = mock_put.call_args[0][0]
            assert call_url == "/objs/my-obj/versions/abc123/tags"

            sent_data = mock_put.call_args[1]["data"]
            body = json.loads(sent_data)
            assert body["project_id"] == "entity/project"
            assert body["tags"] == ["production", "reviewed"]
            # object_id and digest should NOT be in the body (they're in the URL)
            assert "object_id" not in body
            assert "digest" not in body


class TestObjRemoveTags:
    def test_sends_correct_request(self, server):
        mock_resp = _mock_response()
        with patch.object(server, "post", return_value=mock_resp) as mock_post:
            server.obj_remove_tags(
                tsi.ObjRemoveTagsReq(
                    project_id="entity/project",
                    object_id="my-obj",
                    digest="abc123",
                    tags=["staging"],
                )
            )

            mock_post.assert_called_once()
            call_url = mock_post.call_args[0][0]
            assert call_url == "/objs/my-obj/versions/abc123/tags/remove"

            sent_data = mock_post.call_args[1]["data"]
            body = json.loads(sent_data)
            assert body["project_id"] == "entity/project"
            assert body["tags"] == ["staging"]
            assert "object_id" not in body
            assert "digest" not in body


class TestObjSetAliases:
    def test_sends_correct_request(self, server):
        mock_resp = _mock_response()
        with patch.object(server, "put", return_value=mock_resp) as mock_put:
            server.obj_set_aliases(
                tsi.ObjSetAliasesReq(
                    project_id="entity/project",
                    object_id="my-obj",
                    digest="abc123",
                    aliases=["staging", "candidate"],
                )
            )

            mock_put.assert_called_once()
            call_url = mock_put.call_args[0][0]
            assert call_url == "/objs/my-obj/aliases"

            sent_data = mock_put.call_args[1]["data"]
            body = json.loads(sent_data)
            assert body["project_id"] == "entity/project"
            assert body["digest"] == "abc123"
            assert body["aliases"] == ["staging", "candidate"]
            assert "object_id" not in body


class TestObjRemoveAliases:
    def test_sends_correct_request(self, server):
        mock_resp = _mock_response()
        with patch.object(server, "post", return_value=mock_resp) as mock_post:
            server.obj_remove_aliases(
                tsi.ObjRemoveAliasesReq(
                    project_id="entity/project",
                    object_id="my-obj",
                    aliases=["staging"],
                )
            )

            mock_post.assert_called_once()
            call_url = mock_post.call_args[0][0]
            assert call_url == "/objs/my-obj/aliases/remove"

            sent_data = mock_post.call_args[1]["data"]
            body = json.loads(sent_data)
            assert body["project_id"] == "entity/project"
            assert body["aliases"] == ["staging"]
            assert "object_id" not in body


class TestTagsList:
    def test_sends_get_to_correct_url(self, server):
        mock_resp = _mock_response({"tags": ["prod", "staging"]})
        with patch.object(server, "get", return_value=mock_resp) as mock_get:
            result = server.tags_list(tsi.TagsListReq(project_id="entity/project"))

            mock_get.assert_called_once()
            call_url = mock_get.call_args[0][0]
            assert call_url == "/tags"

    def test_passes_project_id_as_query_param(self, server):
        mock_resp = _mock_response({"tags": ["prod"]})
        with patch.object(server, "get", return_value=mock_resp) as mock_get:
            server.tags_list(tsi.TagsListReq(project_id="entity/project"))

            call_kwargs = mock_get.call_args[1]
            assert call_kwargs["params"] == {"project_id": "entity/project"}

    def test_returns_parsed_response(self, server):
        mock_resp = _mock_response({"tags": ["prod", "staging"]})
        with patch.object(server, "get", return_value=mock_resp):
            result = server.tags_list(tsi.TagsListReq(project_id="entity/project"))

            assert isinstance(result, tsi.TagsListRes)
            assert result.tags == ["prod", "staging"]


class TestAliasesList:
    def test_sends_get_to_correct_url(self, server):
        mock_resp = _mock_response({"aliases": ["deploy", "staging"]})
        with patch.object(server, "get", return_value=mock_resp) as mock_get:
            server.aliases_list(tsi.AliasesListReq(project_id="entity/project"))

            mock_get.assert_called_once()
            call_url = mock_get.call_args[0][0]
            assert call_url == "/aliases"

    def test_passes_project_id_as_query_param(self, server):
        mock_resp = _mock_response({"aliases": ["deploy"]})
        with patch.object(server, "get", return_value=mock_resp) as mock_get:
            server.aliases_list(tsi.AliasesListReq(project_id="entity/project"))

            call_kwargs = mock_get.call_args[1]
            assert call_kwargs["params"] == {"project_id": "entity/project"}

    def test_returns_parsed_response(self, server):
        mock_resp = _mock_response({"aliases": ["deploy", "staging"]})
        with patch.object(server, "get", return_value=mock_resp):
            result = server.aliases_list(
                tsi.AliasesListReq(project_id="entity/project")
            )

            assert isinstance(result, tsi.AliasesListRes)
            assert result.aliases == ["deploy", "staging"]
