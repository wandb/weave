import pytest
import weave
from weave.trace_server import trace_server_interface as tsi
from typing import Any, Generator
from .llamaindex import llamaindex_patcher


@pytest.fixture(scope="package")
def patch_llamaindex(request: Any) -> Generator[None, None, None]:
    # This little hack is to allow us to run the tests in prod mode
    # For some reason pytest's import procedure causes the patching
    # to fail in prod mode. Specifically, the patches get run twice
    # despite the fact that the patcher is a singleton.
    weave_server_flag = request.config.getoption("--weave-server")
    if weave_server_flag == ("prod"):
        yield
        return

    llamaindex_patcher.attempt_patch()
    yield
    llamaindex_patcher.undo_patch()

def filter_body(r):
    r.body = ''
    return r

@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"], before_record_request=filter_body
)
def test_llamaindex_quickstart(
    client: weave.weave_client.WeaveClient, patch_llamaindex: None
) -> None:
    # This is taken directly from  https://docs.llamaindex.ai/en/stable/getting_started/starter_example/
    from llama_index.core import VectorStoreIndex, SimpleDirectoryReader

    documents = SimpleDirectoryReader("integrations/llamaindex/test_data").load_data()
    index = VectorStoreIndex.from_documents(documents)

    query_engine = index.as_query_engine()
    response = query_engine.query("What did the author do growing up?")
    print(response)
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 11
    #TODO: Finish Assertions
