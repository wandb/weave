"""Regression coverage for the public chat completions client."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx
import pytest
from pydantic import ValidationError

from weave.chat import completions as completions_module
from weave.chat.completions import Completions
from weave.trace.weave_client import WeaveClient


def _client() -> WeaveClient:
    client = MagicMock(spec=WeaveClient)
    client.entity = "entity"
    client.project = "project"
    return client


def _chunk_payload(content: str = "Hello") -> dict:
    return {
        "id": "completion-1",
        "choices": [
            {
                "delta": {"role": "assistant", "content": content},
                "finish_reason": None,
                "index": 0,
            }
        ],
        "created": 1,
        "model": "runtime-model",
        "object": "chat.completion.chunk",
    }


class _TrackingByteStream(httpx.SyncByteStream):
    def __init__(self, content: bytes, close_error: Exception | None = None) -> None:
        self.content = content
        self.close_error = close_error
        self.closed = False

    def __iter__(self):
        yield self.content

    def close(self) -> None:
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


def _install_mock_transport(monkeypatch, handler) -> list[httpx.Client]:
    real_client = httpx.Client
    transport = httpx.MockTransport(handler)

    clients = []

    def client_factory(**kwargs):
        client = real_client(transport=transport, **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(
        completions_module.httpx,
        "Client",
        client_factory,
    )
    monkeypatch.setattr(completions_module, "get_wandb_api_context", lambda: "key")
    return clients


def _create_stream(
    completions: Completions,
    endpoint: completions_module.Endpoint = "inference",
    model: str = "coreweave/runtime-model",
):
    return completions.create(
        endpoint=endpoint,
        model=model,
        messages=[{"role": "user", "content": "Hello"}],
        stream=True,
        track_llm_call=False,
    )


@pytest.mark.parametrize(
    ("endpoint", "model"),
    [
        ("inference", "coreweave/runtime-model"),
        ("playground", "runtime-model"),
    ],
)
def test_stream_remains_open_until_consumed(monkeypatch, endpoint, model) -> None:
    chunk = json.dumps(_chunk_payload()).encode()
    content = (
        b"data: " + chunk + b"\n\ndata: [DONE]\n\n"
        if endpoint == "inference"
        else chunk + b"\n"
    )
    body = _TrackingByteStream(content)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=body)

    clients = _install_mock_transport(monkeypatch, handler)
    completions = Completions(_client())

    stream = _create_stream(completions, endpoint, model)

    assert not stream.response.is_closed
    assert not clients[0].is_closed
    assert [chunk.choices[0].delta.content for chunk in stream] == ["Hello"]
    assert stream.response.is_closed
    assert body.closed
    assert clients[0].is_closed


def test_stream_context_manager_closes_unconsumed_resources(monkeypatch) -> None:
    body = _TrackingByteStream(b"")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=body)

    clients = _install_mock_transport(monkeypatch, handler)
    completions = Completions(_client())
    stream = _create_stream(completions)

    with stream:
        assert not stream.response.is_closed

    assert stream.response.is_closed
    assert body.closed
    assert clients[0].is_closed


def test_stream_close_always_closes_client(monkeypatch) -> None:
    body = _TrackingByteStream(b"", RuntimeError("response close failed"))

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=body)

    clients = _install_mock_transport(monkeypatch, handler)
    completions = Completions(_client())
    stream = _create_stream(completions)

    with pytest.raises(RuntimeError, match="response close failed"):
        stream.close()

    assert stream.response.is_closed
    assert body.closed
    assert clients[0].is_closed


def test_stream_setup_error_closes_resources(monkeypatch) -> None:
    body = _TrackingByteStream(b'{"error":"failed"}')
    responses = []

    def handler(_request: httpx.Request) -> httpx.Response:
        response = httpx.Response(500, stream=body)
        responses.append(response)
        return response

    clients = _install_mock_transport(monkeypatch, handler)
    completions = Completions(_client())

    with pytest.raises(httpx.HTTPStatusError):
        _create_stream(completions)

    assert responses[0].is_closed
    assert body.closed
    assert clients[0].is_closed


def test_stream_setup_error_always_closes_client(monkeypatch) -> None:
    body = _TrackingByteStream(
        b'{"error":"failed"}', RuntimeError("response close failed")
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, stream=body)

    clients = _install_mock_transport(monkeypatch, handler)
    completions = Completions(_client())

    with pytest.raises(RuntimeError, match="response close failed"):
        _create_stream(completions)

    assert body.closed
    assert clients[0].is_closed


def test_stream_parse_error_closes_resources(monkeypatch) -> None:
    body = _TrackingByteStream(b"not-json\n")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=body)

    clients = _install_mock_transport(monkeypatch, handler)
    completions = Completions(_client())
    stream = _create_stream(completions)

    with pytest.raises(ValidationError):
        list(stream)

    assert stream.response.is_closed
    assert body.closed
    assert clients[0].is_closed
