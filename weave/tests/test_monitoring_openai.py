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
from weave.monitoring import init_monitor
from weave.monitoring.openai import util
from weave.monitoring.openai.models import *
from weave.monitoring.openai.models import Context
from weave.monitoring.openai.openai import patch, unpatch
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


def test_log_to_span_basic(
    user_by_api_key_in_env, mocked_create, teardown, reassembled_chat_completion_message
):
    with weave.local_client() as client:
        stream_name = "monitoring"
        project = "openai"
        entity = user_by_api_key_in_env.username

        streamtable = make_stream_table(
            stream_name, project_name=project, entity_name=entity
        )
        chat_completions = weave.monitoring.openai.openai.ChatCompletions(mocked_create)
        create_input = dict(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "Tell me a joke"}],
        )
        result = chat_completions.create(**create_input)
        streamtable.finish()

        run = client.runs()[0]
        inputs = {k: v for k, v in run.inputs.items() if not k.startswith("_")}
        outputs = {k: v for k, v in run.output.get().items() if not k.startswith("_")}

        inputs_expected = ChatCompletionRequest.parse_obj(create_input).dict()
        assert inputs == inputs_expected

        outputs_expected = reassembled_chat_completion_message.dict(exclude_unset=True)
        assert outputs == outputs_expected


def test_log_to_span_streaming(
    user_by_api_key_in_env,
    mocked_streaming_create,
    teardown,
    reassembled_chat_completion_message,
):
    with weave.local_client() as client:
        chat_completions = weave.monitoring.openai.openai.ChatCompletions(
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

        run = client.runs()[0]
        inputs = {k: v for k, v in run.inputs.items() if not k.startswith("_")}
        outputs = {k: v for k, v in run.output.get().items() if not k.startswith("_")}

        inputs_expected = ChatCompletionRequest.parse_obj(create_input).dict()
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
