import os

import pytest
from cerebras.cloud.sdk import AsyncCerebras, Cerebras

import weave

model = "llama3.1-8b"  # Cerebras model


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
def test_cerebras_sync(client: weave.trace.weave_client.WeaveClient) -> None:
    api_key = os.environ.get("CEREBRAS_API_KEY", "DUMMY_API_KEY")
    cerebras_client = Cerebras(api_key=api_key)

    response = cerebras_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "What is the capital of France?"}],
    )

    exp = "The capital of France is Paris."
    assert response.choices[0].message.content.strip() == exp

    calls = list(client.calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None and call.ended_at is not None
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


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
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

    calls = list(client.calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None and call.ended_at is not None
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
