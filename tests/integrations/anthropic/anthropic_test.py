import os
from collections.abc import Generator
from unittest.mock import Mock

import httpx
import pytest
from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import Message, TextBlock, Usage
from pydantic import BaseModel

import weave
from weave.integrations.anthropic.anthropic_sdk import (
    anthropic_on_finish,
    get_anthropic_patcher,
)
from weave.integrations.integration_utilities import op_name_from_call
from weave.trace.call import Call

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


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
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
    # Integration-tracking metadata is stamped on every patched call.
    integration = call.attributes["integration"]
    assert integration["name"] == "anthropic"
    assert integration["version"]  # weave SDK version
    assert integration["meta"]["package_name"] == "anthropic"
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


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
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


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
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


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
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


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
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


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
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


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
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


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
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


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
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


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
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


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
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


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
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


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
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


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
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


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
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


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
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


# Prompt-cache responses report a net input_tokens next to separate
# cache_read_input_tokens / cache_creation_input_tokens counts. The summary's
# input_tokens must be the gross sum of the three (Weave's cost math subtracts
# the cache counts from it), while the raw response usage stays provider-native.
#
# The cache tests are recorded against the live API on a current model
# (claude-3-haiku-20240307 is retired). Caching needs a minimum prefix
# (4096 tokens on haiku 4.5), so the cacheable block repeats a fixed sentence
# well past that, and each test tags it with a unique marker so its first
# recorded call writes the cache and its second call reads it, independent of
# the other cache tests.
cache_model = "claude-haiku-4-5-20251001"
cache_filler = " ".join(
    ["Weave prices cached and uncached prompt tokens with separate counters."] * 400
)


def cache_messages(case: str) -> list[dict]:
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"[cache case: {case}] {cache_filler}",
                    "cache_control": {"type": "ephemeral"},
                },
                {"type": "text", "text": "Reply with the single word: ok"},
            ],
        }
    ]


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
)
def test_anthropic_cache_tokens(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY")
    anthropic_client = Anthropic(api_key=api_key)
    write = anthropic_client.messages.create(
        model=cache_model,
        max_tokens=32,
        messages=cache_messages("sync"),
    )
    read = anthropic_client.messages.create(
        model=cache_model,
        max_tokens=32,
        messages=cache_messages("sync"),
    )

    # The first recorded call wrote the cache, the second read the same prefix.
    assert write.usage.cache_creation_input_tokens > 0
    assert write.usage.cache_read_input_tokens == 0
    assert read.usage.cache_read_input_tokens == write.usage.cache_creation_input_tokens
    assert read.usage.cache_creation_input_tokens == 0

    calls = list(client.get_calls())
    assert len(calls) == 2
    for call, message in zip(calls, (write, read), strict=True):
        assert call.exception is None
        assert call.ended_at is not None
        output = call.output
        # The raw response usage stays net.
        assert output.usage.input_tokens == message.usage.input_tokens
        summary = call.summary
        assert summary is not None
        model_usage = summary["usage"][output.model]
        assert model_usage["requests"] == 1
        # input_tokens is gross: the net count plus both cache counts.
        assert (
            model_usage["input_tokens"]
            == message.usage.input_tokens
            + message.usage.cache_read_input_tokens
            + message.usage.cache_creation_input_tokens
        )
        assert (
            model_usage["cache_read_input_tokens"]
            == message.usage.cache_read_input_tokens
        )
        assert (
            model_usage["cache_creation_input_tokens"]
            == message.usage.cache_creation_input_tokens
        )


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
)
@pytest.mark.asyncio
async def test_async_anthropic_cache_tokens(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    anthropic_client = AsyncAnthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY"),
    )
    write = await anthropic_client.messages.create(
        model=cache_model,
        max_tokens=32,
        messages=cache_messages("async"),
    )
    read = await anthropic_client.messages.create(
        model=cache_model,
        max_tokens=32,
        messages=cache_messages("async"),
    )

    assert write.usage.cache_creation_input_tokens > 0
    assert write.usage.cache_read_input_tokens == 0
    assert read.usage.cache_read_input_tokens == write.usage.cache_creation_input_tokens
    assert read.usage.cache_creation_input_tokens == 0

    calls = list(client.get_calls())
    assert len(calls) == 2
    for call, message in zip(calls, (write, read), strict=True):
        assert call.exception is None
        assert call.ended_at is not None
        output = call.output
        assert output.usage.input_tokens == message.usage.input_tokens
        summary = call.summary
        assert summary is not None
        model_usage = summary["usage"][output.model]
        assert model_usage["requests"] == 1
        assert (
            model_usage["input_tokens"]
            == message.usage.input_tokens
            + message.usage.cache_read_input_tokens
            + message.usage.cache_creation_input_tokens
        )
        assert (
            model_usage["cache_read_input_tokens"]
            == message.usage.cache_read_input_tokens
        )
        assert (
            model_usage["cache_creation_input_tokens"]
            == message.usage.cache_creation_input_tokens
        )


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
)
def test_anthropic_stream_cache_tokens(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY")
    anthropic_client = Anthropic(api_key=api_key)
    for _ in range(2):
        stream = anthropic_client.messages.create(
            model=cache_model,
            stream=True,
            max_tokens=32,
            messages=cache_messages("stream"),
        )
        for _event in stream:
            pass

    calls = list(client.get_calls())
    assert len(calls) == 2
    write_usage = calls[0].output.usage
    read_usage = calls[1].output.usage
    # The accumulated messages keep the net input and both cache counts:
    # the first recorded stream wrote the cache, the second read it.
    assert write_usage.cache_creation_input_tokens > 0
    assert write_usage.cache_read_input_tokens == 0
    assert read_usage.cache_read_input_tokens == write_usage.cache_creation_input_tokens
    assert read_usage.cache_creation_input_tokens == 0

    for call in calls:
        assert call.exception is None
        assert call.ended_at is not None
        usage = call.output.usage
        summary = call.summary
        assert summary is not None
        model_usage = summary["usage"][call.output.model]
        assert model_usage["requests"] == 1
        assert (
            model_usage["input_tokens"]
            == usage.input_tokens
            + usage.cache_read_input_tokens
            + usage.cache_creation_input_tokens
        )
        assert model_usage["cache_read_input_tokens"] == usage.cache_read_input_tokens
        assert (
            model_usage["cache_creation_input_tokens"]
            == usage.cache_creation_input_tokens
        )


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
)
def test_anthropic_messages_stream_ctx_manager_cache_tokens(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY")
    anthropic_client = Anthropic(api_key=api_key)
    for _ in range(2):
        with anthropic_client.messages.stream(
            max_tokens=32,
            messages=cache_messages("ctx"),
            model=cache_model,
        ) as stream:
            for _event in stream:
                pass

    calls = list(client.get_calls())
    assert len(calls) == 2
    write_usage = calls[0].output.usage
    read_usage = calls[1].output.usage
    assert write_usage.cache_creation_input_tokens > 0
    assert write_usage.cache_read_input_tokens == 0
    assert read_usage.cache_read_input_tokens == write_usage.cache_creation_input_tokens
    assert read_usage.cache_creation_input_tokens == 0

    for call in calls:
        assert call.exception is None
        assert call.ended_at is not None
        usage = call.output.usage
        summary = call.summary
        assert summary is not None
        model_usage = summary["usage"][call.output.model]
        assert model_usage["requests"] == 1
        assert (
            model_usage["input_tokens"]
            == usage.input_tokens
            + usage.cache_read_input_tokens
            + usage.cache_creation_input_tokens
        )
        assert model_usage["cache_read_input_tokens"] == usage.cache_read_input_tokens
        assert (
            model_usage["cache_creation_input_tokens"]
            == usage.cache_creation_input_tokens
        )


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
)
def test_anthropic_messages_stream_ctx_manager_abandoned(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    """A stream abandoned before message_stop must still log the call cleanly."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY")
    anthropic_client = Anthropic(api_key=api_key)
    first_event = None
    with anthropic_client.messages.stream(
        max_tokens=32,
        messages=cache_messages("abandoned"),
        model=cache_model,
    ) as stream:
        for event in stream:
            first_event = event
            break

    assert first_event is not None
    assert first_event.type == "message_start"
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]
    assert call.exception is None
    assert call.ended_at is not None
    # No final message was accumulated, so there is no usage to record.
    assert call.output == ""
    assert call.summary.get("usage") is None


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
)
def test_anthropic_create_with_traced_call_in_response_hook(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    """A traced call made from an httpx response hook runs inside the patched
    create and becomes its child; the child-rollup summary must not be
    rewritten with the outer response's own usage.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY")
    inner_client = Anthropic(api_key=api_key)

    def call_anthropic_from_hook(response: httpx.Response) -> None:
        inner_client.messages.create(
            model=cache_model,
            max_tokens=32,
            messages=[{"role": "user", "content": "Hello, Claude"}],
        )

    outer_client = Anthropic(
        api_key=api_key,
        http_client=httpx.Client(event_hooks={"response": [call_anthropic_from_hook]}),
    )
    message = outer_client.messages.create(
        model=cache_model,
        max_tokens=32,
        messages=cache_messages("hook"),
    )

    # The outer response has real cache activity of its own.
    assert message.usage.cache_creation_input_tokens > 0
    calls = list(client.get_calls())
    assert len(calls) == 2
    outer, inner = calls
    assert inner.parent_id == outer.id
    assert outer.exception is None
    assert outer.ended_at is not None
    inner_raw = inner.output.usage
    # The outer summary is the child rollup; the outer response's own gross
    # count must not overwrite the child's counts.
    outer_usage = outer.summary["usage"][inner.output.model]
    assert outer_usage["requests"] == 1
    assert outer_usage["input_tokens"] == inner_raw.input_tokens
    assert outer_usage["output_tokens"] == inner_raw.output_tokens
    inner_usage = inner.summary["usage"][inner.output.model]
    assert inner_usage["input_tokens"] == inner_raw.input_tokens
    assert inner_usage["output_tokens"] == inner_raw.output_tokens


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
)
def test_anthropic_cache_tokens_zero(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    """A cache_control block below the minimum cacheable length is processed
    without caching and reports both cache counts as 0.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY")
    anthropic_client = Anthropic(api_key=api_key)
    message = anthropic_client.messages.create(
        model=cache_model,
        max_tokens=32,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Hello, cached Claude",
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ],
    )

    assert message.usage.cache_creation_input_tokens == 0
    assert message.usage.cache_read_input_tokens == 0
    calls = list(client.get_calls())
    assert len(calls) == 1
    call = calls[0]
    assert call.exception is None
    assert call.ended_at is not None
    output = call.output
    summary = call.summary
    assert summary is not None
    model_usage = summary["usage"][output.model]
    # Zero cache counts add nothing: input_tokens stays at the net count.
    assert model_usage["input_tokens"] == message.usage.input_tokens
    assert model_usage["cache_read_input_tokens"] == 0
    assert model_usage["cache_creation_input_tokens"] == 0


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
)
def test_beta_anthropic_cache_tokens(
    client: weave.trace.weave_client.WeaveClient,
) -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY", "DUMMY_API_KEY")
    anthropic_client = Anthropic(api_key=api_key)
    write = anthropic_client.beta.messages.create(
        model=cache_model,
        max_tokens=32,
        messages=cache_messages("beta"),
    )
    read = anthropic_client.beta.messages.create(
        model=cache_model,
        max_tokens=32,
        messages=cache_messages("beta"),
    )

    assert write.usage.cache_creation_input_tokens > 0
    assert write.usage.cache_read_input_tokens == 0
    assert read.usage.cache_read_input_tokens == write.usage.cache_creation_input_tokens
    assert read.usage.cache_creation_input_tokens == 0

    calls = list(client.get_calls())
    assert len(calls) == 2
    for call, message in zip(calls, (write, read), strict=True):
        assert call.exception is None
        assert call.ended_at is not None
        output = call.output
        assert output.usage.input_tokens == message.usage.input_tokens
        summary = call.summary
        assert summary is not None
        model_usage = summary["usage"][output.model]
        assert model_usage["requests"] == 1
        assert (
            model_usage["input_tokens"]
            == message.usage.input_tokens
            + message.usage.cache_read_input_tokens
            + message.usage.cache_creation_input_tokens
        )
        assert (
            model_usage["cache_read_input_tokens"]
            == message.usage.cache_read_input_tokens
        )
        assert (
            model_usage["cache_creation_input_tokens"]
            == message.usage.cache_creation_input_tokens
        )


def test_anthropic_on_finish_recomputes_gross_input_from_raw_usage() -> None:
    output = Message(
        id="msg_1",
        type="message",
        role="assistant",
        model=model,
        content=[TextBlock(type="text", text="hi")],
        stop_reason="end_turn",
        stop_sequence=None,
        usage=Usage(
            input_tokens=100,
            output_tokens=20,
            cache_read_input_tokens=80,
            cache_creation_input_tokens=15,
        ),
    )
    call = Mock(spec=Call)
    call._children = []
    call.summary = {
        "usage": {
            model: {
                "requests": 1,
                "input_tokens": 100,
                "output_tokens": 20,
                "cache_read_input_tokens": 80,
                "cache_creation_input_tokens": 15,
            }
        }
    }

    anthropic_on_finish(call, output, None)

    model_usage = call.summary["usage"][model]
    assert model_usage["input_tokens"] == 195
    assert output.usage.input_tokens == 100
    # A second run recomputes from the raw usage instead of compounding.
    anthropic_on_finish(call, output, None)
    assert model_usage["input_tokens"] == 195


def test_anthropic_on_finish_without_cache_counts_keeps_net_input() -> None:
    # Cache fields reported as None count as 0.
    output = Message(
        id="msg_1",
        type="message",
        role="assistant",
        model=model,
        content=[TextBlock(type="text", text="hi")],
        stop_reason="end_turn",
        stop_sequence=None,
        usage=Usage(input_tokens=10, output_tokens=5),
    )
    call = Mock(spec=Call)
    call._children = []
    call.summary = {
        "usage": {model: {"requests": 1, "input_tokens": 10, "output_tokens": 5}}
    }

    anthropic_on_finish(call, output, None)

    assert call.summary == {
        "usage": {model: {"requests": 1, "input_tokens": 10, "output_tokens": 5}}
    }

    # Older anthropic SDKs predate the cache fields entirely (attributes absent).
    old_sdk_output = Mock()
    old_sdk_output.model = model
    old_sdk_output.usage = Mock(spec=["input_tokens"])
    old_sdk_output.usage.input_tokens = 10
    anthropic_on_finish(call, old_sdk_output, None)

    assert call.summary == {
        "usage": {model: {"requests": 1, "input_tokens": 10, "output_tokens": 5}}
    }


def test_anthropic_on_finish_ignores_unexpected_shapes() -> None:
    call = Mock(spec=Call)
    call._children = []
    call.summary = {"usage": {model: {"requests": 1, "input_tokens": 7}}}

    # A stream that never produced a final message accumulates to "".
    anthropic_on_finish(call, "", None)
    # A non-string model cannot be a summary usage key ({} is unhashable).
    non_string_model = Mock()
    non_string_model.model = {}
    non_string_model.usage = Usage(input_tokens=1, output_tokens=1)
    anthropic_on_finish(call, non_string_model, None)
    # A non-integer input count is left alone.
    non_int_input = Mock()
    non_int_input.model = model
    non_int_input.usage = Mock(
        input_tokens="100",
        cache_read_input_tokens=80,
        cache_creation_input_tokens=15,
    )
    anthropic_on_finish(call, non_int_input, None)
    # A non-integer cache count next to a valid input count is left alone too.
    non_int_cache = Mock()
    non_int_cache.model = model
    non_int_cache.usage = Mock(
        input_tokens=100,
        cache_read_input_tokens="80",
        cache_creation_input_tokens=15,
    )
    anthropic_on_finish(call, non_int_cache, None)
    assert call.summary == {"usage": {model: {"requests": 1, "input_tokens": 7}}}

    output = Message(
        id="msg_1",
        type="message",
        role="assistant",
        model=model,
        content=[TextBlock(type="text", text="hi")],
        stop_reason="end_turn",
        stop_sequence=None,
        usage=Usage(input_tokens=1, output_tokens=1),
    )
    # A non-dict usage map (user-mutated summary) is left alone.
    call.summary = {"usage": []}
    anthropic_on_finish(call, output, None)
    assert call.summary == {"usage": []}
    # No summary entry for the model and no summary at all are both no-ops.
    call.summary = {"usage": {}}
    anthropic_on_finish(call, output, None)
    assert call.summary == {"usage": {}}
    call.summary = None
    anthropic_on_finish(call, output, None)  # must not raise


def test_anthropic_on_finish_skips_child_rollup_summaries() -> None:
    # A traced op invoked from an httpx event hook runs inside the patched
    # create, so the anthropic call can have children; finish_call then builds
    # the summary from the child rollup and this response's usage has no entry
    # of its own to rewrite.
    output = Message(
        id="msg_1",
        type="message",
        role="assistant",
        model=model,
        content=[TextBlock(type="text", text="hi")],
        stop_reason="end_turn",
        stop_sequence=None,
        usage=Usage(
            input_tokens=10,
            output_tokens=1,
            cache_read_input_tokens=80,
            cache_creation_input_tokens=15,
        ),
    )
    call = Mock(spec=Call)
    call._children = [Mock(spec=Call)]
    call.summary = {
        "usage": {model: {"requests": 1, "input_tokens": 500, "output_tokens": 50}}
    }

    anthropic_on_finish(call, output, None)

    assert call.summary == {
        "usage": {model: {"requests": 1, "input_tokens": 500, "output_tokens": 50}}
    }
