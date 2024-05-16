import os
import pytest
from anthropic import Anthropic, AsyncAnthropic
import weave
from weave.trace_server import trace_server_interface as tsi

model = "claude-3-haiku-20240307"
# model = "claude-3-opus-20240229"

@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_anthropic(
    client: weave.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "DUMMY_API_KEY")
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
    anthropic_client = Anthropic(
        api_key=api_key,
    )
    message = anthropic_client.messages.create(
        model=model,
        stream=True,
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello, Claude"}],
    )

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1


@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_async_anthropic(
    client: weave.weave_client.WeaveClient,
) -> None:

    anthropic_client = AsyncAnthropic(
        # This is the default and can be omitted
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )


    message = await anthropic_client.messages.create(
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
@pytest.mark.asyncio
async def test_async_anthropic_stream(
    client: weave.weave_client.WeaveClient,
) -> None:

    anthropic_client = AsyncAnthropic(
        # This is the default and can be omitted
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )


    message = await anthropic_client.messages.create(
        model=model,
        stream=True,
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello, Claude"}],
    )

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
