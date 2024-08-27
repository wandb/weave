import os
import typing

import pytest
from openai import AsyncOpenAI, OpenAI

import weave
from weave.trace_server import trace_server_interface as tsi

model = "gpt-4o"


def _get_call_output(call: tsi.CallSchema) -> typing.Any:
    """This is a hack and should not be needed. We should be able to auto-resolve this for the user.

    Keeping this here for now, but it should be removed in the future once we have a better solution.
    """
    call_output = call.output
    if isinstance(call_output, str) and call_output.startswith("weave://"):
        return weave.ref(call_output).get()
    return call_output


def op_name_from_ref(ref: str) -> str:
    return ref.split("/")[-1].split(":")[0]


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_openai_quickstart(client: weave.trace.weave_client.WeaveClient) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY")

    openai_client = OpenAI(api_key=api_key)

    response = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "How are you?"}],
        temperature=0.0,
        max_tokens=64,
        top_p=1,
    )
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    print(res)

    exp = "I'm just a computer program, so I don't have feelings, but I'm here and ready to help you! How can I assist you today?"
    assert response.choices[0].message.content == exp

    call = res.calls[0]
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = _get_call_output(call)
    assert output.model == "gpt-4o-2024-05-13"
    assert output.object == "chat.completion"

    usage = call.summary["usage"][output.model]  # type: ignore
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


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
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
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1

    exp = "I'm just a computer program, so I don't have feelings, but I'm here and ready to help you! How can I assist you today?"
    assert response.choices[0].message.content == exp

    call = res.calls[0]
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = _get_call_output(call)
    assert output.model == "gpt-4o-2024-05-13"
    assert output.object == "chat.completion"

    usage = call.summary["usage"][output.model]  # type: ignore
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


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
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

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1

    exp = "I'm just a computer program, so I don't have feelings, but thanks for asking! How can I assist you today?"
    assert all_content == exp

    call = res.calls[0]
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = _get_call_output(call)
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


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
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

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1

    exp = "I'm just a computer program, so I don't have feelings, but thanks for asking! How can I assist you today?"
    assert all_content == exp

    call = res.calls[0]
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = _get_call_output(call)
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


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
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

    for chunk in response:
        pass
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    call = res.calls[0]
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = _get_call_output(call)
    usage = call.summary["usage"][output["model"]]  # type: ignore
    assert usage["total_tokens"] == 35
    assert usage["completion_tokens"] == 24
    assert usage["prompt_tokens"] == 11


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
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
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1

    exp = '{"name":"Sachin Tendulkar","team":"India","highest_score":248}'
    assert response.choices[0].message.function_call.arguments == exp

    call = res.calls[0]
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = _get_call_output(call)
    assert output.model == "gpt-4o-2024-05-13"
    assert output.object == "chat.completion"

    usage = call.summary["usage"][output.model]  # type: ignore
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


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
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
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1

    exp = '{"name":"Sachin Tendulkar","team":"India","highest_score":200}'
    assert response.choices[0].message.function_call.arguments == exp

    call = res.calls[0]
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = _get_call_output(call)
    assert output.model == "gpt-4o-2024-05-13"
    assert output.object == "chat.completion"

    usage = call.summary["usage"][output.model]  # type: ignore
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


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
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
    async for chunk in response:
        pass

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    call = res.calls[0]
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


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
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

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1

    exp = '{"name":"Sachin Tendulkar","team":"India","highest_score":248}'
    assert response.choices[0].message.tool_calls[0].function.arguments == exp

    call = res.calls[0]
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = _get_call_output(call)
    assert output.model == "gpt-4o-2024-05-13"
    assert output.object == "chat.completion"

    usage = call.summary["usage"][output.model]  # type: ignore
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


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
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
    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1

    exp = '{"name":"Sachin Tendulkar","team":"India","highest_score":248}'
    assert response.choices[0].message.tool_calls[0].function.arguments == exp

    call = res.calls[0]
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = _get_call_output(call)
    assert output.model == "gpt-4o-2024-05-13"
    assert output.object == "chat.completion"

    usage = call.summary["usage"][output.model]  # type: ignore
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


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
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
    async for chunk in response:
        pass

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1
    call = res.calls[0]
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


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
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

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1

    exp = "Hello! As a context manager, you play a crucial role in managing resources efficiently and ensuring proper setup and teardown in Python. You likely implement methods like `__enter__` and `__exit__` to manage contexts properly. How can I assist you today?"
    assert all_content == exp

    call = res.calls[0]
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = _get_call_output(call)
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


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
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

    res = client.server.calls_query(tsi.CallsQueryReq(project_id=client._project_id()))
    assert len(res.calls) == 1

    exp = "Hello! It sounds like you're referring to the concept of an asynchronous context manager in programming, typically found in languages like Python. Asynchronous context managers are useful for managing resources that need to be setup and cleaned up, often in an asynchronous manner. Do you have any specific questions or scenarios you need help with regarding async context managers?"
    assert all_content == exp

    call = res.calls[0]
    assert op_name_from_ref(call.op_name) == "openai.chat.completions.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = _get_call_output(call)
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
