from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest
from ollama import ChatResponse, Message
from ollama._client import AsyncClient, Client

import weave
from weave.integrations.ollama.ollama_sdk import get_ollama_patcher


@pytest.fixture(autouse=True)
def patch_ollama() -> Generator[None, None, None]:
    """Patch Ollama for all tests in this file."""
    patcher = get_ollama_patcher()
    patcher.attempt_patch()
    yield
    patcher.undo_patch()


def _text_response() -> ChatResponse:
    return ChatResponse(
        model="llama3.2",
        message=Message(
            role="assistant", content="The sky is blue because of Rayleigh scattering."
        ),
        done=True,
        done_reason="stop",
        prompt_eval_count=26,
        eval_count=12,
    )


def test_ollama_chat_module_helper(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    import ollama

    with patch.object(Client, "_request", lambda self, *a, **k: _text_response()):
        response = ollama.chat(
            model="llama3.2",
            messages=[{"role": "user", "content": "Why is the sky blue?"}],
        )

    assert "Rayleigh" in response.message.content

    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]
    assert call.exception is None
    assert call.ended_at is not None
    integration = call.attributes["integration"]
    assert integration["name"] == "ollama"
    assert integration["version"]
    assert integration["meta"]["package_name"] == "ollama"
    assert call.output.message.content == response.message.content


def test_ollama_chat_via_client(client: weave.trace.weave_client.WeaveClient) -> None:
    with patch.object(Client, "_request", lambda self, *a, **k: _text_response()):
        ollama_client = Client()
        ollama_client.chat(
            model="llama3.2",
            messages=[{"role": "user", "content": "Why is the sky blue?"}],
        )

    calls = list(client.get_calls())
    assert len(calls) == 1
    assert calls[0].attributes["integration"]["name"] == "ollama"


@pytest.mark.asyncio
async def test_ollama_async_chat(client: weave.trace.weave_client.WeaveClient) -> None:
    async def _mock_request(self: Any, *a: Any, **k: Any) -> ChatResponse:
        return _text_response()

    with patch.object(AsyncClient, "_request", _mock_request):
        await AsyncClient().chat(
            model="llama3.2",
            messages=[{"role": "user", "content": "Why is the sky blue?"}],
        )

    calls = list(client.get_calls())
    assert len(calls) == 1
    assert calls[0].attributes["integration"]["name"] == "ollama"
