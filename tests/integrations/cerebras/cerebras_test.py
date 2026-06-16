import os
from collections.abc import Generator

import pytest
from cerebras.cloud.sdk import AsyncCerebras, Cerebras

import weave
from weave.integrations.cerebras.cerebras_sdk import get_cerebras_patcher

model = "llama3.1-8b"  # Cerebras model


@pytest.fixture(autouse=True)
def patch_cerebras() -> Generator[None, None, None]:
    """Patch Cerebras for all tests in this file."""
    patcher = get_cerebras_patcher()
    patcher.attempt_patch()
    yield
    patcher.undo_patch()


@pytest.mark.vcr(filter_headers=["authorization"])
def test_cerebras_sync(client: weave.trace.weave_client.WeaveClient) -> None:
    api_key = os.environ.get("CEREBRAS_API_KEY", "DUMMY_API_KEY")
    cerebras_client = Cerebras(api_key=api_key)

    response = cerebras_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "What is the capital of France?"}],
    )

    exp = "The capital of France is Paris."
    assert response.choices[0].message.content.strip() == exp

    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None
    assert call.ended_at is not None
    # Integration-tracking metadata is stamped on every patched call.
    integration = call.attributes["integration"]
    assert integration["name"] == "cerebras"
    assert integration["version"]  # weave SDK version
    assert integration["meta"]["package_name"] == "cerebras-cloud-sdk"
    output = call.output
    assert output.choices[0].message.content.strip() == exp
    assert output.choices[0].finish_reason == "stop"
    assert output.id == response.id
    assert output.model == response.model
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.completion_tokens == model_usage["completion_tokens"]
    assert output.usage.prompt_tokens == model_usage["prompt_tokens"]
    assert output.usage.total_tokens == model_usage["total_tokens"]


@pytest.mark.vcr(filter_headers=["authorization"])
@pytest.mark.asyncio
async def test_cerebras_async(client: weave.trace.weave_client.WeaveClient) -> None:
    api_key = os.environ.get("CEREBRAS_API_KEY", "DUMMY_API_KEY")
    cerebras_client = AsyncCerebras(api_key=api_key)

    response = await cerebras_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "What is the capital of France?"}],
    )

    exp = "The capital of France is Paris."
    assert response.choices[0].message.content.strip() == exp

    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None
    assert call.ended_at is not None
    output = call.output
    assert output.choices[0].message.content.strip() == exp
    assert output.choices[0].finish_reason == "stop"
    assert output.id == response.id
    assert output.model == response.model
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.completion_tokens == model_usage["completion_tokens"]
    assert output.usage.prompt_tokens == model_usage["prompt_tokens"]
    assert output.usage.total_tokens == model_usage["total_tokens"]
