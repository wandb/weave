import asyncio
import os

import pytest

from weave.integrations.integration_utilities import op_name_from_ref


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_content_generation_sync(client):
    from google import genai

    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    response = google_client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents="What's the capital of France?",
    )

    assert "paris" in response.text.lower()

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.models.Models.generate_content"
    assert call.output is not None
    assert call.output.candidates[0].content.parts[0].text == response.text
    assert call.output.usage_metadata.candidates_token_count > 0
    assert call.output.usage_metadata.prompt_token_count > 0
    assert (
        call.output.usage_metadata.total_token_count
        == call.output.usage_metadata.candidates_token_count
        + call.output.usage_metadata.prompt_token_count
    )


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_content_generation_async(client):
    from google import genai

    google_client = genai.Client(api_key=os.getenv("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    response = asyncio.run(
        google_client.aio.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents="What's the capital of France?",
        )
    )

    assert "paris" in response.text.lower()

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "google.genai.models.AsyncModels.generate_content"
    assert call.output is not None
    assert call.output.candidates[0].content.parts[0].text == response.text
    assert call.output.usage_metadata.candidates_token_count > 0
    assert call.output.usage_metadata.prompt_token_count > 0
    assert (
        call.output.usage_metadata.total_token_count
        == call.output.usage_metadata.candidates_token_count
        + call.output.usage_metadata.prompt_token_count
    )
