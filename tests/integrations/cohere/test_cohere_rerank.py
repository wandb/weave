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
def test_cohere_rerank(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("COHERE_API_KEY", "DUMMY_API_KEY")

    cohere_client = cohere.Client(api_key=api_key)

    query = "What is the capital of France?"
    documents = [
        "Paris is the capital of France.",
        "London is the capital of England.",
        "Berlin is the capital of Germany.",
    ]

    response = cohere_client.rerank(
        query=query,
        documents=documents,
        model="rerank-english-v2.0",
        top_n=2,
    )

    assert len(response.results) == 2
    assert response.results[0].relevance_score > 0
    assert response.results[1].relevance_score > 0
    assert response.results[0].relevance_score >= response.results[1].relevance_score

    calls = list(client.calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "cohere.Client.rerank"
    output = call.output

    assert len(output.results) == len(response.results)
    assert output.results == response.results
    assert output.meta == response.meta


@pytest.mark.asyncio
@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
async def test_cohere_rerank_async(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("COHERE_API_KEY", "DUMMY_API_KEY")

    cohere_client = cohere.AsyncClient(api_key=api_key)

    query = "What is the capital of France?"
    documents = [
        "Paris is the capital of France.",
        "London is the capital of England.",
        "Berlin is the capital of Germany.",
    ]

    response = await cohere_client.rerank(
        query=query,
        documents=documents,
        model="rerank-english-v2.0",
        top_n=2,
    )

    assert len(response.results) == 2
    assert response.results[0].relevance_score > 0
    assert response.results[1].relevance_score > 0
    assert response.results[0].relevance_score >= response.results[1].relevance_score

    calls = list(client.calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None and call.ended_at is not None
    assert call.started_at < call.ended_at
    assert op_name_from_ref(call.op_name) == "cohere.AsyncClient.rerank"
    output = call.output

    assert len(output.results) == len(response.results)
    assert output.results == response.results
    assert output.meta == response.meta