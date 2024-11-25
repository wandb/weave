import importlib
from collections.abc import AsyncIterator, Iterator
from functools import wraps
from typing import Any, Callable

import weave
from weave.trace.op import AsyncIterableContext, SyncIterableContext
from weave.trace.patcher import MultiPatcher, SymbolPatcher
from weave.trace.weave_client import Call


def should_accumulate(call: Call) -> bool:
    return bool(call.inputs.get("stream"))


class AnthropicCallback:
    def before_yield(self, call: Call, value: Any) -> None:
        from anthropic.types import (
            ContentBlockDeltaEvent,
            Message,
            MessageDeltaEvent,
            TextBlock,
            Usage,
        )

        if call.output is None:
            if not hasattr(value, "message"):
                raise ValueError("Initial event must contain a message")
            call.output = Message(
                id=value.message.id,
                role=value.message.role,
                content=[],
                model=value.message.model,
                stop_reason=value.message.stop_reason,
                stop_sequence=value.message.stop_sequence,
                type=value.message.type,
                usage=Usage(input_tokens=0, output_tokens=0),
            )

        # Merge in the usage info if available
        if hasattr(value, "message") and value.message.usage is not None:
            call.output.usage.input_tokens += value.message.usage.input_tokens

        # Accumulate the content if it's a ContentBlockDeltaEvent
        if isinstance(value, ContentBlockDeltaEvent) and hasattr(value.delta, "text"):
            if call.output.content and isinstance(call.output.content[-1], TextBlock):
                call.output.content[-1].text += value.delta.text
            else:
                call.output.content.append(
                    TextBlock(type="text", text=value.delta.text)
                )

        # Handle MessageDeltaEvent for stop_reason and stop_sequence
        if isinstance(value, MessageDeltaEvent):
            if hasattr(value.delta, "stop_reason") and value.delta.stop_reason:
                call.output.stop_reason = value.delta.stop_reason
            if hasattr(value.delta, "stop_sequence") and value.delta.stop_sequence:
                call.output.stop_sequence = value.delta.stop_sequence
            if hasattr(value, "usage") and value.usage.output_tokens:
                call.output.usage.output_tokens = value.usage.output_tokens


class AnthropicStreamingCallback:
    def before_yield(self, call: Call, value: Any) -> None:
        from anthropic.lib.streaming._types import MessageStopEvent

        if call.output is None:
            call.output = ""

        if isinstance(value, MessageStopEvent):
            call.output = value.message


def create_wrapper_sync(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        return weave.op(
            fn,
            name=name,
            callbacks=[AnthropicCallback()],
            __should_accumulate=should_accumulate,
        )

    return wrapper


# Surprisingly, the async `client.chat.completions.create` does not pass
# `inspect.iscoroutinefunction`, so we can't dispatch on it and must write
# it manually here...
def create_wrapper_async(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        def _fn_wrapper(fn: Callable) -> Callable:
            @wraps(fn)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await fn(*args, **kwargs)

            return _async_wrapper

        return weave.op(
            _fn_wrapper(fn),
            name=name,
            callbacks=[AnthropicCallback()],
            __should_accumulate=should_accumulate,
        )

    return wrapper


class AnthropicSyncIterableContext(SyncIterableContext):
    def __stream_text__(self) -> Iterator[str]:
        for chunk in self:  # type: ignore
            if chunk.type == "content_block_delta" and chunk.delta.type == "text_delta":  # type: ignore
                yield chunk.delta.text  # type: ignore

    @property
    def text_stream(self) -> Iterator[str]:
        return self.__stream_text__()


class AnthropicAsyncIterableContext(AsyncIterableContext):
    def __stream_text__(self) -> AsyncIterator[str]:
        return self.__async_stream_text__()

    async def __async_stream_text__(self) -> AsyncIterator[str]:
        async for chunk in self:  # type: ignore
            if chunk.type == "content_block_delta" and chunk.delta.type == "text_delta":  # type: ignore
                yield chunk.delta.text  # type: ignore

    @property
    def text_stream(self) -> AsyncIterator[str]:
        return self.__stream_text__()


def create_stream_wrapper(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        return weave.op(
            fn,
            name=name,
            callbacks=[AnthropicStreamingCallback()],
            # __should_accumulate=should_accumulate,
            __should_accumulate=lambda _: True,
            __custom_iterator_wrapper=AnthropicSyncIterableContext,
        )

    return wrapper


def create_async_stream_wrapper(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        return weave.op(
            fn,
            name=name,
            callbacks=[AnthropicStreamingCallback()],
            __should_accumulate=lambda _: True,
            __custom_iterator_wrapper=AnthropicAsyncIterableContext,
        )

    return wrapper


anthropic_patcher = MultiPatcher(
    [
        # Patch the sync messages.create method for all messages.create methods
        SymbolPatcher(
            lambda: importlib.import_module("anthropic.resources.messages"),
            "Messages.create",
            create_wrapper_sync(name="anthropic.Messages.create"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("anthropic.resources.messages"),
            "AsyncMessages.create",
            create_wrapper_async(name="anthropic.AsyncMessages.create"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("anthropic.resources.messages"),
            "Messages.stream",
            create_stream_wrapper(name="anthropic.Messages.stream"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("anthropic.resources.messages"),
            "AsyncMessages.stream",
            create_async_stream_wrapper(name="anthropic.AsyncMessages.stream"),
        ),
    ]
)
