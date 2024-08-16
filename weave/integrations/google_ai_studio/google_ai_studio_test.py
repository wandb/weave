import asyncio
import os
from typing import Any, Optional

import pytest

import weave
from weave.trace_server import trace_server_interface as tsi
from weave.weave_client import WeaveClient


def _get_call_output(call: tsi.CallSchema) -> Any:
    """This is a hack and should not be needed. We should be able to auto-resolve this for the user.

    Keeping this here for now, but it should be removed in the future once we have a better solution.
    """
    call_output = call.output
    if isinstance(call_output, str) and call_output.startswith("weave://"):
        return weave.ref(call_output).get()
    return call_output


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
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_content_generation(client: WeaveClient) -> None:
    import google.generativeai as genai

    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", "DUMMY_API_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content("Write a story about an AI and magic")

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
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
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
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
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


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_content_generation_async_stream(client: WeaveClient) -> None:
    import google.generativeai as genai

    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", "DUMMY_API_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")

    async def get_response() -> None:
        async for chunk in await model.generate_content_async(
            "Write a story about an AI and magic", stream=True
        ):
            if chunk.text:
                print(chunk.text)
            print("_" * 80)

    asyncio.run(get_response())

    weave_server_response = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id())
    )
    assert len(weave_server_response.calls) == 1

    flattened_calls_list = [
        (op_name_from_ref(c.op_name), d)
        for (c, d) in flatten_calls(weave_server_response.calls)
    ]
    assert flattened_calls_list == [
        ("google.generativeai.GenerativeModel.generate_content_async", 0)
    ]
    for call in weave_server_response.calls:
        assert call.exception is None and call.ended_at is not None
