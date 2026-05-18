"""WB-31070: failed file_create futures must not stay cached.

Without eviction, `_send_file_create` returns the cached failed future
on every subsequent retry, turning a transient 502 into a permanent
silent failure until LRU eviction.
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import FileCreateReq, FileCreateRes
from weave.trace_server_bindings.remote_http_trace_server import (
    RemoteHTTPTraceServer,
)


def _make_502() -> httpx.HTTPStatusError:
    response = httpx.Response(
        status_code=502,
        request=httpx.Request("POST", "http://example.com/file/create"),
        content=b"Bad Gateway",
    )
    return httpx.HTTPStatusError("502", request=response.request, response=response)


@pytest.fixture
def offline_client(monkeypatch):
    monkeypatch.setenv("WEAVE_RETRY_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("WEAVE_RETRY_MAX_INTERVAL", "0.01")
    monkeypatch.setenv("WEAVE_ENABLE_WAL", "false")
    server = RemoteHTTPTraceServer("http://example.com")
    client = WeaveClient(
        entity="ent",
        project="proj",
        server=server,
        ensure_project_exists=False,
    )
    return client, server


@pytest.mark.disable_logging_error_check
def test_failed_file_create_evicts_cache_and_retries_on_next_call(offline_client):
    """A 502 on file_create must evict the entry so the next call retries.

    Pre-fix: the failed future stayed cached and was returned for every
    subsequent same-content request, silently re-failing.
    """
    client, server = offline_client
    req = FileCreateReq(project_id="ent/proj", name="f", content=b"hello")

    with patch.object(server, "file_create", side_effect=_make_502()):
        fut1 = client._send_file_create(req)
        client.future_executor.flush()
        if client.future_executor_fastlane is not None:
            client.future_executor_fastlane.flush()

    assert fut1.exception() is not None
    assert client.send_file_cache.get(req) is None

    success_res = FileCreateRes(digest="abc")
    with patch.object(server, "file_create", return_value=success_res):
        fut2 = client._send_file_create(req)
        client.future_executor.flush()
        if client.future_executor_fastlane is not None:
            client.future_executor_fastlane.flush()

    assert fut2 is not fut1
    assert fut2.result() == success_res
    assert client.send_file_cache.get(req) is fut2


def test_successful_file_create_stays_cached(offline_client):
    """A successful file_create must stay cached so duplicates are deduped."""
    client, server = offline_client
    req = FileCreateReq(project_id="ent/proj", name="f", content=b"hello")
    success_res = FileCreateRes(digest="abc")

    with patch.object(server, "file_create", return_value=success_res):
        fut1 = client._send_file_create(req)
        client.future_executor.flush()
        if client.future_executor_fastlane is not None:
            client.future_executor_fastlane.flush()

    assert client.send_file_cache.get(req) is fut1
    fut2 = client._send_file_create(req)
    assert fut2 is fut1
