import asyncio
import os
from typing import Any, Optional

import pytest

from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


def flatten_calls(
    calls: list[tsi.CallSchema], parent_id: Optional[str] = None, depth: int = 0
) -> list:
    def children_of_parent_id(id: Optional[str]) -> list[tsi.CallSchema]:
        return [call for call in calls if call.parent_id == id]

    children = children_of_parent_id(parent_id)
    res = []
    for child in children:
        res.append((child, depth))
        res.extend(flatten_calls(calls, child.id, depth + 1))

    return res


def op_name_from_ref(ref: str) -> str:
    return ref.split("/")[-1].split(":")[0]


@pytest.mark.skip_clickhouse_client
def test_content_generation(client: WeaveClient) -> None:
    import google.generativeai as genai

    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")
    model.generate_content("Write a story about an AI and magic")

    weave_server_response = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id())
    )
    assert len(weave_server_response.calls) == 1

    flattened_calls_list = [
        (op_name_from_ref(c.op_name), d)
        for (c, d) in flatten_calls(weave_server_response.calls)
    ]
    assert flattened_calls_list == [
        ("google.generativeai.GenerativeModel.generate_content", 0),
    ]
    for call in weave_server_response.calls:
        assert call.exception is None and call.ended_at is not None


@pytest.mark.skip_clickhouse_client
def test_content_generation_stream(client: WeaveClient) -> None:
    import google.generativeai as genai

    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", "DUMMY_API_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(
        "Write a story about an AI and magic", stream=True
    )
    chunks = [chunk.text for chunk in response]
    assert len(chunks) > 1

    weave_server_response = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id())
    )
    assert len(weave_server_response.calls) == 1

    flattened_calls_list = [
        (op_name_from_ref(c.op_name), d)
        for (c, d) in flatten_calls(weave_server_response.calls)
    ]
    assert flattened_calls_list == [
        ("google.generativeai.GenerativeModel.generate_content", 0)
    ]
    for call in weave_server_response.calls:
        assert call.exception is None and call.ended_at is not None


@pytest.mark.skip_clickhouse_client
def test_content_generation_async(client: WeaveClient) -> None:
    import google.generativeai as genai

    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", "DUMMY_API_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")

    async def async_generate() -> Any:
        return await model.generate_content_async("Write a story about an AI and magic")

    asyncio.run(async_generate())

    weave_server_response = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id())
    )
    assert len(weave_server_response.calls) == 1

    flattened_calls_list = [
        (op_name_from_ref(c.op_name), d)
        for (c, d) in flatten_calls(weave_server_response.calls)
    ]
    assert flattened_calls_list == [
        ("google.generativeai.GenerativeModel.generate_content_async", 0),
    ]
    for call in weave_server_response.calls:
        assert call.exception is None and call.ended_at is not None
