import os
from importlib.metadata import version
from typing import Any, Generator

import litellm
import pytest
from packaging.version import parse as version_parse

import weave
from weave.integrations.litellm.litellm import litellm_patcher

# This PR:
# https://github.com/BerriAI/litellm/commit/fe2aa706e8ff4edbcd109897e5da6b83ef6ad693
# Changed the output format for OpenAI to use APIResponse.
# We can handle this in non-streaming mode, but in streaming mode, we
# have no way of correctly capturing the output and not messing up the
# users' code (that i can see). In these cases, model cost is not captured.
USES_RAW_OPENAI_RESPONSE = version_parse(version("litellm")) > version_parse("1.42.11")


class Nearly:
    def __init__(self, v: float) -> None:
        self.v = v

    def __eq__(self, other: Any) -> bool:
        return abs(self.v - other) < 2


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
    client: weave.trace.weave_client.WeaveClient, patch_litellm: None
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
    calls = list(client.calls())
    assert len(calls) == 2
    call = calls[0]
    assert call.exception is None and call.ended_at is not None
    output = call.output
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
    client: weave.trace.weave_client.WeaveClient, patch_litellm: None
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
    calls = list(client.calls())
    assert len(calls) == 2
    call = calls[0]
    assert call.exception is None and call.ended_at is not None
    output = call.output
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
    client: weave.trace.weave_client.WeaveClient, patch_litellm: None
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

    exp = """Hello! I'm just a computer program, so I don't have feelings, but I'm here to help you. How can I assist you today?"""

    assert all_content == exp
    calls = list(client.calls())
    assert len(calls) == 2
    call = calls[0]
    assert call.exception is None and call.ended_at is not None
    output = call.output
    assert output["choices"][0]["message"]["content"] == exp
    assert output["choices"][0]["finish_reason"] == "stop"
    assert output["id"] == chunk.id
    assert output["model"] == chunk.model
    assert output["created"] == Nearly(chunk.created)
    summary = call.summary
    assert summary is not None

    # We are stuck here:
    # 1. LiteLLM uses raw responses, which we can't wrap in our iterator
    # 2. They don't even capture token usage correctly, so this info is
    # not available for now.
    if not USES_RAW_OPENAI_RESPONSE:
        model_usage = summary["usage"][output["model"]]
        assert model_usage["requests"] == 1
        assert model_usage["completion_tokens"] == 31
        assert model_usage["prompt_tokens"] == 13
        assert model_usage["total_tokens"] == 44


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
@pytest.mark.asyncio
async def test_litellm_quickstart_stream_async(
    client: weave.trace.weave_client.WeaveClient, patch_litellm: None
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
    exp = """Hello! I'm just a computer program, so I don't have feelings, but I'm here and ready to assist you with any questions or tasks you may have. How can I help you today?"""

    assert all_content == exp
    calls = list(client.calls())
    assert len(calls) == 2
    call = calls[0]
    assert call.exception is None and call.ended_at is not None
    output = call.output
    assert output["choices"][0]["message"]["content"] == exp
    assert output["choices"][0]["finish_reason"] == "stop"
    assert output["id"] == chunk.id
    assert output["model"] == chunk.model
    assert output["created"] == Nearly(chunk.created)
    summary = call.summary
    assert summary is not None

    # We are stuck here:
    # 1. LiteLLM uses raw responses, which we can't wrap in our iterator
    # 2. They don't even capture token usage correctly, so this info is
    # not available for now.
    if not USES_RAW_OPENAI_RESPONSE:
        model_usage = summary["usage"][output["model"]]
        assert model_usage["requests"] == 1
        assert model_usage["completion_tokens"] == 41
        assert model_usage["prompt_tokens"] == 13
        assert model_usage["total_tokens"] == 54


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
def test_model_predict(
    client: weave.trace.weave_client.WeaveClient, patch_litellm: None
) -> None:
    class TranslatorModel(weave.Model):
        model: str
        temperature: float

        @weave.op()
        def predict(self, text: str, target_language: str) -> str:
            response = litellm.completion(
                api_key=os.environ.get("ANTHROPIC_API_KEY", "sk-ant-DUMMY_API_KEY"),
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a translator. Translate the given text to {target_language}.",
                    },
                    {"role": "user", "content": text},
                ],
                max_tokens=1024,
                temperature=self.temperature,
            )
            return response.choices[0].message.content

    # Create instances with different models
    claude_translator = TranslatorModel(
        model="claude-3-5-sonnet-20240620", temperature=0.1
    )

    res = claude_translator.predict("There is a bug in my code!", "Spanish")
    assert res is not None

    call = claude_translator.predict.calls()[0]
    d = call.summary["usage"]["claude-3-5-sonnet-20240620"]
    assert d["cache_creation_input_tokens"] == 0
    assert d["cache_read_input_tokens"] == 0
    assert d["requests"] == 1
    assert d["prompt_tokens"] == 28
    assert d["prompt_tokens_details"]["cached_tokens"] == 0
    assert d["completion_tokens"] == 10
    assert d["total_tokens"] == 38
