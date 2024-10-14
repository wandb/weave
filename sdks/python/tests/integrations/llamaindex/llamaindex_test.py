from typing import Generator

import pytest

import weave
from weave.integrations.integration_utilities import (
    filter_body,
    flatten_calls,
    flattened_calls_to_names,
)
from weave.trace.weave_client import Call
from weave.trace_server.trace_server_interface import CallsFilter


def assert_calls_correct_for_quickstart(flattened_calls: list[Call]) -> None:
    """Next, the major thing to assert is the "shape" of the calls:
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
    assert len(flattened_calls) == 9

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
    assert flattened_calls_to_names(flattened_calls) == exp


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
    client: weave.trace.weave_client.WeaveClient, fake_api_key: None
) -> None:
    # This is taken directly from  https://docs.llamaindex.ai/en/stable/getting_started/starter_example/
    from llama_index.core import SimpleDirectoryReader, VectorStoreIndex

    documents = SimpleDirectoryReader("integrations/llamaindex/test_data").load_data()
    index = VectorStoreIndex.from_documents(documents)

    query_engine = index.as_query_engine()
    response = query_engine.query("What did the author do growing up?")

    calls = list(client.calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)
    assert_calls_correct_for_quickstart(flattened_calls)
    call, _ = flattened_calls[-2]
    assert call.inputs["serialized"]["api_key"] == "REDACTED"


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
@pytest.mark.asyncio
async def test_llamaindex_quickstart_async(
    client: weave.trace.weave_client.WeaveClient, fake_api_key: None
) -> None:
    # This is taken directly from  https://docs.llamaindex.ai/en/stable/getting_started/starter_example/
    from llama_index.core import SimpleDirectoryReader, VectorStoreIndex

    documents = SimpleDirectoryReader("integrations/llamaindex/test_data").load_data()
    index = VectorStoreIndex.from_documents(documents)

    query_engine = index.as_query_engine()
    response = await query_engine.aquery("What did the author do growing up?")

    calls = list(client.calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)
    assert_calls_correct_for_quickstart(flattened_calls)
    call, _ = flattened_calls[-2]
    assert call.inputs["serialized"]["api_key"] == "REDACTED"
