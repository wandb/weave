import os

import cohere
import pytest

import weave
from weave.integrations.integration_utilities import _get_call_output, op_name_from_ref

cohere_model = "command"  # You can change this to a specific model if needed


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
    calls = list(client.calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "cohere.Client.chat"
    output = call.output
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
    calls = list(client.calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "cohere.Client.chat_stream"
    output = call.output
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
    calls = list(client.calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "cohere.AsyncClient.chat"
    output = call.output
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
    calls = list(client.calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "cohere.AsyncClient.chat_stream"
    output = call.output
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


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_cohere_v2(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("COHERE_API_KEY", "DUMMY_API_KEY")

    cohere_client = cohere.ClientV2(api_key=api_key)

    response = cohere_client.chat(
        model=cohere_model,
        messages=[{"role": "user", "content": "count to three"}],
        max_tokens=1024,
    )
    calls = list(client.calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "cohere.ClientV2.chat"
    output = _get_call_output(call)

    assert output.message.content[0].text == response.message.content[0].text
    assert output.id == response.id
    assert output.finish_reason == response.finish_reason
    assert output.message.role == response.message.role
    assert output.message.tool_calls == response.message.tool_calls
    assert output.message.tool_plan == response.message.tool_plan
    assert output.message.citations == response.message.citations

    assert (
        output.usage.billed_units.input_tokens
        == response.meta["billed_units"]["input_tokens"]
    )
    assert (
        output.usage.billed_units.output_tokens
        == response.meta["billed_units"]["output_tokens"]
    )
    assert output.usage.tokens.input_tokens == response.meta["tokens"]["input_tokens"]
    assert output.usage.tokens.output_tokens == response.meta["tokens"]["output_tokens"]


@pytest.mark.asyncio
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
async def test_cohere_async_v2(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("COHERE_API_KEY", "DUMMY_API_KEY")

    cohere_client = cohere.AsyncClientV2(api_key=api_key)

    response = await cohere_client.chat(
        model=cohere_model,
        messages=[{"role": "user", "content": "count to three"}],
        max_tokens=1024,
    )
    calls = list(client.calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "cohere.AsyncClientV2.chat"
    output = _get_call_output(call)

    assert output.message.content[0].text == response.message.content[0].text
    assert output.id == response.id
    assert output.finish_reason == response.finish_reason
    assert output.message.role == response.message.role
    assert output.message.tool_calls == response.message.tool_calls
    assert output.message.tool_plan == response.message.tool_plan
    assert output.message.citations == response.message.citations

    assert (
        output.usage.billed_units.input_tokens
        == response.meta["billed_units"]["input_tokens"]
    )
    assert (
        output.usage.billed_units.output_tokens
        == response.meta["billed_units"]["output_tokens"]
    )
    assert output.usage.tokens.input_tokens == response.meta["tokens"]["input_tokens"]
    assert output.usage.tokens.output_tokens == response.meta["tokens"]["output_tokens"]


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_cohere_stream_v2(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("COHERE_API_KEY", "DUMMY_API_KEY")

    cohere_client = cohere.ClientV2(api_key=api_key)

    response = cohere_client.chat_stream(
        model=cohere_model,
        messages=[{"role": "user", "content": "count to three"}],
        max_tokens=10,
    )

    all_content = ""
    for event in response:
        if event is not None:
            if event.type == "message-start":
                id = event.id
                role = event.delta.message.role
            if event.type == "content-delta":
                all_content += event.delta.message.content.text
            if event.type == "message-end":
                finish_reason = event.delta.finish_reason

    calls = list(client.calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "cohere.ClientV2.chat_stream"
    output = _get_call_output(call)

    assert output.message.content[0] == all_content
    assert output.id == id
    assert output.finish_reason == finish_reason
    assert output.message.role == role

    assert output.usage.billed_units.input_tokens == 3.0
    assert output.usage.billed_units.output_tokens == 9.0
    assert output.usage.tokens.input_tokens == 65.0
    assert output.usage.tokens.output_tokens == 10.0


@pytest.mark.asyncio
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
async def test_cohere_async_stream_v2(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("COHERE_API_KEY", "DUMMY_API_KEY")

    cohere_client = cohere.AsyncClientV2(api_key=api_key)

    response = cohere_client.chat_stream(
        model=cohere_model,
        messages=[{"role": "user", "content": "count to three"}],
        max_tokens=15,
    )

    all_content = ""
    async for event in response:
        if event is not None:
            if event.type == "message-start":
                id = event.id
                role = event.delta.message.role
            if event.type == "content-delta":
                all_content += event.delta.message.content.text
            if event.type == "message-end":
                finish_reason = event.delta.finish_reason

    calls = list(client.calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "cohere.AsyncClientV2.chat_stream"
    output = _get_call_output(call)

    assert output.message.content[0] == all_content
    assert output.id == id
    assert output.finish_reason == finish_reason
    assert output.message.role == role

    assert output.usage.billed_units.input_tokens == 3.0
    assert output.usage.billed_units.output_tokens == 15.0
    assert output.usage.tokens.input_tokens == 65.0
    assert output.usage.tokens.output_tokens == 15.0
