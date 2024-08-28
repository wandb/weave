import os
from typing import Any

import pytest
from cerebras.cloud.sdk import AsyncCerebras, Cerebras

import weave
from weave.trace_server import trace_server_interface as tsi

model = "llama3.1-8b"  # Cerebras model


def _get_call_output(call: tsi.CallSchema) -> Any:
    call_output = call.output
    if isinstance(call_output, str) and call_output.startswith("weave://"):
        return weave.ref(call_output).get()
    return call_output


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

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
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

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
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
