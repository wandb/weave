import os
from collections.abc import Generator
from importlib.metadata import version
from typing import Any

import litellm
import pytest
from packaging.version import parse as version_parse

import weave
from weave.integrations.litellm.litellm import get_litellm_patcher
from weave.integrations.openai.openai_sdk import get_openai_patcher

# This PR:
# https://github.com/BerriAI/litellm/commit/fe2aa706e8ff4edbcd109897e5da6b83ef6ad693
# Changed the output format for OpenAI to use APIResponse.
# We can handle this in non-streaming mode, but in streaming mode, we
# have no way of correctly capturing the output and not messing up the
# users' code (that i can see). In these cases, model cost is not captured.
USES_RAW_OPENAI_RESPONSE = version_parse(version("litellm")) > version_parse("1.42.11")


class Nearly:  # noqa: PLW1641
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
    weave_server_flag = request.config.getoption("--trace-server")
    if weave_server_flag == ("prod"):
        yield
        return

    # Patch both LiteLLM and OpenAI since LiteLLM uses OpenAI as backend
    litellm_patcher = get_litellm_patcher()
    openai_patcher = get_openai_patcher()

    litellm_patcher.attempt_patch()
    openai_patcher.attempt_patch()

    yield

    litellm_patcher.undo_patch()
    openai_patcher.undo_patch()


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
    calls = list(client.get_calls())
    assert len(calls) == 2
    call = calls[0]
    assert call.exception is None
    assert call.ended_at is not None
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
    calls = list(client.get_calls())
    assert len(calls) == 2
    call = calls[0]
    assert call.exception is None
    assert call.ended_at is not None
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
    calls = list(client.get_calls())
    assert len(calls) == 2
    call = calls[0]
    assert call.exception is None
    assert call.ended_at is not None
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
    calls = list(client.get_calls())
    assert len(calls) == 2
    call = calls[0]
    assert call.exception is None
    assert call.ended_at is not None
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
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
def test_litellm_responses(
    client: weave.trace.weave_client.WeaveClient, patch_litellm: None
) -> None:
    """
    Requirement: litellm.responses() should be traced with captured output
    Interface: weave client call recording
    Given: A patched litellm environment with weave client
    When: User calls litellm.responses(model="gpt-4o-mini", input="Say hi")
    Then: client.get_calls() contains a call with captured output and usage
    """
    response = litellm.responses(
        api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
        model="gpt-4o-mini",
        input="Say hi in one word.",
    )

    # Get output text from the response
    output_text = ""
    for item in response.output:
        if hasattr(item, "content"):
            for content in item.content:
                if hasattr(content, "text"):
                    output_text += content.text

    assert output_text  # Should have some content

    calls = list(client.get_calls())
    # Should have litellm.responses call (and possibly nested OpenAI call)
    assert len(calls) >= 1

    # Find the litellm.responses call
    responses_call = None
    for call in calls:
        if call.op_name and "litellm.responses" in call.op_name:
            responses_call = call
            break

    assert responses_call is not None, "litellm.responses call not found"
    assert responses_call.exception is None
    assert responses_call.ended_at is not None

    output = responses_call.output
    assert output is not None
    assert "id" in output
    assert "model" in output
    assert "output" in output
    assert "usage" in output

    # Check usage is captured in summary
    summary = responses_call.summary
    assert summary is not None
    assert "usage" in summary


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
@pytest.mark.asyncio
async def test_litellm_aresponses(
    client: weave.trace.weave_client.WeaveClient, patch_litellm: None
) -> None:
    """
    Requirement: litellm.aresponses() should be traced with captured output
    Interface: weave client call recording
    Given: A patched litellm environment with weave client
    When: User calls await litellm.aresponses(model="gpt-4o-mini", input="Say hi")
    Then: client.get_calls() contains a call with captured output and usage
    """
    response = await litellm.aresponses(
        api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
        model="gpt-4o-mini",
        input="Say hi in one word.",
    )

    # Get output text from the response
    output_text = ""
    for item in response.output:
        if hasattr(item, "content"):
            for content in item.content:
                if hasattr(content, "text"):
                    output_text += content.text

    assert output_text  # Should have some content

    calls = list(client.get_calls())
    assert len(calls) >= 1

    # Find the litellm.aresponses call
    responses_call = None
    for call in calls:
        if call.op_name and "litellm.aresponses" in call.op_name:
            responses_call = call
            break

    assert responses_call is not None, "litellm.aresponses call not found"
    assert responses_call.exception is None
    assert responses_call.ended_at is not None

    output = responses_call.output
    assert output is not None
    assert "id" in output
    assert "model" in output
    assert "output" in output
    assert "usage" in output

    summary = responses_call.summary
    assert summary is not None
    assert "usage" in summary


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
def test_litellm_responses_stream(
    client: weave.trace.weave_client.WeaveClient, patch_litellm: None
) -> None:
    """
    Requirement: Streaming litellm.responses() should accumulate and be traced
    Interface: weave client call recording, iterator behavior
    Given: A patched litellm environment with weave client
    When: User calls litellm.responses(stream=True) and iterates
    Then: User receives streaming chunks, call.output contains accumulated response
    """
    response = litellm.responses(
        api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
        model="gpt-4o-mini",
        input="Say hi in one word.",
        stream=True,
    )

    # Consume the stream
    all_text = ""
    for event in response:
        event_type = getattr(event, "type", None)
        if event_type == "response.output_text.delta":
            all_text += event.delta

    assert all_text  # Should have accumulated some text

    calls = list(client.get_calls())
    assert len(calls) >= 1

    # Find the litellm.responses call
    responses_call = None
    for call in calls:
        if call.op_name and "litellm.responses" in call.op_name:
            responses_call = call
            break

    assert responses_call is not None, "litellm.responses call not found"
    assert responses_call.exception is None
    assert responses_call.ended_at is not None

    output = responses_call.output
    assert output is not None
    # For streaming, the accumulated output should contain the response
    assert "id" in output
    assert "output" in output


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
@pytest.mark.asyncio
async def test_litellm_aresponses_stream(
    client: weave.trace.weave_client.WeaveClient, patch_litellm: None
) -> None:
    """
    Requirement: Streaming litellm.aresponses() should accumulate and be traced
    Interface: weave client call recording, async iterator behavior
    Given: A patched litellm environment with weave client
    When: User calls await litellm.aresponses(stream=True) and async iterates
    Then: User receives streaming chunks, call.output contains accumulated response
    """
    response = await litellm.aresponses(
        api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
        model="gpt-4o-mini",
        input="Say hi in one word.",
        stream=True,
    )

    # Consume the async stream
    all_text = ""
    async for event in response:
        event_type = getattr(event, "type", None)
        if event_type == "response.output_text.delta":
            all_text += event.delta

    assert all_text  # Should have accumulated some text

    calls = list(client.get_calls())
    assert len(calls) >= 1

    # Find the litellm.aresponses call
    responses_call = None
    for call in calls:
        if call.op_name and "litellm.aresponses" in call.op_name:
            responses_call = call
            break

    assert responses_call is not None, "litellm.aresponses call not found"
    assert responses_call.exception is None
    assert responses_call.ended_at is not None

    output = responses_call.output
    assert output is not None
    assert "id" in output
    assert "output" in output


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_model_predict(
    client: weave.trace.weave_client.WeaveClient, patch_litellm: None
) -> None:
    class TranslatorModel(weave.Model):
        model: str
        temperature: float

        @weave.op
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
