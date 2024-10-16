import os

import pytest

from weave.integrations.integration_utilities import op_name_from_ref


@pytest.mark.skip_clickhouse_client
def test_content_generation(client):
    import google.generativeai as genai

    genai.configure(api_key=os.environ.get("GOOGLE_GENAI_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")
    model.generate_content("Explain how AI works in simple terms")

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "google.generativeai.GenerativeModel.generate_content"
    )
    output = call.output
    assert output is not None


@pytest.mark.skip_clickhouse_client
def test_content_generation_stream(client):
    import google.generativeai as genai

    genai.configure(api_key=os.environ.get("GOOGLE_GENAI_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(
        "Explain how AI works in simple terms", stream=True
    )
    chunks = [chunk.text for chunk in response]
    assert len(chunks) > 1

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "google.generativeai.GenerativeModel.generate_content"
    )
    output = call.output
    assert output is not None


@pytest.mark.asyncio
@pytest.mark.skip_clickhouse_client
async def test_content_generation_async(client):
    import google.generativeai as genai

    genai.configure(api_key=os.environ.get("GOOGLE_GENAI_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")

    _ = await model.generate_content_async("Explain how AI works in simple terms")

    calls = list(client.calls())
    assert len(calls) == 1

    call = calls[0]
    assert call.started_at < call.ended_at
    assert (
        op_name_from_ref(call.op_name)
        == "google.generativeai.GenerativeModel.generate_content_async"
    )
    output = call.output
    assert output is not None
