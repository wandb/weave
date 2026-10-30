import json
import os
from collections.abc import AsyncIterator, Generator
from typing import Any

import httpx
import pytest
from openai import AsyncOpenAI, OpenAI
from openai._legacy_response import LegacyAPIResponse
from openai._models import FinalRequestOptions
from openai._response import APIResponse
from openai.types.chat import ChatCompletion

import weave
from weave.integrations.integration_utilities import op_name_from_ref
from weave.integrations.openai.openai_sdk import (
    get_openai_patcher,
    maybe_unwrap_api_response,
)
from weave.trace.weave_client import WeaveClient

model = "gpt-4o"
RawChatCompletionResponse = (
    LegacyAPIResponse[ChatCompletion] | APIResponse[ChatCompletion]
)
RawChatCompletionResponseCls = (
    type[LegacyAPIResponse[ChatCompletion]] | type[APIResponse[ChatCompletion]]
)


@pytest.fixture(autouse=True)
def patch_openai() -> Generator[None, None, None]:
    """Patch OpenAI for all tests in this file."""
    patcher = get_openai_patcher()
    patcher.attempt_patch()
    yield
    patcher.undo_patch()


def _unread_chat_completion_response(
    response_cls: RawChatCompletionResponseCls,
) -> RawChatCompletionResponse:
    body = (
        b'{"id":"chatcmpl-test","object":"chat.completion","created":1,'
        b'"model":"gpt-4o-mini","choices":[{"index":0,"message":'
        b'{"role":"assistant","content":"hi"},"finish_reason":"stop"}]}'
    )
    response = httpx.Response(
        200,
        headers={"content-type": "application/json"},
        stream=httpx.ByteStream(body),
        request=httpx.Request(
            "POST",
            "https://api.openai.com/v1/chat/completions",
        ),
    )
    return response_cls(
        raw=response,
        cast_to=ChatCompletion,
        client=OpenAI(api_key="sk-test"),
        stream=False,
        stream_cls=None,
        options=FinalRequestOptions.construct(
            method="post",
            url="/chat/completions",
        ),
        retries_taken=0,
    )


@pytest.mark.parametrize("response_cls", [LegacyAPIResponse, APIResponse])
def test_maybe_unwrap_api_response_reads_unread_raw_response(
    response_cls: RawChatCompletionResponseCls,
) -> None:
    # LegacyAPIResponse.parse() raises on an unread body — the bug we fix.
    # APIResponse.parse() self-reads, so it has no equivalent failure mode.
    if response_cls is LegacyAPIResponse:
        with pytest.raises(httpx.ResponseNotRead):
            _unread_chat_completion_response(response_cls).parse()

    raw_response = _unread_chat_completion_response(response_cls)
    parsed_for_trace = maybe_unwrap_api_response(raw_response)

    assert isinstance(parsed_for_trace, ChatCompletion)
    assert parsed_for_trace.choices[0].message.content == "hi"

    # The same raw response is returned to raw-response callers after tracing.
    parsed_for_caller = raw_response.parse()
    assert parsed_for_caller.choices[0].message.content == "hi"


def test_maybe_unwrap_api_response_returns_value_when_parse_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_response = _unread_chat_completion_response(LegacyAPIResponse)

    def boom(self: LegacyAPIResponse) -> None:
        raise RuntimeError("unexpected parse failure")

    monkeypatch.setattr(LegacyAPIResponse, "parse", boom)

    assert maybe_unwrap_api_response(raw_response) is raw_response


@pytest.mark.vcr(filter_headers=["authorization"])
@pytest.mark.asyncio
async def test_openai_async_quickstart(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    openai_client = AsyncOpenAI(api_key=api_key)

    response = await openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "How are you?"}],
        temperature=0.0,
        max_tokens=64,
        top_p=1,
    )
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    exp = "I'm just a computer program, so I don't have feelings, but I'm here and ready to help you! How can I assist you today?"
    assert response.choices[0].message.content == exp

    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    # Integration-tracking metadata is stamped on every patched call.
    integration = call.attributes["integration"]
    assert integration["name"] == "openai"
    assert integration["version"]  # weave SDK version
    assert integration["meta"]["package_name"] == "openai"

    output = call.output
    assert output["model"] == "gpt-4o-2024-05-13"
    assert output["object"] == "chat.completion"

    usage = call.summary["usage"][output["model"]]  # type: ignore
    assert usage["requests"] == 1
    assert usage["completion_tokens"] == 28
    assert usage["prompt_tokens"] == 11
    assert usage["total_tokens"] == 39

    inputs = call.inputs
    assert inputs["model"] == "gpt-4o"
    assert inputs["messages"] == [{"role": "user", "content": "How are you?"}]
    assert inputs["max_tokens"] == 64
    assert inputs["temperature"] == 0.0
    assert inputs["top_p"] == 1


@pytest.mark.vcr(filter_headers=["authorization"])
def test_openai_stream_quickstart(client: weave.trace.weave_client.WeaveClient) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    openai_client = OpenAI(api_key=api_key)

    response = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "How are you?"}],
        temperature=0.0,
        max_tokens=64,
        top_p=1,
        stream=True,
    )

    all_content = ""
    for chunk in response:
        if chunk.choices[0].delta.content:
            all_content += chunk.choices[0].delta.content

    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    exp = "I'm just a computer program, so I don't have feelings, but thanks for asking! How can I assist you today?"
    assert all_content == exp

    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output["model"] == "gpt-4o-2024-05-13"
    assert output["object"] == "chat.completion"

    inputs = call.inputs
    assert inputs["model"] == "gpt-4o"
    assert inputs["messages"] == [{"role": "user", "content": "How are you?"}]
    assert inputs["max_tokens"] == 64
    assert inputs["temperature"] == 0.0
    assert inputs["top_p"] == 1

    # usage information should be available even if `stream_options` is not set
    usage = call.summary["usage"][output["model"]]  # type: ignore
    assert usage["total_tokens"] == 35
    assert usage["completion_tokens"] == 24
    assert usage["prompt_tokens"] == 11

    # since we are setting `stream_options`, the chunk should not have usage information
    assert chunk.usage is None


@pytest.mark.vcr(filter_headers=["authorization"])
@pytest.mark.asyncio
async def test_openai_async_stream_quickstart(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    openai_client = AsyncOpenAI(api_key=api_key)

    response = await openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "How are you?"}],
        temperature=0.0,
        max_tokens=64,
        top_p=1,
        stream=True,
    )
    all_content = ""
    async for chunk in response:
        if chunk.choices[0].delta.content:
            all_content += chunk.choices[0].delta.content

    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    exp = "I'm just a computer program, so I don't have feelings, but thanks for asking! How can I assist you today?"
    assert all_content == exp

    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output["model"] == "gpt-4o-2024-05-13"
    assert output["object"] == "chat.completion"

    usage = call.output["usage"]  # type: ignore
    assert usage["total_tokens"] == 35
    assert usage["completion_tokens"] == 24
    assert usage["prompt_tokens"] == 11
    assert chunk.usage is None

    inputs = call.inputs
    assert inputs["model"] == "gpt-4o"
    assert inputs["messages"] == [{"role": "user", "content": "How are you?"}]
    assert inputs["max_tokens"] == 64
    assert inputs["temperature"] == 0.0
    assert inputs["top_p"] == 1


@pytest.mark.vcr(filter_headers=["authorization"])
def test_openai_stream_usage_quickstart(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    openai_client = OpenAI(api_key=api_key)

    response = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "How are you?"}],
        temperature=0.0,
        max_tokens=64,
        top_p=1,
        stream=True,
        stream_options={
            "include_usage": True
        },  # User needs to pass this argument to get usage
    )

    for _chunk in response:
        pass
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    usage = call.summary["usage"][output["model"]]  # type: ignore
    assert usage["total_tokens"] == 35
    assert usage["completion_tokens"] == 24
    assert usage["prompt_tokens"] == 11


@pytest.mark.vcr(filter_headers=["authorization"])
def test_openai_function_call(client: weave.trace.weave_client.WeaveClient) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    openai_client = OpenAI(api_key=api_key)

    function_list = [
        {
            "name": "cricket_player_names",  # Function Name
            "description": "store the name of players",  # Meta information of function
            "parameters": {  # parameters
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the player",
                    },
                    "team:": {
                        "type": "string",
                        "description": "The team of the player",
                    },
                    "highest_score": {
                        "type": "number",
                        "description": "The highest score of the player",
                    },
                },
                "required": ["name", "team", "highest_score"],
            },
        }
    ]

    response = openai_client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": "Can you name a cricket player along with team name and highest score?",
            }
        ],
        functions=function_list,
        function_call={
            "name": "cricket_player_names"
        },  # this forces the LLM to do function call.
        temperature=0.0,
        max_tokens=64,
        top_p=1,
    )
    print(response)
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    exp = '{"name":"Sachin Tendulkar","team":"India","highest_score":248}'
    assert response.choices[0].message.function_call.arguments == exp

    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output["model"] == "gpt-4o-2024-05-13"
    assert output["object"] == "chat.completion"

    usage = call.summary["usage"][output["model"]]  # type: ignore
    assert usage["total_tokens"] == 117
    assert usage["completion_tokens"] == 18
    assert usage["prompt_tokens"] == 99

    inputs = call.inputs
    assert inputs["model"] == "gpt-4o"
    assert (
        inputs["messages"][0]["content"]
        == "Can you name a cricket player along with team name and highest score?"
    )
    assert inputs["function_call"]["name"] == "cricket_player_names"
    assert inputs["functions"] == function_list
    assert inputs["max_tokens"] == 64
    assert inputs["temperature"] == 0.0
    assert inputs["top_p"] == 1


@pytest.mark.vcr(filter_headers=["authorization"])
@pytest.mark.asyncio
async def test_openai_function_call_async(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    openai_client = AsyncOpenAI(api_key=api_key)

    function_list = [
        {
            "name": "cricket_player_names",  # Function Name
            "description": "store the name of players",  # Meta information of function
            "parameters": {  # parameters
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the player",
                    },
                    "team:": {
                        "type": "string",
                        "description": "The team of the player",
                    },
                    "highest_score": {
                        "type": "number",
                        "description": "The highest score of the player",
                    },
                },
                "required": ["name", "team", "highest_score"],
            },
        }
    ]

    response = await openai_client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": "Can you name a cricket player along with team name and highest score?",
            }
        ],
        functions=function_list,
        function_call={
            "name": "cricket_player_names"
        },  # this forces the LLM to do function call.
        temperature=0.0,
        max_tokens=64,
        top_p=1,
    )
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    exp = '{"name":"Sachin Tendulkar","team":"India","highest_score":200}'
    assert response.choices[0].message.function_call.arguments == exp

    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output["model"] == "gpt-4o-2024-05-13"
    assert output["object"] == "chat.completion"

    usage = call.summary["usage"][output["model"]]  # type: ignore
    assert usage["total_tokens"] == 117
    assert usage["completion_tokens"] == 18
    assert usage["prompt_tokens"] == 99

    inputs = call.inputs
    assert inputs["model"] == "gpt-4o"
    assert (
        inputs["messages"][0]["content"]
        == "Can you name a cricket player along with team name and highest score?"
    )
    assert inputs["function_call"]["name"] == "cricket_player_names"
    assert inputs["functions"] == function_list
    assert inputs["max_tokens"] == 64
    assert inputs["temperature"] == 0.0
    assert inputs["top_p"] == 1


@pytest.mark.vcr(filter_headers=["authorization"])
@pytest.mark.asyncio
async def test_openai_function_call_async_stream(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    openai_client = AsyncOpenAI(api_key=api_key)

    function_list = [
        {
            "name": "cricket_player_names",  # Function Name
            "description": "store the name of players",  # Meta information of function
            "parameters": {  # parameters
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the player",
                    },
                    "team:": {
                        "type": "string",
                        "description": "The team of the player",
                    },
                    "highest_score": {
                        "type": "number",
                        "description": "The highest score of the player",
                    },
                },
                "required": ["name", "team", "highest_score"],
            },
        }
    ]

    response = await openai_client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": "Can you name a cricket player along with team name and highest score?",
            }
        ],
        functions=function_list,
        function_call={
            "name": "cricket_player_names"
        },  # this forces the LLM to do function call.
        temperature=0.0,
        max_tokens=64,
        top_p=1,
        stream=True,
    )
    # TODO: figure out if this is the write pattern
    async for _chunk in response:
        pass

    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    exp = '{"name":"Sachin Tendulkar","team":"India","highest_score":200}'
    choice = call.output["choices"][0]  # type: ignore
    assert choice["message"]["function_call"]["arguments"] == exp
    assert choice["message"]["function_call"]["name"] == "cricket_player_names"
    assert choice["finish_reason"] == "stop"
    assert choice["message"]["role"] == "assistant"

    assert call.output["id"] == "chatcmpl-9cDoAspZs24R7hQPixbNse9Lg5dgR"  # type: ignore
    assert call.output["model"] == "gpt-4o-2024-05-13"  # type: ignore
    assert call.output["object"] == "chat.completion"  # type: ignore

    inputs = call.inputs
    assert inputs["model"] == "gpt-4o"
    assert (
        inputs["messages"][0]["content"]
        == "Can you name a cricket player along with team name and highest score?"
    )
    assert inputs["function_call"]["name"] == "cricket_player_names"
    assert inputs["functions"] == function_list
    assert inputs["max_tokens"] == 64
    assert inputs["temperature"] == 0.0
    assert inputs["top_p"] == 1


@pytest.mark.vcr(filter_headers=["authorization"])
def test_openai_tool_call(client: weave.trace.weave_client.WeaveClient) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    openai_client = OpenAI(api_key=api_key)

    function_list = [
        {
            "type": "function",
            "function": {
                "name": "cricket_player_names",  # Function Name
                "description": "store the name of players",  # Meta information of function
                "parameters": {  # parameters
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the player",
                        },
                        "team:": {
                            "type": "string",
                            "description": "The team of the player",
                        },
                        "highest_score": {
                            "type": "number",
                            "description": "The highest score of the player",
                        },
                    },
                    "required": ["name", "team", "highest_score"],
                },
            },
        }
    ]

    response = openai_client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": "Can you name a cricket player along with team name and highest score?",
            }
        ],
        tools=function_list,
        tool_choice="required",  # this forces the LLM to do function call.
        temperature=0.0,
        max_tokens=64,
        top_p=1,
    )
    print(response)

    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    exp = '{"name":"Sachin Tendulkar","team":"India","highest_score":248}'
    assert response.choices[0].message.tool_calls[0].function.arguments == exp

    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output["model"] == "gpt-4o-2024-05-13"
    assert output["object"] == "chat.completion"

    usage = call.summary["usage"][output["model"]]  # type: ignore
    assert usage["total_tokens"] == 117
    assert usage["completion_tokens"] == 27
    assert usage["prompt_tokens"] == 90

    inputs = call.inputs
    assert inputs["model"] == "gpt-4o"
    assert (
        inputs["messages"][0]["content"]
        == "Can you name a cricket player along with team name and highest score?"
    )
    assert inputs["tools"] == function_list
    assert inputs["tool_choice"] == "required"
    assert inputs["max_tokens"] == 64
    assert inputs["temperature"] == 0.0
    assert inputs["top_p"] == 1


@pytest.mark.vcr(filter_headers=["authorization"])
@pytest.mark.asyncio
async def test_openai_tool_call_async(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    openai_client = AsyncOpenAI(api_key=api_key)

    function_list = [
        {
            "type": "function",
            "function": {
                "name": "cricket_player_names",  # Function Name
                "description": "store the name of players",  # Meta information of function
                "parameters": {  # parameters
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the player",
                        },
                        "team:": {
                            "type": "string",
                            "description": "The team of the player",
                        },
                        "highest_score": {
                            "type": "number",
                            "description": "The highest score of the player",
                        },
                    },
                    "required": ["name", "team", "highest_score"],
                },
            },
        }
    ]

    response = await openai_client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": "Can you name a cricket player along with team name and highest score?",
            }
        ],
        tools=function_list,
        tool_choice="required",  # this forces the LLM to do function call.
        temperature=0.0,
        max_tokens=64,
        top_p=1,
    )
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    exp = '{"name":"Sachin Tendulkar","team":"India","highest_score":248}'
    assert response.choices[0].message.tool_calls[0].function.arguments == exp

    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output["model"] == "gpt-4o-2024-05-13"
    assert output["object"] == "chat.completion"

    usage = call.summary["usage"][output["model"]]  # type: ignore
    assert usage["total_tokens"] == 117
    assert usage["completion_tokens"] == 27
    assert usage["prompt_tokens"] == 90

    inputs = call.inputs
    assert inputs["model"] == "gpt-4o"
    assert (
        inputs["messages"][0]["content"]
        == "Can you name a cricket player along with team name and highest score?"
    )
    assert inputs["tools"] == function_list
    assert inputs["tool_choice"] == "required"
    assert inputs["max_tokens"] == 64
    assert inputs["temperature"] == 0.0
    assert inputs["top_p"] == 1


@pytest.mark.vcr(filter_headers=["authorization"])
@pytest.mark.asyncio
async def test_openai_tool_call_async_stream(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    openai_client = AsyncOpenAI(api_key=api_key)

    function_list = [
        {
            "type": "function",
            "function": {
                "name": "cricket_player_names",  # Function Name
                "description": "store the name of players",  # Meta information of function
                "parameters": {  # parameters
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the player",
                        },
                        "team:": {
                            "type": "string",
                            "description": "The team of the player",
                        },
                        "highest_score": {
                            "type": "number",
                            "description": "The highest score of the player",
                        },
                    },
                    "required": ["name", "team", "highest_score"],
                },
            },
        }
    ]

    response = await openai_client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": "Can you name a cricket player along with team name and highest score?",
            }
        ],
        tools=function_list,
        tool_choice="required",  # this forces the LLM to do function call.
        temperature=0.0,
        max_tokens=64,
        top_p=1,
        stream=True,
        stream_options={
            "include_usage": True
        },  # User needs to pass this argument to get usage
    )
    # TODO: figure out if this is the write pattern
    async for _chunk in response:
        pass

    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    exp = '{"name":"Sachin Tendulkar","team":"India","highest_score":248}'
    choice = call.output["choices"][0]  # type: ignore
    assert choice["message"]["tool_calls"][0]["function"]["arguments"] == exp
    assert (
        choice["message"]["tool_calls"][0]["function"]["name"] == "cricket_player_names"
    )
    assert choice["message"]["tool_calls"][0]["id"] == "call_f0b9z5IxIGxTMHYa55QnIXdG"
    assert choice["message"]["tool_calls"][0]["type"] == "function"
    assert choice["finish_reason"] == "tool_calls"
    assert choice["message"]["role"] == "assistant"

    assert call.output["id"] == "chatcmpl-9cEL2tGY6V4efCUFlecqgb6HZOhpV"  # type: ignore
    assert call.output["model"] == "gpt-4o-2024-05-13"  # type: ignore
    assert call.output["object"] == "chat.completion"  # type: ignore

    usage = call.output["usage"]  # type: ignore
    assert usage["total_tokens"] == 117
    assert usage["completion_tokens"] == 27
    assert usage["prompt_tokens"] == 90

    inputs = call.inputs
    assert inputs["model"] == "gpt-4o"
    assert (
        inputs["messages"][0]["content"]
        == "Can you name a cricket player along with team name and highest score?"
    )
    assert inputs["tools"] == function_list
    assert inputs["tool_choice"] == "required"
    assert inputs["max_tokens"] == 64
    assert inputs["temperature"] == 0.0
    assert inputs["top_p"] == 1


@pytest.mark.vcr(filter_headers=["authorization"])
def test_openai_as_context_manager(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    openai_client = OpenAI(api_key=api_key)

    with openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Hello, I am context manager!"}],
        stream=True,
    ) as response:
        all_content = ""
        for chunk in response:
            if chunk.choices[0].delta.content:
                all_content += chunk.choices[0].delta.content

    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    exp = "Hello! As a context manager, you play a crucial role in managing resources efficiently and ensuring proper setup and teardown in Python. You likely implement methods like `__enter__` and `__exit__` to manage contexts properly. How can I assist you today?"
    assert all_content == exp

    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output["model"] == "gpt-4o-2024-05-13"
    assert output["object"] == "chat.completion"

    inputs = call.inputs
    assert inputs["model"] == "gpt-4o"
    assert inputs["messages"] == [
        {"role": "user", "content": "Hello, I am context manager!"}
    ]

    # usage information should be available even if `stream_options` is not set
    usage = call.summary["usage"][output["model"]]  # type: ignore
    assert usage["total_tokens"] == 67
    assert usage["completion_tokens"] == 53
    assert usage["prompt_tokens"] == 14

    # since we are setting `stream_options`, the chunk should not have usage information
    assert chunk.usage is None


@pytest.mark.vcr(filter_headers=["authorization"])
@pytest.mark.asyncio
async def test_openai_as_context_manager_async(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    openai_client = AsyncOpenAI(api_key=api_key)

    response = await openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Hello, I am async context manager!"}],
        stream=True,
    )

    async with response:
        all_content = ""
        async for chunk in response:
            if chunk.choices[0].delta.content:
                all_content += chunk.choices[0].delta.content

    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    exp = "Hello! It sounds like you're referring to the concept of an asynchronous context manager in programming, typically found in languages like Python. Asynchronous context managers are useful for managing resources that need to be setup and cleaned up, often in an asynchronous manner. Do you have any specific questions or scenarios you need help with regarding async context managers?"
    assert all_content == exp

    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output["model"] == "gpt-4o-2024-05-13"
    assert output["object"] == "chat.completion"

    inputs = call.inputs
    assert inputs["model"] == "gpt-4o"
    assert inputs["messages"] == [
        {"role": "user", "content": "Hello, I am async context manager!"}
    ]

    # usage information should be available even if `stream_options` is not set
    usage = call.summary["usage"][output["model"]]  # type: ignore
    assert usage["total_tokens"] == 81
    assert usage["completion_tokens"] == 66
    assert usage["prompt_tokens"] == 15

    # since we are setting `stream_options`, the chunk should not have usage information
    assert chunk.usage is None


@pytest.mark.vcr(
    filter_headers=["authorization"],
)
def test_openai_moderation_patching(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    openai_client = OpenAI(api_key=api_key)

    response = openai_client.moderations.create(
        model="omni-moderation-latest",
        input="...text to classify goes here...",
    )

    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    exp_harassment = False
    assert response.results[0].categories.harassment == exp_harassment

    assert op_name_from_ref(call.op_name) == "openai.moderations.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output["model"] == "omni-moderation-latest-intents"

    inputs = call.inputs
    assert inputs["model"] == "omni-moderation-latest"
    assert inputs["input"] == "...text to classify goes here..."


@pytest.mark.vcr(filter_headers=["authorization"])
@pytest.mark.asyncio
async def test_openai_async_moderation_patching(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    openai_client = AsyncOpenAI(api_key=api_key)

    response = await openai_client.moderations.create(
        model="omni-moderation-latest",
        input="...text to classify goes here...",
    )

    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    exp_harassment = False
    assert response.results[0].categories.harassment == exp_harassment

    assert op_name_from_ref(call.op_name) == "openai.moderations.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output["model"] == "omni-moderation-latest-intents"

    inputs = call.inputs
    assert inputs["model"] == "omni-moderation-latest"
    assert inputs["input"] == "...text to classify goes here..."


@pytest.mark.vcr(
    filter_headers=["authorization"],
)
def test_openai_embeddings_patching(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    openai_client = OpenAI(api_key=api_key)

    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input="embed this",
    )

    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    exp_embeddings = "list"
    assert response.object == exp_embeddings

    assert op_name_from_ref(call.op_name) == "openai.embeddings.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output["model"] == "text-embedding-3-small"

    inputs = call.inputs
    assert inputs["model"] == "text-embedding-3-small"
    assert inputs["input"] == "embed this"


@pytest.mark.vcr(filter_headers=["authorization"])
@pytest.mark.asyncio
async def test_openai_async_embeddings_patching(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    openai_client = AsyncOpenAI(api_key=api_key)

    response = await openai_client.embeddings.create(
        model="text-embedding-3-small",
        input="embed this",
    )

    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    exp_embeddings = "list"
    assert response.object == exp_embeddings

    assert op_name_from_ref(call.op_name) == "openai.embeddings.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output["model"] == "text-embedding-3-small"

    inputs = call.inputs
    assert inputs["model"] == "text-embedding-3-small"
    assert inputs["input"] == "embed this"


### Responses API


@pytest.mark.vcr(
    filter_headers=["authorization"],
)
def test_openai_responses_quickstart(client: WeaveClient) -> None:
    oai = OpenAI()

    response = oai.responses.create(
        model="gpt-4o-2024-08-06",
        input="Write a one-sentence bedtime story about a unicorn.",
    )

    calls = client.get_calls()
    assert len(calls) == 1

    call = calls[0]
    assert op_name_from_ref(call.op_name) == "openai.responses.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output["model"] == "gpt-4o-2024-08-06"
    assert output["object"] == "response"
    assert isinstance(output["output"][0]["content"][0]["text"], str)
    assert (
        output["output"][0]["content"][0]["text"]
        == "Under a moonlit sky, the gentle unicorn whispered dreams of stardust to sleepy children, guiding them to restful slumber."
    )

    usage = call.summary["usage"][output["model"]]  # type: ignore
    assert usage["requests"] == 1
    assert usage["input_tokens"] == 36
    assert usage["output_tokens"] == 27
    assert usage["total_tokens"] == 63
    assert usage["output_tokens_details"]["reasoning_tokens"] == 0  # type: ignore
    assert usage["input_tokens_details"]["cached_tokens"] == 0  # type: ignore

    inputs = call.inputs
    assert inputs["model"] == "gpt-4o-2024-08-06"
    assert inputs["input"] == "Write a one-sentence bedtime story about a unicorn."


@pytest.mark.vcr(
    filter_headers=["authorization"],
)
def test_openai_responses_quickstart_stream(client: WeaveClient) -> None:
    oai = OpenAI()

    stream = oai.responses.create(
        model="gpt-4o-2024-08-06",
        input="Write a one-sentence bedtime story about a unicorn.",
        stream=True,
    )
    res = list(stream)

    calls = client.get_calls()
    assert len(calls) == 1

    call = calls[0]
    assert op_name_from_ref(call.op_name) == "openai.responses.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output["model"] == "gpt-4o-2024-08-06"
    assert output["object"] == "response"
    assert isinstance(output["output"][0]["content"][0]["text"], str)
    assert (
        output["output"][0]["content"][0]["text"]
        == "Under the shimmering glow of the moon, a gentle unicorn danced across a field of twinkling flowers, leaving trails of stardust as every dreamer peacefully drifted to sleep."
    )

    usage = call.summary["usage"][output["model"]]  # type: ignore
    assert usage["requests"] == 1
    assert usage["input_tokens"] == 36
    assert usage["output_tokens"] == 38
    assert usage["total_tokens"] == 74
    assert usage["output_tokens_details"]["reasoning_tokens"] == 0
    assert usage["input_tokens_details"]["cached_tokens"] == 0

    inputs = call.inputs
    assert inputs["model"] == "gpt-4o-2024-08-06"
    assert inputs["input"] == "Write a one-sentence bedtime story about a unicorn."


@pytest.mark.vcr(
    filter_headers=["authorization"],
)
@pytest.mark.asyncio
async def test_openai_responses_quickstart_async(client: WeaveClient) -> None:
    oai = AsyncOpenAI()

    response = await oai.responses.create(
        model="gpt-4o-2024-08-06",
        input="Write a one-sentence bedtime story about a unicorn.",
    )

    calls = client.get_calls()
    assert len(calls) == 1

    call = calls[0]
    assert op_name_from_ref(call.op_name) == "openai.responses.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output["model"] == "gpt-4o-2024-08-06"
    assert output["object"] == "response"
    assert isinstance(output["output"][0]["content"][0]["text"], str)
    assert (
        output["output"][0]["content"][0]["text"]
        == "Under the twinkling starlit sky, Luna the unicorn gently sang lullabies to the moon, casting dreams of shimmering rainbows across the sleeping world."
    )

    usage = call.summary["usage"][output["model"]]  # type: ignore
    assert usage["requests"] == 1
    assert usage["input_tokens"] == 36
    assert usage["output_tokens"] == 33
    assert usage["total_tokens"] == 69
    assert usage["output_tokens_details"]["reasoning_tokens"] == 0
    assert usage["input_tokens_details"]["cached_tokens"] == 0

    inputs = call.inputs
    assert inputs["model"] == "gpt-4o-2024-08-06"
    assert inputs["input"] == "Write a one-sentence bedtime story about a unicorn."


@pytest.mark.vcr(
    filter_headers=["authorization"],
)
@pytest.mark.asyncio
async def test_openai_responses_quickstart_async_stream(client: WeaveClient) -> None:
    oai = AsyncOpenAI()

    response = await oai.responses.create(
        model="gpt-4o-2024-08-06",
        input="Write a one-sentence bedtime story about a unicorn.",
        stream=True,
    )
    async for _chunk in response:
        pass

    calls = client.get_calls()
    assert len(calls) == 1

    call = calls[0]
    assert op_name_from_ref(call.op_name) == "openai.responses.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output["model"] == "gpt-4o-2024-08-06"
    assert output["object"] == "response"
    assert isinstance(output["output"][0]["content"][0]["text"], str)
    assert (
        output["output"][0]["content"][0]["text"]
        == "Under the silver glow of the moon, a gentle unicorn softly treaded through the starlit meadow, where dreams blossomed like the flowers beneath her hooves."
    )

    usage = call.summary["usage"][output["model"]]  # type: ignore
    assert usage["requests"] == 1
    assert usage["input_tokens"] == 36
    assert usage["output_tokens"] == 34
    assert usage["total_tokens"] == 70
    assert usage["output_tokens_details"]["reasoning_tokens"] == 0
    assert usage["input_tokens_details"]["cached_tokens"] == 0

    inputs = call.inputs
    assert inputs["model"] == "gpt-4o-2024-08-06"
    assert inputs["input"] == "Write a one-sentence bedtime story about a unicorn."


@pytest.mark.vcr(
    filter_headers=["authorization"],
)
def test_openai_responses_tool_calling(client: WeaveClient) -> None:
    oai = OpenAI()

    response = oai.responses.create(
        model="gpt-4o-2024-08-06",
        tools=[{"type": "web_search_preview"}],
        input="What was a positive news story from today?",
    )

    calls = client.get_calls()
    assert len(calls) == 1

    call = calls[0]
    assert op_name_from_ref(call.op_name) == "openai.responses.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output["model"] == "gpt-4o-2024-08-06"
    assert output["object"] == "response"

    web_search_call = output["output"][0]
    assert web_search_call["status"] == "completed"
    assert web_search_call["type"] == "web_search_call"

    response_output_message = output["output"][1]
    search_results = response_output_message["content"][0]["annotations"]
    assert len(search_results) > 0

    tools = call.output["tools"]
    web_search_tool = tools[0]
    assert web_search_tool["type"] == "web_search_preview"
    assert web_search_tool["search_context_size"] == "medium"
    assert web_search_tool["user_location"]["type"] == "approximate"
    assert web_search_tool["user_location"]["country"] == "US"

    usage = call.summary["usage"][output["model"]]  # type: ignore
    assert usage["input_tokens"] == 328
    assert usage["output_tokens"] == 201
    assert usage["requests"] == 1
    assert usage["total_tokens"] == 529
    assert usage["output_tokens_details"]["reasoning_tokens"] == 0
    assert usage["input_tokens_details"]["cached_tokens"] == 0

    inputs = call.inputs
    assert inputs["input"] == "What was a positive news story from today?"
    assert inputs["model"] == "gpt-4o-2024-08-06"
    assert inputs["tools"][0]["type"] == "web_search_preview"


@pytest.mark.vcr(
    filter_headers=["authorization"],
)
def test_openai_responses_tool_calling_stream(client: WeaveClient) -> None:
    oai = OpenAI()

    response = oai.responses.create(
        model="gpt-4o-2024-08-06",
        tools=[{"type": "web_search_preview"}],
        input="What was a positive news story from today?",
        stream=True,
    )
    list(response)

    calls = client.get_calls()
    assert len(calls) == 1

    call = calls[0]
    assert op_name_from_ref(call.op_name) == "openai.responses.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output["model"] == "gpt-4o-2024-08-06"
    assert output["object"] == "response"

    web_search_call = output["output"][0]
    assert web_search_call["status"] == "completed"
    assert web_search_call["type"] == "web_search_call"

    response_output_message = output["output"][1]
    search_results = response_output_message["content"][0]["annotations"]
    assert len(search_results) > 0

    tools = call.output["tools"]
    web_search_tool = tools[0]
    assert web_search_tool["type"] == "web_search_preview"
    assert web_search_tool["search_context_size"] == "medium"
    assert web_search_tool["user_location"]["type"] == "approximate"
    assert web_search_tool["user_location"]["country"] == "US"

    usage = call.summary["usage"][output["model"]]  # type: ignore
    assert usage["input_tokens"] == 328
    assert usage["output_tokens"] == 461
    assert usage["requests"] == 1
    assert usage["total_tokens"] == 789
    assert usage["output_tokens_details"]["reasoning_tokens"] == 0
    assert usage["input_tokens_details"]["cached_tokens"] == 0

    inputs = call.inputs
    assert inputs["input"] == "What was a positive news story from today?"
    assert inputs["model"] == "gpt-4o-2024-08-06"
    assert inputs["tools"][0]["type"] == "web_search_preview"


@pytest.mark.vcr(
    filter_headers=["authorization"],
)
@pytest.mark.asyncio
async def test_openai_responses_tool_calling_async(client: WeaveClient) -> None:
    oai = AsyncOpenAI()

    response = await oai.responses.create(
        model="gpt-4o-2024-08-06",
        tools=[{"type": "web_search_preview"}],
        input="What was a positive news story from today?",
    )

    calls = client.get_calls()
    assert len(calls) == 1

    call = calls[0]
    assert op_name_from_ref(call.op_name) == "openai.responses.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    print(f"{output=}")
    assert output["model"] == "gpt-4o-2024-08-06"
    assert output["object"] == "response"

    web_search_call = output["output"][0]
    assert web_search_call["status"] == "completed"
    assert web_search_call["type"] == "web_search_call"

    response_output_message = output["output"][1]
    search_results = response_output_message["content"][0]["annotations"]
    assert len(search_results) > 0

    tools = call.output["tools"]
    web_search_tool = tools[0]
    assert web_search_tool["type"] == "web_search_preview"
    assert web_search_tool["search_context_size"] == "medium"
    assert web_search_tool["user_location"]["type"] == "approximate"
    assert web_search_tool["user_location"]["country"] == "US"

    usage = call.summary["usage"][output["model"]]  # type: ignore
    assert usage["input_tokens"] == 328
    assert usage["output_tokens"] == 379
    assert usage["requests"] == 1
    assert usage["total_tokens"] == 707
    assert usage["output_tokens_details"]["reasoning_tokens"] == 0
    assert usage["input_tokens_details"]["cached_tokens"] == 0

    inputs = call.inputs
    assert inputs["input"] == "What was a positive news story from today?"
    assert inputs["model"] == "gpt-4o-2024-08-06"
    assert inputs["tools"][0]["type"] == "web_search_preview"


@pytest.mark.vcr(
    filter_headers=["authorization"],
)
@pytest.mark.asyncio
async def test_openai_responses_tool_calling_async_stream(client: WeaveClient) -> None:
    oai = AsyncOpenAI()

    response = await oai.responses.create(
        model="gpt-4o-2024-08-06",
        tools=[{"type": "web_search_preview"}],
        input="What was a positive news story from today?",
        stream=True,
    )
    async for _chunk in response:
        pass

    calls = client.get_calls()
    assert len(calls) == 1

    call = calls[0]
    assert op_name_from_ref(call.op_name) == "openai.responses.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    print(f"{output=}")
    assert output["model"] == "gpt-4o-2024-08-06"
    assert output["object"] == "response"

    web_search_call = output["output"][0]
    assert web_search_call["status"] == "completed"
    assert web_search_call["type"] == "web_search_call"

    response_output_message = output["output"][1]
    search_results = response_output_message["content"][0]["annotations"]
    assert len(search_results) > 0

    tools = call.output["tools"]
    web_search_tool = tools[0]
    assert web_search_tool["type"] == "web_search_preview"
    assert web_search_tool["search_context_size"] == "medium"
    assert web_search_tool["user_location"]["type"] == "approximate"
    assert web_search_tool["user_location"]["country"] == "US"

    usage = call.summary["usage"][output["model"]]  # type: ignore
    assert usage["input_tokens"] == 328
    assert usage["output_tokens"] == 209
    assert usage["requests"] == 1
    assert usage["total_tokens"] == 537
    assert usage["output_tokens_details"]["reasoning_tokens"] == 0
    assert usage["input_tokens_details"]["cached_tokens"] == 0

    inputs = call.inputs
    assert inputs["input"] == "What was a positive news story from today?"
    assert inputs["model"] == "gpt-4o-2024-08-06"
    assert inputs["tools"][0]["type"] == "web_search_preview"


# `with_streaming_response` streams arrive as a raw APIResponse whose parse()
# returns the event stream, so these tests serve SSE from a mock transport.
STREAMING_RESPONSE_MODEL = "gpt-4o-2024-08-06"
STREAMING_RESPONSE_REQUEST_ID = "req_streaming_response"


def _streamed_response_events(text: str) -> list[dict[str, Any]]:
    completed = {
        "id": "resp_streaming",
        "object": "response",
        "created_at": 1,
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "instructions": None,
        "max_output_tokens": None,
        "model": STREAMING_RESPONSE_MODEL,
        "output": [
            {
                "type": "message",
                "id": "msg_streaming",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
        "parallel_tool_calls": True,
        "previous_response_id": None,
        "reasoning": {"effort": None, "summary": None},
        "store": True,
        "temperature": 1.0,
        "text": {"format": {"type": "text"}},
        "tool_choice": "auto",
        "tools": [],
        "top_p": 1.0,
        "truncation": "disabled",
        "usage": {
            "input_tokens": 4,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 2,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 6,
        },
        "user": None,
        "metadata": {},
    }
    created = {**completed, "status": "in_progress", "output": [], "usage": None}
    return [
        {"type": "response.created", "sequence_number": 0, "response": created},
        {
            "type": "response.output_text.delta",
            "sequence_number": 1,
            "item_id": "msg_streaming",
            "output_index": 0,
            "content_index": 0,
            "delta": text,
        },
        {"type": "response.completed", "sequence_number": 2, "response": completed},
    ]


def _streamed_chat_chunks(text: str) -> list[dict[str, Any]]:
    chunk = {
        "id": "chatcmpl-streaming",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": STREAMING_RESPONSE_MODEL,
    }
    return [
        {
            **chunk,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": text},
                    "finish_reason": None,
                }
            ],
        },
        {**chunk, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
        {
            **chunk,
            "choices": [],
            "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
        },
    ]


def _sse(events: list[dict[str, Any]], *, done: bool = False) -> bytes:
    lines = [f"data: {json.dumps(event)}\n\n" for event in events]
    if done:
        lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


class _ReadErrorAfter(httpx.AsyncByteStream):
    """Yields one SSE chunk, then fails the way a dropped connection does."""

    def __init__(self, first_chunk: bytes) -> None:
        self._first_chunk = first_chunk

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield self._first_chunk
        raise httpx.ReadError("connection dropped")


def _streaming_response(stream: bytes | httpx.AsyncByteStream) -> httpx.Response:
    headers = {
        "content-type": "text/event-stream",
        "x-request-id": STREAMING_RESPONSE_REQUEST_ID,
    }
    if isinstance(stream, bytes):
        return httpx.Response(200, headers=headers, content=stream)
    return httpx.Response(200, headers=headers, stream=stream)


def _async_openai(stream: bytes | httpx.AsyncByteStream) -> AsyncOpenAI:
    async def handle(request: httpx.Request) -> httpx.Response:
        return _streaming_response(stream)

    return AsyncOpenAI(
        api_key="sk-test",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )


def _sync_openai(stream: bytes) -> OpenAI:
    def handle(request: httpx.Request) -> httpx.Response:
        return _streaming_response(stream)

    return OpenAI(
        api_key="sk-test",
        http_client=httpx.Client(transport=httpx.MockTransport(handle)),
    )


def _only_call(client: WeaveClient, op_name: str) -> Any:
    calls = client.get_calls()
    assert len(calls) == 1
    call = calls[0]
    assert op_name_from_ref(call.op_name) == op_name
    assert call.ended_at is not None
    return call


@pytest.mark.asyncio
async def test_openai_responses_with_streaming_response_async(
    client: WeaveClient,
) -> None:
    oai = _async_openai(_sse(_streamed_response_events("Hello")))

    async with oai.responses.with_streaming_response.create(
        model=STREAMING_RESPONSE_MODEL, input="Hi", stream=True
    ) as raw:
        assert raw.request_id == STREAMING_RESPONSE_REQUEST_ID
        stream = await raw.parse()
        assert await raw.parse() is stream
        deltas = [
            event.delta
            async for event in stream
            if event.type == "response.output_text.delta"
        ]

    assert deltas == ["Hello"]
    assert raw.http_response.is_closed

    call = _only_call(client, "openai.responses.create")
    assert call.exception is None
    assert call.output["output"][0]["content"][0]["text"] == "Hello"
    usage = call.summary["usage"][STREAMING_RESPONSE_MODEL]
    assert usage["requests"] == 1
    assert usage["total_tokens"] == 6


def test_openai_responses_with_streaming_response_sync(client: WeaveClient) -> None:
    oai = _sync_openai(_sse(_streamed_response_events("Hello")))

    with oai.responses.with_streaming_response.create(
        model=STREAMING_RESPONSE_MODEL, input="Hi", stream=True
    ) as raw:
        deltas = [
            event.delta
            for event in raw.parse()
            if event.type == "response.output_text.delta"
        ]

    assert deltas == ["Hello"]
    assert raw.http_response.is_closed

    call = _only_call(client, "openai.responses.create")
    assert call.output["output"][0]["content"][0]["text"] == "Hello"
    assert call.summary["usage"][STREAMING_RESPONSE_MODEL]["total_tokens"] == 6


@pytest.mark.asyncio
async def test_openai_chat_with_streaming_response_async(client: WeaveClient) -> None:
    oai = _async_openai(_sse(_streamed_chat_chunks("Hello"), done=True))

    async with oai.chat.completions.with_streaming_response.create(
        model=STREAMING_RESPONSE_MODEL,
        messages=[{"role": "user", "content": "Hi"}],
        stream=True,
    ) as raw:
        contents = [
            chunk.choices[0].delta.content
            async for chunk in await raw.parse()
            if chunk.choices
        ]

    assert contents == ["Hello", None]
    assert raw.http_response.is_closed

    call = _only_call(client, "openai.chat.completions.create")
    assert call.output["choices"][0]["message"]["content"] == "Hello"
    assert call.summary["usage"][STREAMING_RESPONSE_MODEL]["total_tokens"] == 6


@pytest.mark.asyncio
async def test_openai_responses_with_streaming_response_keeps_stream_error(
    client: WeaveClient,
) -> None:
    first_event = _sse(_streamed_response_events("Hello")[:1])
    oai = _async_openai(_ReadErrorAfter(first_event))

    responses: list[Any] = []

    async def consume() -> None:
        async with oai.responses.with_streaming_response.create(
            model=STREAMING_RESPONSE_MODEL, input="Hi", stream=True
        ) as raw:
            responses.append(raw)
            async for _event in await raw.parse():
                pass

    with pytest.raises(httpx.ReadError):
        await consume()

    assert responses[0].http_response.is_closed

    call = _only_call(client, "openai.responses.create")
    assert "connection dropped" in call.exception


@pytest.mark.asyncio
async def test_openai_responses_with_streaming_response_closed_unread(
    client: WeaveClient,
) -> None:
    oai = _async_openai(_sse(_streamed_response_events("Hello")))

    async with oai.responses.with_streaming_response.create(
        model=STREAMING_RESPONSE_MODEL, input="Hi", stream=True
    ) as raw:
        pass

    assert raw.http_response.is_closed

    call = _only_call(client, "openai.responses.create")
    assert call.exception is None
    assert call.output is None
