import typing
from typing import Any, Generator, List, Optional

import pytest

import weave
from weave.trace_server import trace_server_interface as tsi

from .llamaindex import llamaindex_patcher


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


def assert_calls_correct_for_quickstart(calls: list[tsi.CallSchema]) -> None:
    assert len(calls) == 9
    """ Next, the major thing to assert is the "shape" of the calls:
    llama_index.query
        llama_index.retrieve
            llama_index.embedding
        llama_index.synthesize
            llama_index.chunking
            llama_index.chunking
            llama_index.templating
            llama_index.llm
                openai.chat.completions.create
    """
    flattened = flatten_calls(calls)
    got = [(op_name_from_ref(c.op_name), d) for (c, d) in flattened]
    exp = [
        ("llama_index.query", 0),
        ("llama_index.retrieve", 1),
        ("llama_index.embedding", 2),
        ("llama_index.synthesize", 1),
        ("llama_index.chunking", 2),
        ("llama_index.chunking", 2),
        ("llama_index.templating", 2),
        ("llama_index.llm", 2),
        ("openai.chat.completions.create", 3),
    ]
    assert got == exp


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


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_llamaindex_quickstart(
    client: weave.weave_client.WeaveClient, fake_api_key: None
) -> None:
    # This is taken directly from  https://docs.llamaindex.ai/en/stable/getting_started/starter_example/
    from llama_index.core import SimpleDirectoryReader, VectorStoreIndex

    documents = SimpleDirectoryReader("integrations/llamaindex/test_data").load_data()
    index = VectorStoreIndex.from_documents(documents)

    query_engine = index.as_query_engine()
    response = query_engine.query("What did the author do growing up?")

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert_calls_correct_for_quickstart(res.calls)


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
@pytest.mark.asyncio
async def test_llamaindex_quickstart_async(
    client: weave.weave_client.WeaveClient, fake_api_key: None
) -> None:
    # This is taken directly from  https://docs.llamaindex.ai/en/stable/getting_started/starter_example/
    from llama_index.core import SimpleDirectoryReader, VectorStoreIndex

    documents = SimpleDirectoryReader("integrations/llamaindex/test_data").load_data()
    index = VectorStoreIndex.from_documents(documents)

    query_engine = index.as_query_engine()
    response = await query_engine.aquery("What did the author do growing up?")
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert_calls_correct_for_quickstart(res.calls)
