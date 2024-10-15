import asyncio
import os
from typing import Any

import pytest

from weave.integrations.integration_utilities import op_name_from_ref
from weave.trace.weave_client import WeaveClient


@pytest.mark.skip_clickhouse_client
def test_content_generation(client: WeaveClient) -> None:
    import google.generativeai as genai

    genai.configure(api_key=os.environ.get("GOOGLE_GENAI_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")
    model.generate_content("Write a story about an AI and magic")

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
def test_content_generation_stream(client: WeaveClient) -> None:
    import google.generativeai as genai

    genai.configure(api_key=os.environ.get("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(
        "Write a story about an AI and magic", stream=True
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
async def test_content_generation_async(client: WeaveClient) -> None:
    import google.generativeai as genai

    genai.configure(api_key=os.environ.get("GOOGLE_GENAI_KEY", "DUMMY_API_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")

    async def async_generate() -> Any:
        return await model.generate_content_async("Write a story about an AI and magic")

    asyncio.run(async_generate())

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
