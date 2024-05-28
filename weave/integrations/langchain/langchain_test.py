import os
from typing import Any, Optional

import pytest
from weave.trace_server import trace_server_interface as tsi
from weave.weave_client import WeaveClient


def filter_body(r: Any) -> Any:
    r.body = ""
    return r


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


def assert_correct_calls_for_chain_invoke(calls: list[tsi.CallSchema]) -> None:
    assert len(calls) == 4

    flattened = flatten_calls(calls)
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
    exp = [
        ("langchain.Chain.RunnableSequence", 0),
        ("langchain.Prompt.PromptTemplate", 1),
        ("langchain.Llm.ChatOpenAI", 1),
        ("openai.chat.completions.create", 2),
    ]
    assert got == exp


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_simple_chain_invoke(client: WeaveClient) -> None:
    from langchain_core.prompts import PromptTemplate
    from langchain_openai import ChatOpenAI

    from .langchain import WeaveTracer

    tracer = WeaveTracer()
    config = {
        "callbacks": [tracer],
    }
    api_key = os.environ.get("OPENAI_API_KEY", "sk-DUMMY_KEY")
    llm = ChatOpenAI(openai_api_key=api_key, temperature=0.0)
    prompt = PromptTemplate.from_template("1 + {number} = ")

    llm_chain = prompt | llm
    output = llm_chain.invoke({"number": 2}, config=config)

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert_correct_calls_for_chain_invoke(res.calls)
