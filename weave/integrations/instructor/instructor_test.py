import os
from typing import Any, Optional

import pytest
from pydantic import BaseModel

import weave
from weave.trace_server import trace_server_interface as tsi


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


class FruitExtractor(BaseModel):
    fruit_name: str
    fruit_color: str
    fruit_flavor: str


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_instructor_openai(
    client: weave.weave_client.WeaveClient,
) -> None:
    import instructor
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")
    lm_client = instructor.from_openai(OpenAI(api_key=api_key))
    fruit_description = lm_client.chat.completions.create(
        model="gpt-3.5-turbo",
        response_model=FruitExtractor,
        seed=42,
        messages=[
            {
                "role": "system",
                "content": "Your task is to extract the fruit, color and flavor from a given sentence.",
            },
            {
                "role": "user",
                "content": """
    There are many fruits that were found on the recently discovered planet Goocrux.
    There are neoskizzles that grow there, which are purple and taste like candy.
    """,
            },
        ],
    )
    assert fruit_description.fruit_name == "neoskizzles"
    assert fruit_description.fruit_color == "purple"
    assert fruit_description.fruit_flavor == "candy"

    weave_server_response = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id())
    )
    assert len(weave_server_response.calls) == 2

    flattened_calls_list = [
        (op_name_from_ref(c.op_name), d)
        for (c, d) in flatten_calls(weave_server_response.calls)
    ]
    assert flattened_calls_list == [
        ("Instructor.create", 0),
        ("openai.chat.completions.create", 1),
    ]

    call = weave_server_response.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    assert output.fruit_name == "neoskizzles"
    assert output.fruit_color == "purple"
    assert output.fruit_flavor == "candy"

    call = weave_server_response.calls[1]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    assert (
        output.choices[0].message.tool_calls[0].function._val.arguments
        == '{"fruit_name":"neoskizzles","fruit_color":"purple","fruit_flavor":"candy"}'
    )
