import copy
from types import SimpleNamespace

import pytest
from anthropic.lib.streaming._types import MessageStopEvent
from anthropic.resources.beta.messages import AsyncMessages as BetaAsyncMessages
from anthropic.resources.beta.messages import Messages as BetaMessages
from anthropic.resources.messages import AsyncMessages, Messages
from anthropic.types import Message, Usage
from anthropic.types.beta import BetaUsage

from weave.integrations.anthropic.anthropic_sdk import (
    anthropic_on_finish,
    create_stream_wrapper,
    create_wrapper_async,
    create_wrapper_sync,
    get_anthropic_patcher,
)
from weave.trace.autopatch import OpSettings
from weave.trace.weave_client import WeaveClient

pytestmark = pytest.mark.trace_server


def _cache_message() -> Message:
    return Message(
        id="msg_test",
        content=[],
        model="claude-test",
        role="assistant",
        stop_reason="end_turn",
        stop_sequence=None,
        type="message",
        usage=Usage(
            input_tokens=10,
            output_tokens=4,
            cache_read_input_tokens=100,
            cache_creation_input_tokens=20,
        ),
    )


@pytest.mark.parametrize(
    ("output_usage", "expected_gross"),
    [
        (SimpleNamespace(input_tokens=10), 10),
        (
            SimpleNamespace(
                input_tokens=10,
                cache_read_input_tokens=None,
                cache_creation_input_tokens=None,
            ),
            10,
        ),
        (
            SimpleNamespace(
                input_tokens=10,
                cache_read_input_tokens=100,
                cache_creation_input_tokens=0,
            ),
            110,
        ),
        (
            SimpleNamespace(
                input_tokens=10,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=20,
            ),
            30,
        ),
        (
            SimpleNamespace(
                input_tokens=10,
                cache_read_input_tokens=100,
                cache_creation_input_tokens=20,
            ),
            130,
        ),
    ],
)
def test_anthropic_on_finish_adds_gross_input_tokens(
    output_usage: SimpleNamespace, expected_gross: int
) -> None:
    model_usage = {
        "requests": 1,
        "input_tokens": 10,
        "output_tokens": 4,
        "cache_read_input_tokens": getattr(output_usage, "cache_read_input_tokens", 0),
        "cache_creation_input_tokens": getattr(
            output_usage, "cache_creation_input_tokens", 0
        ),
    }
    call = SimpleNamespace(summary={"usage": {"claude": model_usage}})
    output = SimpleNamespace(model="claude", usage=output_usage)

    anthropic_on_finish(call, output)
    anthropic_on_finish(call, output)

    assert model_usage == {
        "requests": 1,
        "input_tokens": 10,
        "output_tokens": 4,
        "cache_read_input_tokens": getattr(output_usage, "cache_read_input_tokens", 0),
        "cache_creation_input_tokens": getattr(
            output_usage, "cache_creation_input_tokens", 0
        ),
        "gross_input_tokens": expected_gross,
    }


@pytest.mark.parametrize(
    "output_usage",
    [
        SimpleNamespace(),
        SimpleNamespace(input_tokens=None),
        SimpleNamespace(input_tokens="10"),
        SimpleNamespace(input_tokens=True),
        SimpleNamespace(input_tokens=-1),
        SimpleNamespace(input_tokens=10, cache_read_input_tokens="100"),
        SimpleNamespace(input_tokens=10, cache_read_input_tokens=True),
        SimpleNamespace(input_tokens=10, cache_read_input_tokens=-1),
        SimpleNamespace(input_tokens=10, cache_creation_input_tokens="20"),
        SimpleNamespace(input_tokens=10, cache_creation_input_tokens=True),
        SimpleNamespace(input_tokens=10, cache_creation_input_tokens=-1),
    ],
)
def test_anthropic_on_finish_rejects_invalid_token_values(
    output_usage: SimpleNamespace,
) -> None:
    model_usage = {"input_tokens": 10, "output_tokens": 4}
    call = SimpleNamespace(summary={"usage": {"claude": model_usage}})

    anthropic_on_finish(call, SimpleNamespace(model="claude", usage=output_usage))

    assert model_usage == {"input_tokens": 10, "output_tokens": 4}


@pytest.mark.parametrize("model", [None, 1, True])
def test_anthropic_on_finish_requires_string_model(model: object) -> None:
    model_usage = {"input_tokens": 10}
    call = SimpleNamespace(summary={"usage": {"claude": model_usage}})

    anthropic_on_finish(
        call, SimpleNamespace(model=model, usage=SimpleNamespace(input_tokens=10))
    )

    assert model_usage == {"input_tokens": 10}


@pytest.mark.parametrize(
    "summary",
    [
        None,
        [],
        {},
        {"usage": []},
        {"usage": {"claude": []}},
        {"usage": {"other-model": {"input_tokens": 10}}},
    ],
)
def test_anthropic_on_finish_ignores_unexpected_summary_shape(summary: object) -> None:
    original_summary = copy.deepcopy(summary)
    call = SimpleNamespace(summary=summary)

    anthropic_on_finish(
        call,
        SimpleNamespace(model="claude", usage=SimpleNamespace(input_tokens=10)),
    )

    assert call.summary == original_summary


def test_anthropic_on_finish_supports_beta_usage() -> None:
    model_usage = {
        "input_tokens": 7,
        "output_tokens": 2,
        "cache_read_input_tokens": 11,
        "cache_creation_input_tokens": 13,
    }
    call = SimpleNamespace(summary={"usage": {"claude": model_usage}})
    output = SimpleNamespace(
        model="claude",
        usage=BetaUsage(
            input_tokens=7,
            output_tokens=2,
            cache_read_input_tokens=11,
            cache_creation_input_tokens=13,
        ),
    )

    anthropic_on_finish(call, output)

    assert model_usage == {
        "input_tokens": 7,
        "output_tokens": 2,
        "cache_read_input_tokens": 11,
        "cache_creation_input_tokens": 13,
        "gross_input_tokens": 31,
    }


def test_anthropic_resource_wrappers_register_finish_handler() -> None:
    patcher = get_anthropic_patcher()
    patcher.attempt_patch()
    try:
        wrapped_methods = [
            Messages.create,
            AsyncMessages.create,
            Messages.stream,
            AsyncMessages.stream,
            BetaMessages.create,
            BetaAsyncMessages.create,
            BetaMessages.parse,
            BetaAsyncMessages.parse,
            BetaMessages.stream,
            BetaAsyncMessages.stream,
        ]
        assert all(
            method._on_finish_handler is anthropic_on_finish
            for method in wrapped_methods
        )
    finally:
        patcher.undo_patch()


def test_anthropic_gross_input_tokens_are_persisted(client: WeaveClient) -> None:
    message = _cache_message()

    def create_message() -> Message:
        return message

    wrapped = create_wrapper_sync(OpSettings())(create_message)
    output = wrapped()
    created_call = next(iter(wrapped.calls()))
    persisted_call = client.get_call(created_call.id)

    assert output.usage == Usage(
        input_tokens=10,
        output_tokens=4,
        cache_read_input_tokens=100,
        cache_creation_input_tokens=20,
    )
    assert persisted_call.output.usage == output.usage
    assert persisted_call.summary["usage"]["claude-test"] == {
        "requests": 1,
        "input_tokens": 10,
        "output_tokens": 4,
        "cache_read_input_tokens": 100,
        "cache_creation_input_tokens": 20,
        "gross_input_tokens": 130,
    }


@pytest.mark.asyncio
async def test_async_anthropic_gross_input_tokens_are_persisted(
    client: WeaveClient,
) -> None:
    message = _cache_message()

    async def create_message() -> Message:
        return message

    wrapped = create_wrapper_async(OpSettings())(create_message)
    output = await wrapped()
    created_call = next(iter(wrapped.calls()))
    persisted_call = client.get_call(created_call.id)

    assert output.usage == message.usage
    assert persisted_call.output.usage == message.usage
    assert persisted_call.summary["usage"]["claude-test"] == {
        "requests": 1,
        "input_tokens": 10,
        "output_tokens": 4,
        "cache_read_input_tokens": 100,
        "cache_creation_input_tokens": 20,
        "gross_input_tokens": 130,
    }


def test_streamed_anthropic_gross_input_tokens_are_persisted(
    client: WeaveClient,
) -> None:
    message = _cache_message()
    event = MessageStopEvent(type="message_stop", message=message)

    def stream_message():
        yield event

    wrapped = create_stream_wrapper(OpSettings())(stream_message)
    assert list(wrapped()) == [event]
    created_call = next(iter(wrapped.calls()))
    persisted_call = client.get_call(created_call.id)

    assert persisted_call.output.usage == message.usage
    assert persisted_call.summary["usage"]["claude-test"] == {
        "requests": 1,
        "input_tokens": 10,
        "output_tokens": 4,
        "cache_read_input_tokens": 100,
        "cache_creation_input_tokens": 20,
        "gross_input_tokens": 130,
    }
