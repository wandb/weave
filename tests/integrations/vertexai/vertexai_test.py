import os

import pytest

from weave.integrations.integration_utilities import op_name_from_ref


@pytest.mark.retry(max_attempts=5)
@pytest.mark.skip_clickhouse_client
def test_content_generation(client):
    import vertexai
    from vertexai.generative_models import GenerativeModel

    vertexai.init(project="wandb-growth", location="us-central1")
    model = GenerativeModel("gemini-1.5-flash")
    model.generate_content("Explain how AI works in simple terms")

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at

    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "vertexai.GenerativeModel.generate_content"
    assert call.output is not None


@pytest.mark.retry(max_attempts=5)
@pytest.mark.skip_clickhouse_client
def test_content_generation_stream(client):
    import vertexai
    from vertexai.generative_models import GenerativeModel

    vertexai.init(project="wandb-growth", location="us-central1")
    model = GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(
        "Explain how AI works in simple terms", stream=True
    )
    chunks = [chunk.text for chunk in response]
    assert len(chunks) > 1

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at

    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "vertexai.GenerativeModel.generate_content"
    assert call.output is not None


@pytest.mark.retry(max_attempts=5)
@pytest.mark.asyncio
@pytest.mark.skip_clickhouse_client
async def test_content_generation_async(client):
    import vertexai
    from vertexai.generative_models import GenerativeModel

    vertexai.init(project="wandb-growth", location="us-central1")
    model = GenerativeModel("gemini-1.5-flash")
    _ = await model.generate_content_async("Explain how AI works in simple terms")

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at

    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "vertexai.GenerativeModel.generate_content_async"
    assert call.output is not None


@pytest.mark.retry(max_attempts=5)
@pytest.mark.asyncio
@pytest.mark.skip_clickhouse_client
async def test_content_generation_async_stream(client):
    import vertexai
    from vertexai.generative_models import GenerativeModel

    vertexai.init(project="wandb-growth", location="us-central1")
    model = GenerativeModel("gemini-1.5-flash")

    async def get_response():
        chunks = []
        async for chunk in await model.generate_content_async(
            "Explain how AI works in simple terms", stream=True
        ):
            if chunk.text:
                chunks.append(chunk.text)
        return chunks

    _ = await get_response()

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at

    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "vertexai.GenerativeModel.generate_content_async"
    assert call.output is not None
