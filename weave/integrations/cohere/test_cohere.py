import os, json
from typing import Any

import pytest
import cohere

import weave
from weave.trace_server import trace_server_interface as tsi

cohere_model = "command"  # You can change this to a specific model if needed

def _get_call_output(call: tsi.CallSchema) -> Any:
    call_output = call.output
    if isinstance(call_output, str) and call_output.startswith("weave://"):
        return weave.ref(call_output).get()
    return call_output

    
def pprint(obj):
    print(json.dumps(obj.dict(), indent=4))

@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_cohere(
    client: weave.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("COHERE_API_KEY", "DUMMY_API_KEY")
    cohere_client = cohere.Client(api_key=api_key)
    
    response = cohere_client.chat(
        model=cohere_model,
        message="Hello, Cohere!",
        max_tokens=1024,
    )

    exp = response.text
    assert exp.strip() != ""
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    print("-----------------")
    pprint(response)
    print("-----------------")
    print(output)  #<- the output is a big string and doens't get parsed as it is a Pydantic.v1.BaseModel
    assert output.text == exp
    assert output.generation_id == response.generation_id
    assert output.response_id == response.response_id
    assert output.citations == response.citations
    assert output.chat_history == response.chat_history
    assert output.meta == response.meta
    assert output.finish_reason == response.finish_reason


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_cohere_stream(
    client: weave.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("COHERE_API_KEY", "DUMMY_API_KEY")
    cohere_client = cohere.Client(api_key=api_key)
    
    stream = cohere_client.chat(
        model=cohere_model,
        message="Hello, Cohere!",
        max_tokens=1024,
        stream=True,
    )

    all_content = ""
    for event in stream:
        all_content += event.text

    assert all_content.strip() != ""
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    assert output.text == all_content
    assert output.generation_id is not None
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][model]
    assert model_usage["requests"] == 1
    assert output.token_count["prompt_tokens"] == model_usage["prompt_tokens"]
    assert output.token_count["response_tokens"] == model_usage["response_tokens"]
