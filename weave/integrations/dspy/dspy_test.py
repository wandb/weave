import os
import pytest
from typing import Generator, List, Optional, Tuple

from weave.weave_client import WeaveClient
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


@pytest.fixture
def fake_api_key() -> Generator[None, None, None]:
    import os

    orig_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "sk-DUMMY_KEY"
    try:
        yield
    finally:
        if orig_key is None:
            del os.environ["OPENAI_API_KEY"]
        else:
            os.environ["OPENAI_API_KEY"] = orig_key


def assert_calls(
    client: WeaveClient,
    expected_calls: List[Tuple[str, int]],
) -> None:
    weave_server_respose = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id())
    )
    flattened_call_response = [
        (op_name_from_ref(c.op_name), d)
        for (c, d) in flatten_calls(weave_server_respose.calls)
    ]
    assert flattened_call_response == expected_calls


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
def test_dspy_language_models(client: WeaveClient, fake_api_key: None) -> None:
    import dspy

    gpt3_turbo = dspy.OpenAI(model="gpt-3.5-turbo-1106", max_tokens=300)
    dspy.configure(lm=gpt3_turbo)
    gpt3_turbo("hello! this is a raw prompt to GPT-3.5")
    assert_calls(
        client,
        expected_calls=[
            ("GPT3.__call__", 0),
            ("GPT3.request", 1),
            ("GPT3.basic_request", 2),
            ("openai.chat.completions.create", 3)
        ],
    )
