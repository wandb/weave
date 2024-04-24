import os
import pytest
import weave
from weave.trace_server import trace_server_interface as tsi
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage
from .mistral import mistral_patcher

from typing import Generator


@pytest.fixture()
def patch_mistral() -> Generator[None, None, None]:
    mistral_patcher.attempt_patch()
    yield
    mistral_patcher.undo_patch()


@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
def test_mistral_quickstart(
    client: weave.weave_client.WeaveClient, patch_mistral: None
) -> None:
    # This is taken directly from https://docs.mistral.ai/getting-started/quickstart/
    api_key = os.environ.get("MISTRAL_API_KEY", "DUMMY_API_KEY")
    model = "mistral-large-latest"

    mistral_client = MistralClient(api_key=api_key)

    chat_response = mistral_client.chat(
        model=model,
        messages=[ChatMessage(role="user", content="What is the best French cheese?")],
    )

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    # Probably should do some other more robust testing here
