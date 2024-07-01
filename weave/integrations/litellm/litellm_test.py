import os
from typing import Any, Generator

import litellm
import pytest

import weave
from weave.trace_server import trace_server_interface as tsi

from .litellm import litellm_patcher


class Nearly:
    def __init__(self, v: float) -> None:
        self.v = v

    def __eq__(self, other: Any) -> bool:
        return abs(self.v - other) < 2


def _get_call_output(call: tsi.CallSchema) -> Any:
    """This is a hack and should not be needed. We should be able to auto-resolve this for the user.

    Keeping this here for now, but it should be removed in the future once we have a better solution.
    """
    call_output = call.output
    if isinstance(call_output, str) and call_output.startswith("weave://"):
        return weave.ref(call_output).get()
    return call_output


@pytest.fixture(scope="package")
def patch_litellm(request: Any) -> Generator[None, None, None]:
    # This little hack is to allow us to run the tests in prod mode
    # For some reason pytest's import procedure causes the patching
    # to fail in prod mode. Specifically, the patches get run twice
    # despite the fact that the patcher is a singleton.
    weave_server_flag = request.config.getoption("--weave-server")
    if weave_server_flag == ("prod"):
        yield
        return

    litellm_patcher.attempt_patch()
    yield
    litellm_patcher.undo_patch()


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
def test_litellm_quickstart(
    client: weave.weave_client.WeaveClient, patch_litellm: None
) -> None:
    # This is taken directly from https://docs.litellm.ai/docs/
    chat_response = litellm.completion(
        api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
        model="gpt-3.5-turbo-0125",
        messages=[{"content": "Hello, how are you?", "role": "user"}],
    )

    all_content = chat_response.choices[0].message.content
    exp = """Hello! I'm just a computer program, so I don't have feelings, but I'm here to help you. How can I assist you today?"""

    assert all_content == exp
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 2
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    assert output["choices"][0]["message"]["content"] == exp
    assert output["choices"][0]["finish_reason"] == "stop"
    assert output["id"] == chat_response.id
    assert output["model"] == chat_response.model
    assert output["object"] == chat_response.object
    assert output["created"] == Nearly(chat_response.created)
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output["model"]]
    assert model_usage["requests"] == 1
    assert (
        output["usage"]["completion_tokens"] == model_usage["completion_tokens"] == 31
    )
    assert output["usage"]["prompt_tokens"] == model_usage["prompt_tokens"] == 13
    assert output["usage"]["total_tokens"] == model_usage["total_tokens"] == 44


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
@pytest.mark.asyncio
async def test_litellm_quickstart_async(
    client: weave.weave_client.WeaveClient, patch_litellm: None
) -> None:
    # This is taken directly from https://docs.litellm.ai/docs/
    chat_response = await litellm.acompletion(
        api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
        model="gpt-3.5-turbo-0125",
        messages=[{"content": "Hello, how are you?", "role": "user"}],
    )

    all_content = chat_response.choices[0].message.content
    exp = """Hello! I'm just a computer program, so I don't have feelings, but I'm here to help you with whatever you need. How can I assist you today?"""

    assert all_content == exp
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 2
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    assert output["choices"][0]["message"]["content"] == exp
    assert output["choices"][0]["finish_reason"] == "stop"
    assert output["id"] == chat_response.id
    assert output["model"] == chat_response.model
    assert output["object"] == chat_response.object
    assert output["created"] == Nearly(chat_response.created)
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output["model"]]
    assert model_usage["requests"] == 1
    assert (
        output["usage"]["completion_tokens"] == model_usage["completion_tokens"] == 35
    )
    assert output["usage"]["prompt_tokens"] == model_usage["prompt_tokens"] == 13
    assert output["usage"]["total_tokens"] == model_usage["total_tokens"] == 48


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
def test_litellm_quickstart_stream(
    client: weave.weave_client.WeaveClient, patch_litellm: None
) -> None:
    # This is taken directly from https://docs.litellm.ai/docs/
    chat_response = litellm.completion(
        api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
        model="gpt-3.5-turbo-0125",
        messages=[{"content": "Hello, how are you?", "role": "user"}],
        stream=True,
    )

    all_content = ""
    for chunk in chat_response:
        if chunk.choices[0].delta.content:
            all_content += chunk.choices[0].delta.content

    exp = """Hello! I'm just a virtual assistant so I don't have feelings, but I'm here and ready to help you with anything you need. How can I assist you today?"""

    assert all_content == exp
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 2
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    assert output["choices"][0]["message"]["content"] == exp
    assert output["choices"][0]["finish_reason"] == "stop"
    assert output["id"] == chunk.id
    assert output["model"] == chunk.model
    assert output["created"] == Nearly(chunk.created)
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output["model"]]
    assert model_usage["requests"] == 1
    # Stream tokens not supported yet with liteLLM - need to add manual counting similar to openai
    # assert (
    #     output["usage"]["completion_tokens"] == model_usage["completion_tokens"] == 0
    # )
    # assert output["usage"]["prompt_tokens"] == model_usage["prompt_tokens"] == 0
    # assert output["usage"]["total_tokens"] == model_usage["total_tokens"] == 0


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
@pytest.mark.asyncio
async def test_litellm_quickstart_stream_async(
    client: weave.weave_client.WeaveClient, patch_litellm: None
) -> None:
    # This is taken directly from https://docs.litellm.ai/docs/
    chat_response = await litellm.acompletion(
        api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
        model="gpt-3.5-turbo-0125",
        messages=[{"content": "Hello, how are you?", "role": "user"}],
        stream=True,
    )

    all_content = ""
    async for chunk in chat_response:
        if chunk.choices[0].delta.content:
            all_content += chunk.choices[0].delta.content
    exp = """Hello! I'm just a computer program, so I don't have feelings, but I'm here and ready to help you with anything you need. How can I assist you today?"""

    assert all_content == exp
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 2
    call = res.calls[0]
    assert call.exception is None and call.ended_at is not None
    output = _get_call_output(call)
    assert output["choices"][0]["message"]["content"] == exp
    assert output["choices"][0]["finish_reason"] == "stop"
    assert output["id"] == chunk.id
    assert output["model"] == chunk.model
    assert output["created"] == Nearly(chunk.created)
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output["model"]]
    assert model_usage["requests"] == 1
    # Stream tokens not supported yet with liteLLM - need to add manual counting similar to openai
    # assert (
    #     output["usage"]["completion_tokens"] == model_usage["completion_tokens"] == 0
    # )
    # assert output["usage"]["prompt_tokens"] == model_usage["prompt_tokens"] == 0
    # assert output["usage"]["total_tokens"] == model_usage["total_tokens"] == 0
