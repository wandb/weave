import os, json
from typing import Any, Generator


import pytest
import cohere

import weave
from weave.autopatch import autopatch, reset_autopatch
from weave.integrations.cohere.cohere_sdk import cohere_patcher
from weave.trace_server import trace_server_interface as tsi

cohere_model = "command"  # You can change this to a specific model if needed

@pytest.fixture
def only_patch_cohere() -> Generator[None, None, None]:
    reset_autopatch() # unpatch all other integrations.
    cohere_patcher.attempt_patch()

    try:
        yield  # This is where the test using this fixture will run
    finally:
        autopatch()  # Ensures future tests have the patch applied

def _get_call_output(call: tsi.CallSchema) -> Any:
    call_output = call.output
    if isinstance(call_output, str) and call_output.startswith("weave://"):
        return weave.ref(call_output).get()
    return call_output


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
    assert output.text == exp
    assert output.generation_id == response.generation_id
    assert output.citations == response.citations
    assert output.documents == response.documents
    assert output.is_search_required == response.is_search_required
    assert output.search_queries == response.search_queries
    assert output.search_results == response.search_results

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
