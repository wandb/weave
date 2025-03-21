import os

import pytest

from weave.integrations.integration_utilities import op_name_from_ref


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_hf_api_model(client):
    from smolagents import HfApiModel

    engine = HfApiModel(
        model_id="Qwen/Qwen2.5-Coder-32B-Instruct",
        token=os.environ.get("HUGGINGFACE_API_KEY", "DUMMY_API_KEY"),
    )
    messages = [{"role": "user", "content": "What is the capital of France?"}]
    response = engine(messages, stop_sequences=["END"])
    assert "paris" in response.content.lower()

    calls = list(client.calls())
    assert len(calls) == 2

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "smolagents.HfApiModel"
    assert "paris" in call.output.content.lower()

    call = calls[1]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "huggingface_hub.InferenceClient.chat_completion"
    )
    assert "paris" in call.output.choices[0].message.content.lower()


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_openai_server_model(client):
    from smolagents import OpenAIServerModel

    engine = OpenAIServerModel(
        model_id="gpt-4o-mini",
        api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
    )
    messages = [{"role": "user", "content": "What is the capital of France?"}]
    response = engine(messages, stop_sequences=["END"])
    assert "paris" in response.content.lower()

    calls = list(client.calls())
    assert len(calls) == 2

    call = calls[0]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "smolagents.OpenAIServerModel"
    assert "paris" in call.output.content.lower()

    call = calls[1]
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert "paris" in call.output["choices"][0]["message"]["content"].lower()
