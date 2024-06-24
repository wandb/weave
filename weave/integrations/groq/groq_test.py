import os
from typing import Any, Generator, Optional

import pytest
from groq import Groq

import weave
from weave.trace_server import trace_server_interface as tsi

from .groq import groq_patcher


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


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_groq(
    client: weave.weave_client.WeaveClient,
) -> None:
    groq_client = Groq(
        api_key=os.environ.get("GROQ_API_KEY", "DUMMY_API_KEY"),
    )
    chat_completion = groq_client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": "What is the capital of India?",
            }
        ],
        model="llama3-8b-8192",
        seed=42,
    )

    assert (
        chat_completion.choices[0].message.content
        == "The capital of India is New Delhi."
    )
    weave_server_respose = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id())
    )
    flattened_call_response = [
        (op_name_from_ref(c.op_name), d)
        for (c, d) in flatten_calls(weave_server_respose.calls)
    ]
    assert flattened_call_response == []
