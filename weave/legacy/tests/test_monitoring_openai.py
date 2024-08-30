import contextlib
import os
from unittest.mock import Mock

import openai
import pytest
import pytest_asyncio
from openai import AsyncStream, Stream
from openai.types.chat.chat_completion import ChatCompletion, Choice
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk, ChoiceDelta
from openai.types.chat.chat_completion_chunk import Choice as ChunkChoice
from openai.types.completion_usage import CompletionUsage

import weave
from weave.legacy.weave.monitoring import init_monitor
from weave.legacy.weave.monitoring.openai import util
from weave.legacy.weave.monitoring.openai.models import *
from weave.legacy.weave.monitoring.openai.models import Context
from weave.legacy.weave.monitoring.openai.openai import patch, unpatch
from weave.legacy.weave.monitoring.openai.util import Context
from weave.legacy.weave.wandb_interface.wandb_stream_table import StreamTable


@pytest.fixture
def chat_completion_request_message():
    return [
        ChatCompletionRequestMessage(
            content="Tell me a joke", role="system", function_call=None, tool_calls=None
        )
    ]


@pytest.fixture
def streaming_chat_completion_messages():
    return [
        ChatCompletionChunk(
            id="chatcmpl-blank",
            choices=[
                ChunkChoice(
                    delta=ChoiceDelta(
                        content="",
                        function_call=None,
                        role="assistant",
                        tool_calls=None,
                    ),
                    finish_reason=None,
                    index=0,
                )
            ],
            created=1700686161,
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        ),
        ChatCompletionChunk(
            id="chatcmpl-blank",
            choices=[
                ChunkChoice(
                    delta=ChoiceDelta(
                        content="Why", function_call=None, role=None, tool_calls=None
                    ),
                    finish_reason=None,
                    index=0,
                )
            ],
            created=1700686161,
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        ),
        ChatCompletionChunk(
            id="chatcmpl-blank",
            choices=[
                ChunkChoice(
                    delta=ChoiceDelta(
                        content=" don", function_call=None, role=None, tool_calls=None
                    ),
                    finish_reason=None,
                    index=0,
                )
            ],
            created=1700686161,
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        ),
        ChatCompletionChunk(
            id="chatcmpl-blank",
            choices=[
                ChunkChoice(
                    delta=ChoiceDelta(
                        content="'t", function_call=None, role=None, tool_calls=None
                    ),
                    finish_reason=None,
                    index=0,
                )
            ],
            created=1700686161,
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        ),
        ChatCompletionChunk(
            id="chatcmpl-blank",
            choices=[
                ChunkChoice(
                    delta=ChoiceDelta(
                        content=" scientists",
                        function_call=None,
                        role=None,
                        tool_calls=None,
                    ),
                    finish_reason=None,
                    index=0,
                )
            ],
            created=1700686161,
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        ),
        ChatCompletionChunk(
            id="chatcmpl-blank",
            choices=[
                ChunkChoice(
                    delta=ChoiceDelta(
                        content=" trust", function_call=None, role=None, tool_calls=None
                    ),
                    finish_reason=None,
                    index=0,
                )
            ],
            created=1700686161,
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        ),
        ChatCompletionChunk(
            id="chatcmpl-blank",
            choices=[
                ChunkChoice(
                    delta=ChoiceDelta(
                        content=" atoms", function_call=None, role=None, tool_calls=None
                    ),
                    finish_reason=None,
                    index=0,
                )
            ],
            created=1700686161,
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        ),
        ChatCompletionChunk(
            id="chatcmpl-blank",
            choices=[
                ChunkChoice(
                    delta=ChoiceDelta(
                        content="?\n\n", function_call=None, role=None, tool_calls=None
                    ),
                    finish_reason=None,
                    index=0,
                )
            ],
            created=1700686161,
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        ),
        ChatCompletionChunk(
            id="chatcmpl-blank",
            choices=[
                ChunkChoice(
                    delta=ChoiceDelta(
                        content="Because",
                        function_call=None,
                        role=None,
                        tool_calls=None,
                    ),
                    finish_reason=None,
                    index=0,
                )
            ],
            created=1700686161,
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        ),
        ChatCompletionChunk(
            id="chatcmpl-blank",
            choices=[
                ChunkChoice(
                    delta=ChoiceDelta(
                        content=" they", function_call=None, role=None, tool_calls=None
                    ),
                    finish_reason=None,
                    index=0,
                )
            ],
            created=1700686161,
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        ),
        ChatCompletionChunk(
            id="chatcmpl-blank",
            choices=[
                ChunkChoice(
                    delta=ChoiceDelta(
                        content=" make", function_call=None, role=None, tool_calls=None
                    ),
                    finish_reason=None,
                    index=0,
                )
            ],
            created=1700686161,
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        ),
        ChatCompletionChunk(
            id="chatcmpl-blank",
            choices=[
                ChunkChoice(
                    delta=ChoiceDelta(
                        content=" up", function_call=None, role=None, tool_calls=None
                    ),
                    finish_reason=None,
                    index=0,
                )
            ],
            created=1700686161,
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        ),
        ChatCompletionChunk(
            id="chatcmpl-blank",
            choices=[
                ChunkChoice(
                    delta=ChoiceDelta(
                        content=" everything",
                        function_call=None,
                        role=None,
                        tool_calls=None,
                    ),
                    finish_reason=None,
                    index=0,
                )
            ],
            created=1700686161,
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        ),
        ChatCompletionChunk(
            id="chatcmpl-blank",
            choices=[
                ChunkChoice(
                    delta=ChoiceDelta(
                        content="!", function_call=None, role=None, tool_calls=None
                    ),
                    finish_reason=None,
                    index=0,
                )
            ],
            created=1700686161,
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        ),
        ChatCompletionChunk(
            id="chatcmpl-blank",
            choices=[
                ChunkChoice(
                    delta=ChoiceDelta(
                        content=None, function_call=None, role=None, tool_calls=None
                    ),
                    finish_reason="stop",
                    index=0,
                )
            ],
            created=1700686161,
            model="gpt-3.5-turbo-0613",
            object="chat.completion.chunk",
        ),
    ]


class MockAsyncResponse:
    """This emulates an SSE response"""

    def __init__(self, chunks: List):
        self._chunks = iter(chunks)

    async def aiter_lines(self):
        i = 0
        for chunk in self._chunks:
            i += 1
            yield f"data: {chunk.model_dump_json()}\n"
            yield "\n"
        yield "data: [DONE]\n"
        yield "\n"

    async def aiter_bytes(self):
        async for line in self.aiter_lines():
            yield line.encode("utf-8")


class MockAsyncStream(AsyncStream):
    def __init__(self, chunks: List):
        self._chunks = iter(chunks)

        def process_response_data(*, data: object, **kwargs):
            return ChatCompletionChunk.model_validate(data)

        def make_sse_decoder():
            from openai._streaming import SSEDecoder

            return SSEDecoder()

        super().__init__(
            cast_to=ChatCompletionChunk,
            client=Mock(
                _process_response_data=process_response_data,
                _make_sse_decoder=make_sse_decoder,
            ),
            response=MockAsyncResponse(chunks),
        )


@pytest.fixture
def async_streaming_chat_completion_messages(streaming_chat_completion_messages):
    return MockAsyncStream(streaming_chat_completion_messages)


@pytest.fixture
def reassembled_chat_completion_message():
    return ChatCompletion(
        id="chatcmpl-blank",
        choices=[
            Choice(
                # logprobs included here because latest versions of pydantic
                # require optional fields without default values to be included
                # in the constructor
                logprobs=None,
                finish_reason="stop",
                index=0,
                message=ChatCompletionMessage(
                    content="Why don't scientists trust atoms?\n\nBecause they make up everything!",
                    role="assistant",
                    tool_calls=None,
                ),
            )
        ],
        created=1700686161,
        model="gpt-3.5-turbo-0613",
        object="chat.completion",
        usage=CompletionUsage(completion_tokens=19, prompt_tokens=10, total_tokens=29),
    )


@pytest.fixture
def openai_client():
    c = Mock(spec=openai.OpenAI)
    c.chat = Mock()
    c.chat.completions = Mock()
    c.chat.completions.create = Mock()
    return c


@pytest.fixture
def streaming_client(openai_client, streaming_chat_completion_messages):
    openai_client.chat.completions.create.return_value = iter(
        streaming_chat_completion_messages
    )
    return openai_client


@pytest.fixture
def teardown():
    yield
    unpatch()


class MockSyncResponse:
    """This emulates a synchronous SSE response"""

    def __init__(self, chunks: List):
        self._chunks = iter(chunks)

    def iter_lines(self):
        i = 0
        for chunk in self._chunks:
            i += 1
            yield f"data: {chunk.model_dump_json()}\n"
            yield "\n"
        yield "data: [DONE]\n"
        yield "\n"

    def iter_bytes(self):
        for line in self.iter_lines():
            yield line.encode("utf-8")


class MockStream(Stream):
    def __init__(self, chunks: List):
        self._chunks = iter(chunks)

        def process_response_data(*, data: object, **kwargs):
            return ChatCompletionChunk.model_validate(data)

        def make_sse_decoder():
            from openai._streaming import SSEDecoder

            return SSEDecoder()

        super().__init__(
            cast_to=ChatCompletionChunk,
            client=Mock(
                _process_response_data=process_response_data,
                _make_sse_decoder=make_sse_decoder,
            ),
            response=MockSyncResponse(chunks),
        )


@pytest.fixture
def mocked_streaming_create(streaming_chat_completion_messages):
    # Mock the base create method
    return Mock(return_value=MockStream(streaming_chat_completion_messages))


@pytest_asyncio.fixture
async def mocked_async_streaming_create(async_streaming_chat_completion_messages):
    async def mocked_create(*args, **kwargs):
        return async_streaming_chat_completion_messages

    return mocked_create


@pytest.fixture
def mocked_create(reassembled_chat_completion_message):
    # Mock the base create method
    return Mock(return_value=reassembled_chat_completion_message)


def make_stream_table(*args, **kwargs):
    # Unit test backend does not support async logging
    return StreamTable(*args, **kwargs, _disable_async_file_stream=True)


##########


def test_log_to_span_basic(
    user_by_api_key_in_env,
    mocked_create,
    teardown,
    reassembled_chat_completion_message,
    client,
):
    stream_name = "monitoring"
    project = "openai"
    entity = user_by_api_key_in_env.username

    streamtable = make_stream_table(
        stream_name, project_name=project, entity_name=entity
    )
    chat_completions = weave.legacy.weave.monitoring.openai.openai.ChatCompletions(
        mocked_create
    )
    create_input = dict(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "Tell me a joke"}],
    )
    result = chat_completions.create(**create_input)
    streamtable.finish()

    call = client.get_calls()[0]
    inputs = {k: v for k, v in call.inputs.items() if not k.startswith("_")}
    outputs = {k: v for k, v in call.output.items() if not k.startswith("_")}

    inputs_expected = create_input
    assert inputs == inputs_expected

    outputs_expected = reassembled_chat_completion_message.dict(exclude_unset=True)
    assert outputs == outputs_expected


def test_log_to_span_streaming(
    user_by_api_key_in_env,
    mocked_streaming_create,
    teardown,
    reassembled_chat_completion_message,
    client,
):
    chat_completions = weave.legacy.weave.monitoring.openai.openai.ChatCompletions(
        mocked_streaming_create
    )
    create_input = dict(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "Tell me a joke"}],
        stream=True,
    )
    stream = chat_completions.create(**create_input)
    for x in stream:
        ...

    call = client.get_calls()[0]
    inputs = {k: v for k, v in call.inputs.items() if not k.startswith("_")}
    outputs = {k: v for k, v in call.output.items() if not k.startswith("_")}

    inputs_expected = create_input
    assert inputs == inputs_expected

    outputs_expected = reassembled_chat_completion_message.dict(exclude_unset=True)
    assert outputs == outputs_expected


@pytest.mark.asyncio
async def test_log_to_span_async_streaming(
    user_by_api_key_in_env,
    mocked_async_streaming_create,
    teardown,
    reassembled_chat_completion_message,
    client,
):
    chat_completions = weave.legacy.weave.monitoring.openai.openai.AsyncChatCompletions(
        mocked_async_streaming_create
    )
    create_input = dict(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "Tell me a joke"}],
        stream=True,
    )
    stream = await chat_completions.create(**create_input)
    async for x in stream:
        ...

    call = client.get_calls()[0]
    inputs = {k: v for k, v in call.inputs.items() if not k.startswith("_")}
    outputs = {k: v for k, v in call.output.items() if not k.startswith("_")}

    inputs_expected = create_input
    assert inputs == inputs_expected

    outputs_expected = reassembled_chat_completion_message.dict(exclude_unset=True)
    assert outputs == outputs_expected


@contextlib.contextmanager
def async_disabled():
    current = os.environ.get("WEAVE_DISABLE_ASYNC_FILE_STREAM")
    os.environ["WEAVE_DISABLE_ASYNC_FILE_STREAM"] = "true"
    try:
        yield
    finally:
        if current is None:
            del os.environ["WEAVE_DISABLE_ASYNC_FILE_STREAM"]
        else:
            os.environ["WEAVE_DISABLE_ASYNC_FILE_STREAM"] = current
