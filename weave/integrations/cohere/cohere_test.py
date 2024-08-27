import os
from typing import Any

import cohere
import pytest

import weave
from weave.trace_server import trace_server_interface as tsi

cohere_model = "command"  # You can change this to a specific model if needed


def _get_call_output(call: tsi.CallSchema) -> Any:
    call_output = call.output
    if isinstance(call_output, str) and call_output.startswith("weave://"):
        return weave.ref(call_output).get()
    return call_output


def op_name_from_ref(ref: str) -> str:
    return ref.split("/")[-1].split(":")[0]


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_cohere(
    client: weave.trace.weave_client.WeaveClient,
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
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "cohere.Client.chat"
    output = _get_call_output(call)
    assert output.text == exp
    assert output.generation_id == response.generation_id
    assert output.citations == response.citations
    assert output.documents == response.documents
    assert output.is_search_required == response.is_search_required
    assert output.search_queries == response.search_queries
    assert output.search_results == response.search_results
    assert (
        output.meta.billed_units.input_tokens == response.meta.billed_units.input_tokens
    )
    assert (
        output.meta.billed_units.output_tokens
        == response.meta.billed_units.output_tokens
    )
    assert (
        output.meta.billed_units.search_units == response.meta.billed_units.search_units
    )
    assert (
        output.meta.billed_units.classifications
        == response.meta.billed_units.classifications
    )
    assert output.meta.tokens.input_tokens == response.meta.tokens.input_tokens
    assert output.meta.tokens.output_tokens == response.meta.tokens.output_tokens


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_cohere_stream(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("COHERE_API_KEY", "DUMMY_API_KEY")
    cohere_client = cohere.Client(api_key=api_key)

    stream = cohere_client.chat_stream(
        model=cohere_model,
        message="Hello, Cohere!",
        max_tokens=1024,
    )

    # they accumulate for us in the last message
    for event in stream:
        pass

    response = event.response  # the NonStreamedChatResponse
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "cohere.Client.chat_stream"
    output = _get_call_output(call)
    assert output.text == response.text
    assert output.generation_id == response.generation_id
    summary = call.summary
    assert summary is not None
    assert output.generation_id == response.generation_id
    assert output.citations == response.citations
    assert output.documents == response.documents
    assert output.is_search_required == response.is_search_required
    assert output.search_queries == response.search_queries
    assert output.search_results == response.search_results
    assert (
        output.meta.billed_units.input_tokens == response.meta.billed_units.input_tokens
    )
    assert (
        output.meta.billed_units.output_tokens
        == response.meta.billed_units.output_tokens
    )
    assert (
        output.meta.billed_units.search_units == response.meta.billed_units.search_units
    )
    assert (
        output.meta.billed_units.classifications
        == response.meta.billed_units.classifications
    )
    assert output.meta.tokens.input_tokens == response.meta.tokens.input_tokens
    assert output.meta.tokens.output_tokens == response.meta.tokens.output_tokens


@pytest.mark.asyncio
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
async def test_cohere_async(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("COHERE_API_KEY", "DUMMY_API_KEY")

    cohere_client = cohere.AsyncClient(api_key=api_key)

    response = await cohere_client.chat(
        model=cohere_model,
        message="Hello, Async Cohere!",
        max_tokens=1024,
    )

    exp = response.text
    assert exp.strip() != ""
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "cohere.AsyncClient.chat"
    output = _get_call_output(call)
    assert output.text == exp
    assert output.generation_id == response.generation_id
    assert output.citations == response.citations
    assert output.documents == response.documents
    assert output.is_search_required == response.is_search_required
    assert output.search_queries == response.search_queries
    assert output.search_results == response.search_results
    assert (
        output.meta.billed_units.input_tokens == response.meta.billed_units.input_tokens
    )
    assert (
        output.meta.billed_units.output_tokens
        == response.meta.billed_units.output_tokens
    )
    assert (
        output.meta.billed_units.search_units == response.meta.billed_units.search_units
    )
    assert (
        output.meta.billed_units.classifications
        == response.meta.billed_units.classifications
    )
    assert output.meta.tokens.input_tokens == response.meta.tokens.input_tokens
    assert output.meta.tokens.output_tokens == response.meta.tokens.output_tokens


@pytest.mark.asyncio
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
async def test_cohere_async_stream(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("COHERE_API_KEY", "DUMMY_API_KEY")
    cohere_client = cohere.AsyncClient(api_key=api_key)

    stream = cohere_client.chat_stream(
        model=cohere_model,
        message="Hello, Async Cohere Stream!",
        max_tokens=1024,
    )

    async for event in stream:
        pass

    response = event.response  # the NonStreamedChatResponse
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "cohere.AsyncClient.chat_stream"
    output = _get_call_output(call)
    assert output.text == response.text
    assert output.generation_id == response.generation_id
    summary = call.summary
    assert summary is not None
    assert output.generation_id == response.generation_id
    assert output.citations == response.citations
    assert output.documents == response.documents
    assert output.is_search_required == response.is_search_required
    assert output.search_queries == response.search_queries
    assert output.search_results == response.search_results
    assert (
        output.meta.billed_units.input_tokens == response.meta.billed_units.input_tokens
    )
    assert (
        output.meta.billed_units.output_tokens
        == response.meta.billed_units.output_tokens
    )
    assert (
        output.meta.billed_units.search_units == response.meta.billed_units.search_units
    )
    assert (
        output.meta.billed_units.classifications
        == response.meta.billed_units.classifications
    )
    assert output.meta.tokens.input_tokens == response.meta.tokens.input_tokens
    assert output.meta.tokens.output_tokens == response.meta.tokens.output_tokens
