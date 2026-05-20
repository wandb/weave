from __future__ import annotations

import os
import threading
from unittest.mock import patch

import httpx
import pytest

from weave.utils import http_requests


@pytest.fixture(autouse=True)
def clear_http_env(monkeypatch):
    for var_name in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
        "WEAVE_DEBUG_HTTP",
    ):
        monkeypatch.delenv(var_name, raising=False)


def test_client_uses_default_httpx_transport():
    assert isinstance(http_requests.get_client()._transport, httpx.HTTPTransport)


def test_get_client_is_cached_per_thread():
    assert http_requests.get_client() is http_requests.get_client()


def test_get_client_is_distinct_across_threads():
    clients: list[httpx.Client] = []

    def collect() -> None:
        clients.append(http_requests.get_client())

    threads = [threading.Thread(target=collect) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(clients) == 3
    assert len({id(c) for c in clients}) == 3
    assert http_requests.get_client() not in clients


def test_get_client_rebuilds_after_fork(monkeypatch):
    main = http_requests.get_client()

    real_pid = os.getpid()
    fake_pid = real_pid + 1
    monkeypatch.setattr(http_requests.os, "getpid", lambda: fake_pid)

    after_fork = http_requests.get_client()
    assert after_fork is not main


def test_request_hook_logs_when_enabled(monkeypatch):
    monkeypatch.setenv("WEAVE_DEBUG_HTTP", "1")
    request = httpx.Request("GET", "https://api.wandb.ai/calls")

    with patch.object(http_requests, "pprint_request") as mock_pprint_request:
        http_requests._log_request(request)

    mock_pprint_request.assert_called_once_with(request)
    assert isinstance(request.extensions.get("weave_start_time"), float)


def test_request_hook_noop_when_disabled():
    request = httpx.Request("GET", "https://api.wandb.ai/calls")

    with patch.object(http_requests, "pprint_request") as mock_pprint_request:
        http_requests._log_request(request)

    mock_pprint_request.assert_not_called()
    assert "weave_start_time" not in request.extensions


def test_response_hook_logs_when_enabled(monkeypatch):
    monkeypatch.setenv("WEAVE_DEBUG_HTTP", "1")
    request = httpx.Request("GET", "https://api.wandb.ai/calls")
    request.extensions["weave_start_time"] = 1.0
    response = httpx.Response(200, request=request, text="ok")

    with (
        patch.object(http_requests, "pprint_response") as mock_pprint_response,
        patch("weave.utils.http_requests.time", return_value=2.0),
    ):
        http_requests._log_response(response)

    mock_pprint_response.assert_called_once_with(response)


def test_pprint_response_handles_unread_stream():
    request = httpx.Request("GET", "https://api.wandb.ai/calls")
    response = httpx.Response(200, request=request, stream=httpx.ByteStream(b"test"))

    http_requests.pprint_response(response)
