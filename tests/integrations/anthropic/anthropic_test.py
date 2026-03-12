import os
from collections.abc import Generator

import pytest
from anthropic import Anthropic, AsyncAnthropic
from pydantic import BaseModel

import weave
from weave.integrations.anthropic.anthropic_sdk import get_anthropic_patcher
from weave.integrations.integration_utilities import op_name_from_call

model = "claude-3-haiku-20240307"
parse_model = "claude-sonnet-4-5"
# model = "claude-3-opus-20240229"


@pytest.fixture(autouse=True)
def patch_anthropic() -> Generator[None, None, None]:
    """Patch Anthropic for all tests in this file."""
    patcher = get_anthropic_patcher()
    patcher.attempt_patch()
    yield
    patcher.undo_patch()


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_anthropic(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY")
    anthropic_client = Anthropic(api_key=api_key)
    message = anthropic_client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello, Claude"}],
    )

    all_content = message.content[0]
    exp = "Hello! It's nice to meet you. How can I assist you today?"
    assert all_content.text == exp
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]
    assert call.exception is None
    assert call.ended_at is not None
    output = call.output
    assert output.id == message.id
    assert output.model == message.model
    assert output.stop_reason == "end_turn"
    assert output.stop_sequence is None
    assert output.content[0].text == exp
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.output_tokens == model_usage["output_tokens"] == 19
    assert output.usage.input_tokens == model_usage["input_tokens"] == 10


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_anthropic_stream(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY")
    anthropic_client = Anthropic(api_key=api_key)
    stream = anthropic_client.messages.create(
        model=model,
        stream=True,
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello, Claude"}],
    )
    all_content = ""
    for event in stream:
        if event.type == "message_start":
            message = event.message
            input_tokens = event.message.usage.input_tokens
        if event.type == "content_block_delta":
            all_content += event.delta.text
        if event.type == "message_delta":
            output_tokens = event.usage.output_tokens
    exp = "Hello there! How can I assist you today?"
    assert all_content == exp
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None
    assert call.ended_at is not None
    output = call.output
    assert output.id == message.id
    assert output.model == message.model
    assert output.stop_reason == "end_turn"
    assert output.stop_sequence is None
    assert output.content[0].text == exp
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.output_tokens == output_tokens == 13
    assert output.usage.input_tokens == input_tokens == 10


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_async_anthropic(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    anthropic_client = AsyncAnthropic(
        # This is the default and can be omitted
        api_key=os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY"),
    )

    message = await anthropic_client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello, Claude"}],
    )
    all_content = message.content[0]
    exp = "Hello! It's nice to meet you. How can I assist you today?"
    assert all_content.text == exp
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None
    assert call.ended_at is not None
    output = call.output
    assert output.id == message.id
    assert output.model == message.model
    assert output.stop_reason == "end_turn"
    assert output.stop_sequence is None
    assert output.content[0].text == exp
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.output_tokens == model_usage["output_tokens"] == 19
    assert output.usage.input_tokens == model_usage["input_tokens"] == 10


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_async_anthropic_stream(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    anthropic_client = AsyncAnthropic(
        # This is the default and can be omitted
        api_key=os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY"),
    )

    stream = await anthropic_client.messages.create(
        model=model,
        stream=True,
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello, Claude"}],
    )
    all_content = ""
    async for event in stream:
        if event.type == "message_start":
            message = event.message
            input_tokens = event.message.usage.input_tokens
        if event.type == "content_block_delta":
            all_content += event.delta.text
        if event.type == "message_delta":
            output_tokens = event.usage.output_tokens
    exp = "Hello! It's nice to meet you. How can I assist you today?"
    assert all_content == exp
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None
    assert call.ended_at is not None
    output = call.output
    assert output.id == message.id
    assert output.model == message.model
    assert output.stop_reason == "end_turn"
    assert output.stop_sequence is None
    assert output.content[0].text == exp
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.output_tokens == output_tokens == 19
    assert output.usage.input_tokens == input_tokens == 10


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_tools_calling(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY")
    anthropic_client = Anthropic(api_key=api_key)
    message = anthropic_client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": "What's the weather like in San Francisco?",
            }
        ],
        tools=[
            {
                "name": "get_weather",
                "description": "Get the current weather in a given location",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA",
                        }
                    },
                    "required": ["location"],
                },
            },
        ],
    )
    exp = "San Francisco, CA"
    all_content = message.content[0]
    assert all_content.input["location"] == exp
    assert all_content.type == "tool_use"
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None
    assert call.ended_at is not None
    output = call.output
    assert output.id == message.id
    assert output.model == message.model
    assert output.stop_reason == "tool_use"
    assert output.stop_sequence is None
    assert output.content[0].input["location"] == exp
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.output_tokens == model_usage["output_tokens"] == 56
    assert output.usage.input_tokens == model_usage["input_tokens"] == 354


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_anthropic_messages_stream_ctx_manager(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY")
    anthropic_client = Anthropic(api_key=api_key)

    all_content = ""
    with anthropic_client.messages.stream(
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": "Say hello there!",
            }
        ],
        model=model,
    ) as stream:
        for event in stream:
            if event.type == "text":
                all_content += event.text

    exp = "Hello there!"
    assert all_content.strip() == exp
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None
    assert call.ended_at is not None
    output = call.output
    assert output.model == model
    assert output.stop_reason == "end_turn"
    assert output.stop_sequence is None
    assert output.content[0].text.strip() == exp
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.output_tokens == model_usage["output_tokens"]
    assert output.usage.input_tokens == model_usage["input_tokens"]


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_async_anthropic_messages_stream_ctx_manager(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    anthropic_client = AsyncAnthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY"),
    )

    all_content = ""
    async with anthropic_client.messages.stream(
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": "Say hello there!",
            }
        ],
        model=model,
    ) as stream:
        async for event in stream:
            if event.type == "text":
                all_content += event.text

    exp = "Hello there!"
    assert all_content.strip() == exp

    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None
    assert call.ended_at is not None
    output = call.output
    assert output.model == model
    assert output.stop_reason == "end_turn"
    assert output.stop_sequence is None
    assert output.content[0].text.strip() == exp
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.output_tokens == model_usage["output_tokens"]
    assert output.usage.input_tokens == model_usage["input_tokens"]


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_anthropic_messages_stream_get_final_message(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY")
    anthropic_client = Anthropic(api_key=api_key)

    with anthropic_client.messages.stream(
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": "Say hello there!",
            }
        ],
        model=model,
    ) as stream:
        message = stream.get_final_message()

    exp = "Hello there!"
    assert message.content[0].text.strip() == exp
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None
    assert call.ended_at is not None
    output = call.output
    assert output.model == model
    assert output.stop_reason == "end_turn"
    assert output.content[0].text.strip() == exp
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.output_tokens == model_usage["output_tokens"]
    assert output.usage.input_tokens == model_usage["input_tokens"]


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_async_anthropic_messages_stream_get_final_message(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    anthropic_client = AsyncAnthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY"),
    )

    async with anthropic_client.messages.stream(
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": "Say hello there!",
            }
        ],
        model=model,
    ) as stream:
        message = await stream.get_final_message()

    exp = "Hello there!"
    assert message.content[0].text.strip() == exp

    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None
    assert call.ended_at is not None
    output = call.output
    assert output.model == model
    assert output.stop_reason == "end_turn"
    assert output.content[0].text.strip() == exp
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.output_tokens == model_usage["output_tokens"]
    assert output.usage.input_tokens == model_usage["input_tokens"]


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_anthropic_messages_stream_ctx_manager_text(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY")
    anthropic_client = Anthropic(api_key=api_key)

    all_content = ""
    with anthropic_client.messages.stream(
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": "Say hello there!",
            }
        ],
        model=model,
    ) as stream:
        for text in stream.text_stream:
            all_content += text

    exp = "Hello there!"
    assert all_content.strip() == exp
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None
    assert call.ended_at is not None
    output = call.output
    assert output.model == model
    assert output.stop_reason == "end_turn"
    assert output.stop_sequence is None
    assert output.content[0].text.strip() == exp
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.output_tokens == model_usage["output_tokens"]
    assert output.usage.input_tokens == model_usage["input_tokens"]


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_async_anthropic_messages_stream_ctx_manager_text(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    anthropic_client = AsyncAnthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY"),
    )

    all_content = ""
    async with anthropic_client.messages.stream(
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": "Say hello there!",
            }
        ],
        model=model,
    ) as stream:
        async for text in stream.text_stream:
            all_content += text

    exp = "Hello there!"
    assert all_content.strip() == exp

    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None
    assert call.ended_at is not None
    output = call.output
    assert output.model == model
    assert output.stop_reason == "end_turn"
    assert output.stop_sequence is None
    assert output.content[0].text.strip() == exp
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.output_tokens == model_usage["output_tokens"]
    assert output.usage.input_tokens == model_usage["input_tokens"]


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_beta_anthropic(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY")
    anthropic_client = Anthropic(api_key=api_key)
    message = anthropic_client.beta.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello, Claude"}],
    )

    all_content = message.content[0]
    exp = "Hello! It's nice to meet you. How can I assist you today?"
    assert all_content.text == exp
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]
    assert call.exception is None
    assert call.ended_at is not None
    output = call.output
    assert output.id == message.id
    assert output.model == message.model
    assert output.stop_reason == "end_turn"
    assert output.stop_sequence is None
    assert output.content[0].text == exp
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.output_tokens == model_usage["output_tokens"] == 19
    assert output.usage.input_tokens == model_usage["input_tokens"] == 10


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_beta_anthropic_parse(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    class Greeting(BaseModel):
        greeting: str

    api_key = os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY")
    anthropic_client = Anthropic(api_key=api_key)
    message = anthropic_client.beta.messages.parse(
        model=parse_model,
        max_tokens=128,
        messages=[
            {
                "role": "user",
                "content": 'Return JSON: {"greeting":"hello"}',
            }
        ],
        output_format=Greeting,
        temperature=0,
    )

    all_content = message.content[0]
    assert all_content.parsed_output == Greeting(greeting="hello")
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]
    assert op_name_from_call(call) == "anthropic.beta.Messages.parse"
    assert call.exception is None
    assert call.ended_at is not None
    output = call.output
    assert output.id == message.id
    assert output.model == message.model
    assert output.content[0].parsed_output == Greeting(greeting="hello")
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.output_tokens == model_usage["output_tokens"]
    assert output.usage.input_tokens == model_usage["input_tokens"]


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
def test_beta_anthropic_stream(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY")
    anthropic_client = Anthropic(api_key=api_key)
    stream = anthropic_client.beta.messages.create(
        model=model,
        stream=True,
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello, Claude"}],
    )
    all_content = ""
    for event in stream:
        if event.type == "message_start":
            message = event.message
            input_tokens = event.message.usage.input_tokens
        if event.type == "content_block_delta":
            all_content += event.delta.text
        if event.type == "message_delta":
            output_tokens = event.usage.output_tokens
    exp = "Hello! How can I assist you today?"
    assert all_content == exp
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None
    assert call.ended_at is not None
    output = call.output
    assert output.id == message.id
    assert output.model == message.model
    assert output.stop_reason == "end_turn"
    assert output.stop_sequence is None
    assert output.content[0].text == exp
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.output_tokens == output_tokens == 12
    assert output.usage.input_tokens == input_tokens == 10


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_beta_async_anthropic(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    anthropic_client = AsyncAnthropic(
        # This is the default and can be omitted
        api_key=os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY"),
    )

    message = await anthropic_client.beta.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello, Claude"}],
    )
    all_content = message.content[0]
    exp = "Hello! How can I assist you today?"
    assert all_content.text == exp
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None
    assert call.ended_at is not None
    output = call.output
    assert output.id == message.id
    assert output.model == message.model
    assert output.stop_reason == "end_turn"
    assert output.stop_sequence is None
    assert output.content[0].text == exp
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.output_tokens == model_usage["output_tokens"] == 12
    assert output.usage.input_tokens == model_usage["input_tokens"] == 10


@pytest.mark.skip_clickhouse_client  # TODO:VCR recording does not seem to allow us to make requests to the clickhouse db in non-recording mode
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost"],
)
@pytest.mark.asyncio
async def test_beta_async_anthropic_stream(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    anthropic_client = AsyncAnthropic(
        # This is the default and can be omitted
        api_key=os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY"),
    )

    stream = await anthropic_client.beta.messages.create(
        model=model,
        stream=True,
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello, Claude"}],
    )
    all_content = ""
    async for event in stream:
        if event.type == "message_start":
            message = event.message
            input_tokens = event.message.usage.input_tokens
        if event.type == "content_block_delta":
            all_content += event.delta.text
        if event.type == "message_delta":
            output_tokens = event.usage.output_tokens
    exp = "Hello! How can I assist you today?"
    assert all_content == exp
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]

    assert call.exception is None
    assert call.ended_at is not None
    output = call.output
    assert output.id == message.id
    assert output.model == message.model
    assert output.stop_reason == "end_turn"
    assert output.stop_sequence is None
    assert output.content[0].text == exp
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    assert model_usage["requests"] == 1
    assert output.usage.output_tokens == output_tokens == 12
    assert output.usage.input_tokens == input_tokens == 10
