import pytest
from openai import AsyncOpenAI, OpenAI

from weave.integrations.integration_utilities import op_name_from_ref
from weave.trace.weave_client import WeaveClient


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_openai_quickstart(client: WeaveClient) -> None:
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
    assert output.model == "gpt-4o-2024-08-06"
    assert output.object == "response"
    assert isinstance(output.output[0].content[0].text, str)
    assert (
        output.output[0].content[0].text
        == "Under a moonlit sky, the gentle unicorn whispered dreams of stardust to sleepy children, guiding them to restful slumber."
    )

    usage = call.summary["usage"][output.model]  # type: ignore
    assert usage["requests"] == 1
    assert usage["input_tokens"] == 36
    assert usage["output_tokens"] == 27
    assert usage["total_tokens"] == 63
    assert usage["output_tokens_details"]["reasoning_tokens"] == 0
    assert usage["input_tokens_details"]["cached_tokens"] == 0

    inputs = call.inputs
    assert inputs["model"] == "gpt-4o-2024-08-06"
    assert inputs["input"] == "Write a one-sentence bedtime story about a unicorn."


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_openai_quickstart_stream(client: WeaveClient) -> None:
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
    assert output.model == "gpt-4o-2024-08-06"
    assert output.object == "response"
    assert isinstance(output.output[0].content[0].text, str)
    assert (
        output.output[0].content[0].text
        == "Under the shimmering glow of the moon, a gentle unicorn danced across a field of twinkling flowers, leaving trails of stardust as every dreamer peacefully drifted to sleep."
    )

    usage = call.summary["usage"][output.model]  # type: ignore
    assert usage["requests"] == 1
    assert usage["input_tokens"] == 36
    assert usage["output_tokens"] == 38
    assert usage["total_tokens"] == 74
    assert usage["output_tokens_details"]["reasoning_tokens"] == 0
    assert usage["input_tokens_details"]["cached_tokens"] == 0

    inputs = call.inputs
    assert inputs["model"] == "gpt-4o-2024-08-06"
    assert inputs["input"] == "Write a one-sentence bedtime story about a unicorn."


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_openai_quickstart_async(client: WeaveClient) -> None:
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
    assert output.model == "gpt-4o-2024-08-06"
    assert output.object == "response"
    assert isinstance(output.output[0].content[0].text, str)
    assert (
        output.output[0].content[0].text
        == "Under the twinkling starlit sky, Luna the unicorn gently sang lullabies to the moon, casting dreams of shimmering rainbows across the sleeping world."
    )

    usage = call.summary["usage"][output.model]  # type: ignore
    assert usage["requests"] == 1
    assert usage["input_tokens"] == 36
    assert usage["output_tokens"] == 33
    assert usage["total_tokens"] == 69
    assert usage["output_tokens_details"]["reasoning_tokens"] == 0
    assert usage["input_tokens_details"]["cached_tokens"] == 0

    inputs = call.inputs
    assert inputs["model"] == "gpt-4o-2024-08-06"
    assert inputs["input"] == "Write a one-sentence bedtime story about a unicorn."


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_openai_quickstart_async_stream(client: WeaveClient) -> None:
    oai = AsyncOpenAI()

    response = await oai.responses.create(
        model="gpt-4o-2024-08-06",
        input="Write a one-sentence bedtime story about a unicorn.",
        stream=True,
    )
    async for chunk in response:
        pass

    calls = client.get_calls()
    assert len(calls) == 1

    call = calls[0]
    assert op_name_from_ref(call.op_name) == "openai.responses.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    assert output.model == "gpt-4o-2024-08-06"
    assert output.object == "response"
    assert isinstance(output.output[0].content[0].text, str)
    assert (
        output.output[0].content[0].text
        == "Under the silver glow of the moon, a gentle unicorn softly treaded through the starlit meadow, where dreams blossomed like the flowers beneath her hooves."
    )

    usage = call.summary["usage"][output.model]  # type: ignore
    assert usage["requests"] == 1
    assert usage["input_tokens"] == 36
    assert usage["output_tokens"] == 34
    assert usage["total_tokens"] == 70
    assert usage["output_tokens_details"]["reasoning_tokens"] == 0
    assert usage["input_tokens_details"]["cached_tokens"] == 0

    inputs = call.inputs
    assert inputs["model"] == "gpt-4o-2024-08-06"
    assert inputs["input"] == "Write a one-sentence bedtime story about a unicorn."


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_openai_tool_calling(client: WeaveClient) -> None:
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
    print(f"{output=}")
    assert output.model == "gpt-4o-2024-08-06"
    assert output.object == "response"

    web_search_call = output.output[0]
    assert web_search_call.status == "completed"
    assert web_search_call.type == "web_search_call"

    response_output_message = output.output[1]
    search_results = response_output_message.content[0].annotations
    assert len(search_results) > 0

    tools = call.output.tools
    web_search_tool = tools[0]
    assert web_search_tool.type == "web_search_preview"
    assert web_search_tool.search_context_size == "medium"
    assert web_search_tool.user_location.type == "approximate"
    assert web_search_tool.user_location.country == "US"

    usage = call.summary["usage"][output.model]  # type: ignore
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


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_openai_tool_calling_stream(client: WeaveClient) -> None:
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
    print(f"{output=}")
    assert output.model == "gpt-4o-2024-08-06"
    assert output.object == "response"

    web_search_call = output.output[0]
    assert web_search_call.status == "completed"
    assert web_search_call.type == "web_search_call"

    response_output_message = output.output[1]
    search_results = response_output_message.content[0].annotations
    assert len(search_results) > 0

    tools = call.output.tools
    web_search_tool = tools[0]
    assert web_search_tool.type == "web_search_preview"
    assert web_search_tool.search_context_size == "medium"
    assert web_search_tool.user_location.type == "approximate"
    assert web_search_tool.user_location.country == "US"

    usage = call.summary["usage"][output.model]  # type: ignore
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


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_openai_tool_calling_async(client: WeaveClient) -> None:
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
    assert output.model == "gpt-4o-2024-08-06"
    assert output.object == "response"

    web_search_call = output.output[0]
    assert web_search_call.status == "completed"
    assert web_search_call.type == "web_search_call"

    response_output_message = output.output[1]
    search_results = response_output_message.content[0].annotations
    assert len(search_results) > 0

    tools = call.output.tools
    web_search_tool = tools[0]
    assert web_search_tool.type == "web_search_preview"
    assert web_search_tool.search_context_size == "medium"
    assert web_search_tool.user_location.type == "approximate"
    assert web_search_tool.user_location.country == "US"

    usage = call.summary["usage"][output.model]  # type: ignore
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


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_openai_tool_calling_async_stream(client: WeaveClient) -> None:
    oai = AsyncOpenAI()

    response = await oai.responses.create(
        model="gpt-4o-2024-08-06",
        tools=[{"type": "web_search_preview"}],
        input="What was a positive news story from today?",
        stream=True,
    )
    async for chunk in response:
        pass

    calls = client.get_calls()
    assert len(calls) == 1

    call = calls[0]
    assert op_name_from_ref(call.op_name) == "openai.responses.create"
    assert call.started_at is not None
    assert call.started_at < call.ended_at  # type: ignore

    output = call.output
    print(f"{output=}")
    assert output.model == "gpt-4o-2024-08-06"
    assert output.object == "response"

    web_search_call = output.output[0]
    assert web_search_call.status == "completed"
    assert web_search_call.type == "web_search_call"

    response_output_message = output.output[1]
    search_results = response_output_message.content[0].annotations
    assert len(search_results) > 0

    tools = call.output.tools
    web_search_tool = tools[0]
    assert web_search_tool.type == "web_search_preview"
    assert web_search_tool.search_context_size == "medium"
    assert web_search_tool.user_location.type == "approximate"
    assert web_search_tool.user_location.country == "US"

    usage = call.summary["usage"][output.model]  # type: ignore
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
