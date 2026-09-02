from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from together import AsyncTogether, Together
from together.types import ChatCompletionResponse
from together.types.chat.chat_completion import Choice, ChoiceMessage
from together.types.chat.chat_completion_usage import ChatCompletionUsage

import weave
from weave.integrations.together.together_sdk import get_together_patcher

MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo"


@pytest.fixture(autouse=True)
def patch_together() -> Generator[None, None, None]:
    """Patch Together AI for all tests in this file."""
    patcher = get_together_patcher()
    patcher.attempt_patch()
    yield
    patcher.undo_patch()


def _response() -> ChatCompletionResponse:
    return ChatCompletionResponse(
        id="c-0",
        object="chat.completion",
        created=0,
        prompt=[],
        model=MODEL,
        choices=[
            Choice(
                index=0,
                finish_reason="stop",
                message=ChoiceMessage(
                    role="assistant",
                    content="The sky is blue because of Rayleigh scattering.",
                ),
            )
        ],
        usage=ChatCompletionUsage(
            prompt_tokens=26, completion_tokens=12, total_tokens=38
        ),
    )


def test_together_chat(
    client: weave.trace.weave_client.WeaveClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    together_client = Together(api_key="fake-key")
    monkeypatch.setattr(
        together_client.chat.completions, "_post", lambda *a, **k: _response()
    )
    response = together_client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "Why is the sky blue?"}],
    )
    assert "Rayleigh" in response.choices[0].message.content

    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]
    assert call.exception is None
    assert call.ended_at is not None
    integration = call.attributes["integration"]
    assert integration["name"] == "together"
    assert integration["version"]
    assert integration["meta"]["package_name"] == "together"
    assert call.output.choices[0].message.content == response.choices[0].message.content


@pytest.mark.asyncio
async def test_together_async_chat(
    client: weave.trace.weave_client.WeaveClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async_client = AsyncTogether(api_key="fake-key")

    async def _mock_post(*a: Any, **k: Any) -> ChatCompletionResponse:
        return _response()

    monkeypatch.setattr(async_client.chat.completions, "_post", _mock_post)
    await async_client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "Why is the sky blue?"}],
    )

    calls = list(client.get_calls())
    assert len(calls) == 1
    assert calls[0].attributes["integration"]["name"] == "together"
