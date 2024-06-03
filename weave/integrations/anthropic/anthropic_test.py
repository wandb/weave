import os
import pytest
from anthropic import Anthropic, AsyncAnthropic
import weave
from weave.trace_server import trace_server_interface as tsi
from .anthropic_sdk import anthropic_patcher

from typing import Any, Generator

model = "claude-3-haiku-20240307"
# model = "claude-3-opus-20240229"

def _get_call_output(call: tsi.CallSchema) -> Any:
    """This is a hack and should not be needed. We should be able to auto-resolve this for the user.

    Keeping this here for now, but it should be removed in the future once we have a better solution.
    """
    call_output = call.output
    if isinstance(call_output, str) and call_output.startswith("weave://"):
        return weave.ref(call_output).get()
    return call_output

@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"],
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

    all_content = message.content[0]
    exp = "Hello! It's nice to meet you. How can I assist you today?"
    assert all_content.text == exp
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    assert output.id == message.id
    assert output.model == message.model
    assert output.stop_reason== "end_turn"
    assert output.stop_sequence == None
    assert output.content[0].text == exp
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.output_tokens == model_usage["output_tokens"] == 19
    assert output.usage.input_tokens == model_usage["input_tokens"] == 10


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
