import contextlib
import os
from unittest.mock import Mock

import openai
import pytest
from openai.types.chat.chat_completion import ChatCompletion, Choice
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk, ChoiceDelta
from openai.types.chat.chat_completion_chunk import Choice as ChunkChoice
from openai.types.completion_usage import CompletionUsage

import weave
from weave.monitoring.openai import util
from weave.monitoring.openai.models import *
from weave.monitoring.openai.models import Context
from weave.monitoring.openai.openai import Callback, ReassembleStream, patch, unpatch
from weave.monitoring.openai.util import Context
from weave.wandb_interface.wandb_stream_table import StreamTable


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


@pytest.fixture
def reassembled_chat_completion_message():
    return ChatCompletion(
        id="chatcmpl-blank",
        choices=[
            Choice(
                finish_reason="stop",
                index=0,
                message=ChatCompletionMessage(
                    content="Why don't scientists trust atoms?\n\nBecause they make up everything!",
                    role="assistant",
                    function_call=None,
                    tool_calls=None,
                ),
            )
        ],
        created=1700686161,
        model="gpt-3.5-turbo-0613",
        object="chat.completion",
        system_fingerprint=None,
        usage=CompletionUsage(completion_tokens=19, prompt_tokens=10, total_tokens=29),
    )


@pytest.fixture
def client():
    c = Mock(spec=openai.OpenAI)
    c.chat = Mock()
    c.chat.completions = Mock()
    c.chat.completions.create = Mock()
    return c


@pytest.fixture
def streaming_client(client, streaming_chat_completion_messages):
    client.chat.completions.create.return_value = iter(
        streaming_chat_completion_messages
    )
    return client


@pytest.fixture
def teardown():
    yield
    unpatch()


@pytest.fixture
def mocked_streaming_create(streaming_chat_completion_messages):
    # Mock the base create method
    return Mock(return_value=iter(streaming_chat_completion_messages))


@pytest.fixture
def mocked_create(reassembled_chat_completion_message):
    # Mock the base create method
    return Mock(return_value=reassembled_chat_completion_message)


def make_stream_table(*args, **kwargs):
    # Unit test backend does not support async logging
    return StreamTable(*args, **kwargs, _disable_async_file_stream=True)


class TestingCallback(Callback):
    def before_send_request(self, context: Context, *args, **kwargs):
        context.testing = []
        context.testing.append("before_send_request")

    def before_end(self, context: Context, *args, **kwargs):
        context.testing.append("before_end")

    def before_yield_chunk(self, context: Context, *args, **kwargs):
        context.testing.append("before_yield_chunk")

    def after_yield_chunk(self, context: Context, *args, **kwargs):
        context.testing.append("after_yield_chunk")


##########


def test_reconstruct_completion(
    chat_completion_request_message,
    streaming_chat_completion_messages,
    reassembled_chat_completion_message,
):
    assert (
        util.reconstruct_completion(
            chat_completion_request_message, streaming_chat_completion_messages
        )
        == reassembled_chat_completion_message
    )


def test_callback_reassemble_stream(
    mocked_streaming_create, teardown, reassembled_chat_completion_message
):
    cb = ReassembleStream()
    chat_completions = weave.monitoring.openai.openai.ChatCompletions(
        mocked_streaming_create, callbacks=[cb]
    )
    stream = chat_completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "Tell me a joke"}],
        stream=True,
    )
    for x in stream:
        ...

    assert chat_completions.context.outputs == reassembled_chat_completion_message


def test_log_to_span(
    user_by_api_key_in_env, mocked_create, teardown, reassembled_chat_completion_message
):
    stream_name = "monitoring"
    project = "openai"
    entity = user_by_api_key_in_env.username

    streamtable = make_stream_table(
        stream_name, project_name=project, entity_name=entity
    )
    chat_completions = weave.monitoring.openai.openai.ChatCompletions(
        mocked_create, streamtable=streamtable
    )
    create_input = dict(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "Tell me a joke"}],
    )
    result = chat_completions.create(**create_input)
    streamtable.finish()

    hist_node = (
        weave.ops.project(user_by_api_key_in_env.username, project)
        .run(stream_name)
        .history3()
    )

    inputs_st = weave.use(hist_node["inputs"]).to_pylist_tagged()[0]
    inputs_expected = ChatCompletionRequest.parse_obj(create_input).dict()
    assert inputs_st == inputs_expected

    outputs_st = weave.use(hist_node["output"]).to_pylist_tagged()[0]
    outputs_expected = reassembled_chat_completion_message.dict()
    assert outputs_st == outputs_expected


def test_log_to_span_streaming(
    user_by_api_key_in_env,
    mocked_streaming_create,
    teardown,
    reassembled_chat_completion_message,
):
    stream_name = "monitoring"
    project = "openai"
    entity = user_by_api_key_in_env.username

    streamtable = make_stream_table(
        stream_name, project_name=project, entity_name=entity
    )
    chat_completions = weave.monitoring.openai.openai.ChatCompletions(
        mocked_streaming_create,
        callbacks=[ReassembleStream()],
        streamtable=streamtable,
    )
    create_input = dict(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "Tell me a joke"}],
        stream=True,
    )
    stream = chat_completions.create(**create_input)
    for x in stream:
        ...

    streamtable.finish()

    hist_node = (
        weave.ops.project(user_by_api_key_in_env.username, project)
        .run(stream_name)
        .history3()
    )

    inputs_st = weave.use(hist_node["inputs"]).to_pylist_tagged()[0]
    inputs_expected = ChatCompletionRequest.parse_obj(create_input).dict()
    assert inputs_st == inputs_expected

    outputs_st = weave.use(hist_node["output"]).to_pylist_tagged()[0]
    outputs_expected = reassembled_chat_completion_message.dict()
    assert outputs_st == outputs_expected


def test_callback_ordering(mocked_streaming_create):
    cb = TestingCallback()
    chat_completions = weave.monitoring.openai.openai.ChatCompletions(
        mocked_streaming_create, callbacks=[ReassembleStream(), cb]
    )
    stream = chat_completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "Tell me a joke"}],
        stream=True,
    )

    for i, x in enumerate(stream, 1):
        ...

    chunk_messages = [
        "before_yield_chunk",
        "after_yield_chunk",
    ] * i  # 1 pair for each SSE received
    expected = ["before_send_request", *chunk_messages, "before_end"]

    assert expected == chat_completions.context.testing


def test_patching(user_by_api_key_in_env):
    og_create = openai.resources.chat.completions.Completions.create
    og_acreate = openai.resources.chat.completions.AsyncCompletions.create

    patch(callbacks=[])
    assert openai.resources.chat.completions.Completions.create is not og_create
    assert openai.resources.chat.completions.AsyncCompletions.create is not og_acreate

    unpatch()
    assert openai.resources.chat.completions.Completions.create is og_create
    assert openai.resources.chat.completions.AsyncCompletions.create is og_acreate


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
