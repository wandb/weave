import os

import pytest
from langchain_core.messages import AIMessageChunk
from langchain_nvidia_ai_endpoints import ChatNVIDIA

import weave
from weave.integrations.integration_utilities import op_name_from_ref

model = "meta/llama-3.1-8b-instruct"


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_chatnvidia_quickstart(client: weave.trace.weave_client.WeaveClient) -> None:
    api_key = os.environ.get("NVIDIA_API_KEY", "DUMMY_API_KEY")

    nvidia_client = ChatNVIDIA(
        api_key=api_key, model=model, temperature=0.0, max_tokens=64, top_p=1
    )

    response = nvidia_client.invoke("Hello!")

    calls = list(client.calls())
    # need to make 2 because of the langchain integration getting a call in there
    assert len(calls) == 2
    call = calls[1]

    assert response.content is not None

    assert (
        op_name_from_ref(call.op_name)
        == "langchain_nvidia_ai_endpoints.ChatNVIDIA-generate"
    )
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output["model"] == model

    usage = call.summary["usage"][output["model"]]  # type: ignore
    assert usage["requests"] == 1
    assert usage["completion_tokens"] == 24
    assert usage["prompt_tokens"] == 12
    assert usage["total_tokens"] == 36

    inputs = call.inputs
    assert inputs["model"] == model
    assert inputs["messages"] == [{"role": "user", "content": "Hello!"}]
    assert inputs["max_tokens"] == 64
    assert inputs["temperature"] == 0.0
    assert inputs["top_p"] == 1


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
@pytest.mark.asyncio
async def test_chatnvidia_async_quickstart(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("NVIDIA_API_KEY", "DUMMY_API_KEY")

    nvidia_client = ChatNVIDIA(
        api_key=api_key, model=model, temperature=0.0, max_tokens=64, top_p=1
    )

    response = await nvidia_client.ainvoke("Hello!")

    calls = list(client.calls())
    # need to make 2 because of the langchain integration getting a call in there
    assert len(calls) == 2
    call = calls[1]

    assert response.content is not None

    assert (
        op_name_from_ref(call.op_name)
        == "langchain_nvidia_ai_endpoints.ChatNVIDIA-generate"
    )
    assert call.started_at is not None
    assert call.started_at < call.ended_at

    output = call.output
    assert output["model"] == model

    usage = call.summary["usage"][output["model"]]
    assert usage["requests"] == 1
    assert usage["completion_tokens"] == 24
    assert usage["prompt_tokens"] == 12
    assert usage["total_tokens"] == 36

    inputs = call.inputs
    assert inputs["model"] == model
    assert inputs["messages"] == [{"role": "user", "content": "Hello!"}]
    assert inputs["max_tokens"] == 64
    assert inputs["temperature"] == 0.0
    assert inputs["top_p"] == 1


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_chatnvidia_stream_quickstart(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("NVIDIA_API_KEY", "DUMMY_API_KEY")

    nvidia_client = ChatNVIDIA(
        api_key=api_key, model=model, temperature=0.0, max_tokens=64, top_p=1
    )

    response = nvidia_client.stream("Hello!")
    answer = AIMessageChunk(content="")
    for chunk in response:
        answer += chunk
        answer.usage_metadata = chunk.usage_metadata

    calls = list(client.calls())
    # need to make 2 because of the langchain integration getting a call in there
    assert len(calls) == 2
    call = calls[1]

    assert answer.content is not None

    assert (
        op_name_from_ref(call.op_name)
        == "langchain_nvidia_ai_endpoints.ChatNVIDIA-stream"
    )
    assert call.started_at is not None
    assert call.started_at < call.ended_at

    output = call.output
    assert output["model"] == model

    print(call.summary["usage"][output["model"]])
    usage = call.summary["usage"][output["model"]]
    assert usage["requests"] == 1
    assert usage["completion_tokens"] == 24
    assert usage["prompt_tokens"] == 12
    assert usage["total_tokens"] == 36

    inputs = call.inputs
    assert inputs["model"] == model
    assert inputs["messages"] == [{"role": "user", "content": "Hello!"}]
    assert inputs["max_tokens"] == 64
    assert inputs["temperature"] == 0.0
    assert inputs["top_p"] == 1


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
@pytest.mark.asyncio
async def test_chatnvidia_async_stream_quickstart(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("NVIDIA_API_KEY", "DUMMY_API_KEY")

    nvidia_client = ChatNVIDIA(
        api_key=api_key, model=model, temperature=0.0, max_tokens=64, top_p=1
    )
    response = nvidia_client.astream("Hello!")
    answer = AIMessageChunk(content="")
    async for chunk in response:
        answer += chunk
        answer.usage_metadata = chunk.usage_metadata

    calls = list(client.calls())
    # need to make 2 because of the langchain integration getting a call in there
    assert len(calls) == 2
    call = calls[1]

    assert answer.content is not None

    assert (
        op_name_from_ref(call.op_name)
        == "langchain_nvidia_ai_endpoints.ChatNVIDIA-stream"
    )
    assert call.started_at is not None
    assert call.started_at < call.ended_at

    output = call.output
    assert output["model"] == model

    print(call.summary["usage"][output["model"]])
    usage = call.summary["usage"][output["model"]]
    assert usage["requests"] == 1
    assert usage["completion_tokens"] == 24
    assert usage["prompt_tokens"] == 12
    assert usage["total_tokens"] == 36

    inputs = call.inputs
    assert inputs["model"] == model
    assert inputs["messages"] == [{"role": "user", "content": "Hello!"}]
    assert inputs["max_tokens"] == 64
    assert inputs["temperature"] == 0.0
    assert inputs["top_p"] == 1


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
def test_chatnvidia_tool_call(client: weave.trace.weave_client.WeaveClient) -> None:
    api_key = os.environ.get("NVIDIA_API_KEY", "DUMMY_API_KEY")

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

    nvidia_client = ChatNVIDIA(
        api_key=api_key, model=model, temperature=0.0, max_tokens=64, top_p=1
    ).bind_tools(function_list)

    messages = [
        {
            "role": "user",
            "content": "Can you name a cricket player along with team name and highest score?",
        }
    ]

    response = nvidia_client.invoke(messages)

    calls = list(client.calls())
    # need to make 2 because of the langchain integration getting a call in there
    assert len(calls) == 2
    call = calls[1]

    assert response.content is not None

    assert (
        op_name_from_ref(call.op_name)
        == "langchain_nvidia_ai_endpoints.ChatNVIDIA-generate"
    )
    assert call.started_at is not None
    assert call.started_at < call.ended_at

    output = call.output
    assert output["model"] == model

    usage = call.summary["usage"][output["model"]]
    assert usage["requests"] == 1
    assert usage["completion_tokens"] == 30
    assert usage["prompt_tokens"] == 318
    assert usage["total_tokens"] == 348

    inputs = call.inputs
    assert inputs["model"] == model
    assert inputs["messages"] == [
        {
            "role": "user",
            "content": "Can you name a cricket player along with team name and highest score?",
        }
    ]
    assert inputs["max_tokens"] == 64
    assert inputs["temperature"] == 0.0
    assert inputs["top_p"] == 1


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
@pytest.mark.asyncio
async def test_chatnvidia_tool_call_async(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("NVIDIA_API_KEY", "DUMMY_API_KEY")

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

    nvidia_client = ChatNVIDIA(
        api_key=api_key, model=model, temperature=0.0, max_tokens=64, top_p=1
    ).bind_tools(function_list)

    messages = [
        {
            "role": "user",
            "content": "Can you name a cricket player along with team name and highest score?",
        }
    ]

    response = await nvidia_client.ainvoke(messages)

    calls = list(client.calls())
    # need to make 2 because of the langchain integration getting a call in there
    assert len(calls) == 2
    call = calls[1]

    assert response.content is not None

    assert (
        op_name_from_ref(call.op_name)
        == "langchain_nvidia_ai_endpoints.ChatNVIDIA-generate"
    )
    assert call.started_at is not None
    assert call.started_at < call.ended_at

    output = call.output
    assert output["model"] == model

    usage = call.summary["usage"][output["model"]]
    assert usage["requests"] == 1
    assert usage["completion_tokens"] == 30
    assert usage["prompt_tokens"] == 318
    assert usage["total_tokens"] == 348

    inputs = call.inputs
    assert inputs["model"] == model
    assert inputs["messages"] == [
        {
            "role": "user",
            "content": "Can you name a cricket player along with team name and highest score?",
        }
    ]
    assert inputs["max_tokens"] == 64
    assert inputs["temperature"] == 0.0
    assert inputs["top_p"] == 1


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
def test_chatnvidia_tool_call_stream(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("NVIDIA_API_KEY", "DUMMY_API_KEY")

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

    nvidia_client = ChatNVIDIA(
        api_key=api_key, model=model, temperature=0.0, max_tokens=64, top_p=1
    ).bind_tools(function_list)

    messages = [
        {
            "role": "user",
            "content": "Can you name a cricket player along with team name and highest score?",
        }
    ]

    response = nvidia_client.stream(messages)

    answer = AIMessageChunk(content="")
    for chunk in response:
        answer += chunk
        answer.usage_metadata = chunk.usage_metadata

    calls = list(client.calls())
    # need to make 2 because of the langchain integration getting a call in there
    assert len(calls) == 2
    call = calls[1]

    assert answer.tool_calls is not None

    assert (
        op_name_from_ref(call.op_name)
        == "langchain_nvidia_ai_endpoints.ChatNVIDIA-stream"
    )
    assert call.started_at is not None
    assert call.started_at < call.ended_at

    output = call.output
    assert output["model"] == model

    usage = call.summary["usage"][output["model"]]
    assert usage["requests"] == 1
    assert usage["completion_tokens"] == 30
    assert usage["prompt_tokens"] == 318
    assert usage["total_tokens"] == 348

    inputs = call.inputs
    assert inputs["model"] == model
    assert inputs["messages"] == [
        {
            "role": "user",
            "content": "Can you name a cricket player along with team name and highest score?",
        }
    ]
    assert inputs["max_tokens"] == 64
    assert inputs["temperature"] == 0.0
    assert inputs["top_p"] == 1


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization"], allowed_hosts=["api.wandb.ai", "localhost"]
)
@pytest.mark.asyncio
async def test_chatnvidia_tool_call_async_stream(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.environ.get("NVIDIA_API_KEY", "DUMMY_API_KEY")

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

    nvidia_client = ChatNVIDIA(
        api_key=api_key, model=model, temperature=0.0, max_tokens=64, top_p=1
    ).bind_tools(function_list)

    messages = [
        {
            "role": "user",
            "content": "Can you name a cricket player along with team name and highest score?",
        }
    ]

    response = nvidia_client.astream(messages)

    answer = AIMessageChunk(content="")
    async for chunk in response:
        answer += chunk
        answer.usage_metadata = chunk.usage_metadata

    calls = list(client.calls())
    # need to make 2 because of the langchain integration getting a call in there
    assert len(calls) == 2
    call = calls[1]

    assert answer.tool_calls is not None

    assert (
        op_name_from_ref(call.op_name)
        == "langchain_nvidia_ai_endpoints.ChatNVIDIA-stream"
    )
    assert call.started_at is not None
    assert call.started_at < call.ended_at

    output = call.output
    assert output["model"] == model

    usage = call.summary["usage"][output["model"]]
    assert usage["requests"] == 1
    assert usage["completion_tokens"] == 30
    assert usage["prompt_tokens"] == 318
    assert usage["total_tokens"] == 348

    inputs = call.inputs
    assert inputs["model"] == model
    assert inputs["messages"] == [
        {
            "role": "user",
            "content": "Can you name a cricket player along with team name and highest score?",
        }
    ]
    assert inputs["max_tokens"] == 64
    assert inputs["temperature"] == 0.0
    assert inputs["top_p"] == 1
