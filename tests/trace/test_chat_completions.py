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


def _completion_payload(content: str = "Hello") -> dict:
    return {
        "id": "completion-1",
        "choices": [
            {
                "finish_reason": "stop",
                "index": 0,
                "message": {"role": "assistant", "content": content},
            }
        ],
        "created": 1,
        "model": "runtime-model",
        "object": "chat.completion",
    }


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
    monkeypatch.setattr(
        completions_module, "weave_trace_server_url", lambda: "https://trace.test"
    )
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
    assert stream.conversation_id is None
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


@pytest.mark.parametrize(
    ("endpoint", "model", "uses_local_op"),
    [
        ("playground", "custom::runtime::model", False),
        ("inference", "custom::runtime::model", False),
        ("playground", "openai/gpt-4o", True),
    ],
)
def test_completion_tracking_dispatch(
    monkeypatch,
    endpoint: completions_module.Endpoint,
    model: str,
    uses_local_op: bool,
) -> None:
    completions = Completions(_client())
    local_op = MagicMock(return_value="local-op")
    direct = MagicMock(return_value="direct")
    monkeypatch.setattr(completions, "_create_op", local_op)
    monkeypatch.setattr(completions, "_create_non_op", direct)

    result = completions.create(
        endpoint=endpoint,
        model=model,
        messages=[{"role": "user", "content": "Hello"}],
        track_llm_call=True,
    )

    if uses_local_op:
        assert result == "local-op"
        local_op.assert_called_once()
        direct.assert_not_called()
    else:
        assert result == "direct"
        direct.assert_called_once()
        local_op.assert_not_called()


def test_playground_completion_reuses_conversation_across_provider_switches(
    monkeypatch,
) -> None:
    request_bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        request_bodies.append(body)
        conversation_id = body.get("conversation_id", "server-conversation")
        return httpx.Response(
            200,
            json={
                "response": _completion_payload(),
                "conversation_id": conversation_id,
            },
        )

    _install_mock_transport(monkeypatch, handler)
    completions = Completions(_client())

    first = completions.create(
        endpoint="playground",
        model="custom::runtime-a::model-a",
        messages=[{"role": "user", "content": "Hello"}],
    )
    second = completions.create(
        endpoint="playground",
        model="openai/gpt-4o",
        messages=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hello"},
            {"role": "user", "content": "Continue"},
        ],
        conversation_id=first.conversation_id,
        track_llm_call=False,
    )
    third = completions.create(
        endpoint="playground",
        model="custom::runtime-b::model-b",
        messages=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hello"},
            {"role": "user", "content": "Continue"},
            {"role": "assistant", "content": "Hello"},
            {"role": "user", "content": "Finish"},
        ],
        conversation_id=second.conversation_id,
    )

    assert first.choices[0].message.content == "Hello"
    assert first.conversation_id
    assert second.conversation_id == first.conversation_id
    assert third.conversation_id == first.conversation_id
    assert [body["inputs"]["model"] for body in request_bodies] == [
        "custom::runtime-a::model-a",
        "openai/gpt-4o",
        "custom::runtime-b::model-b",
    ]
    assert "conversation_id" not in request_bodies[0]
    assert request_bodies[1]["conversation_id"] == first.conversation_id
    assert request_bodies[2]["conversation_id"] == first.conversation_id


def test_custom_runtime_stream_consumes_server_selected_conversation_context(
    monkeypatch,
) -> None:
    request_bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        request_bodies.append(body)
        content = (
            json.dumps({"_meta": {"conversation_id": "server-conversation"}}).encode()
            + b"\n"
            + json.dumps(_chunk_payload()).encode()
            + b"\n"
        )
        return httpx.Response(200, content=content)

    _install_mock_transport(monkeypatch, handler)
    completions = Completions(_client())

    stream = completions.create(
        endpoint="playground",
        model="custom::runtime::model",
        messages=[{"role": "user", "content": "Hello"}],
        stream=True,
    )
    chunks = list(stream)

    assert [chunk.choices[0].delta.content for chunk in chunks] == ["Hello"]
    assert stream.conversation_id == "server-conversation"
    assert "conversation_id" not in request_bodies[0]
    assert stream.response.is_closed


def test_inference_completion_serialization_has_no_playground_context(
    monkeypatch,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_completion_payload())

    _install_mock_transport(monkeypatch, handler)
    completions = Completions(_client())

    result = completions.create(
        endpoint="inference",
        model="coreweave/runtime-model",
        messages=[{"role": "user", "content": "Hello"}],
        track_llm_call=False,
    )

    assert "conversation_id" not in result.model_dump()
    assert "conversation_id" not in result.model_dump_json()
