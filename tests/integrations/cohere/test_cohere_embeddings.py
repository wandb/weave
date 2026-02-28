import os

import cohere
import pytest

import weave
from weave.integrations.integration_utilities import op_name_from_ref


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_cohere_embed(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("COHERE_API_KEY", "DUMMY_API_KEY")

    cohere_client = cohere.Client(api_key=api_key)

    response = cohere_client.embed(
        texts=["Hello, World!", "This is a test."],
        model="embed-english-v3.0",
        input_type="search_document",
    )

    assert len(response.embeddings) == 2
    assert len(response.embeddings[0]) > 0
    assert len(response.embeddings[1]) > 0

    calls = list(client.calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "cohere.Client.embed"
    output = call.output

    assert len(output.embeddings) == len(response.embeddings)
    assert output.embeddings == response.embeddings
    assert output.meta == response.meta


@pytest.mark.asyncio
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
async def test_cohere_embed_async(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("COHERE_API_KEY", "DUMMY_API_KEY")

    cohere_client = cohere.AsyncClient(api_key=api_key)

    response = await cohere_client.embed(
        texts=["Hello, World!", "This is a test."],
        model="embed-english-v3.0",
        input_type="search_document",
    )

    assert len(response.embeddings) == 2
    assert len(response.embeddings[0]) > 0
    assert len(response.embeddings[1]) > 0

    calls = list(client.calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "cohere.AsyncClient.embed"
    output = call.output

    assert len(output.embeddings) == len(response.embeddings)
    assert output.embeddings == response.embeddings
    assert output.meta == response.meta