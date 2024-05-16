import os
import pytest
from anthropic import Anthropic
import weave
from weave.trace_server import trace_server_interface as tsi


@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_anthropic(
    client: weave.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "DUMMY_API_KEY")
    model = "claude-3-opus-20240229"
    anthropic_client = Anthropic(
        api_key=api_key,
    )
    message = anthropic_client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello, Claude"}],
    )

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))

    assert len(res.calls) == 1


@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_anthropic_stream(
    client: weave.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "DUMMY_API_KEY")
    model = "claude-3-opus-20240229"
    anthropic_client = Anthropic(
        api_key=api_key,
    )
    message = anthropic_client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello, Claude"}],
    )

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))

    assert len(res.calls) == 1
