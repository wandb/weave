from __future__ import annotations

import importlib
from collections.abc import AsyncIterator, Iterator
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.op import _add_accumulator, _IteratorWrapper

if TYPE_CHECKING:
    from anthropic.lib.streaming import MessageStream
    from anthropic.types import Message, MessageStreamEvent

_anthropic_patcher: MultiPatcher | None = None


def anthropic_accumulator(
    acc: Message | None,
    value: MessageStreamEvent,
) -> Message:
    from anthropic.types import (
        ContentBlockDeltaEvent,
        Message,
        MessageDeltaEvent,
        TextBlock,
        Usage,
    )

    if acc is None:
        if hasattr(value, "message"):
            acc = Message(
                id=value.message.id,
                role=value.message.role,
                content=[],
                model=value.message.model,
                stop_reason=value.message.stop_reason,
                stop_sequence=value.message.stop_sequence,
                type=value.message.type,  # Include the type field
                usage=Usage(input_tokens=0, output_tokens=0),
            )
        else:
            raise ValueError("Initial event must contain a message")

    # Merge in the usage info if available
    if hasattr(value, "message") and value.message.usage is not None:
        acc.usage.input_tokens += value.message.usage.input_tokens

    # Accumulate the content if it's a ContentBlockDeltaEvent
    if isinstance(value, ContentBlockDeltaEvent) and hasattr(value.delta, "text"):
        if acc.content and isinstance(acc.content[-1], TextBlock):
            acc.content[-1].text += value.delta.text
        else:
            acc.content.append(TextBlock(type="text", text=value.delta.text))

    # Handle MessageDeltaEvent for stop_reason and stop_sequence
    if isinstance(value, MessageDeltaEvent):
        if hasattr(value.delta, "stop_reason") and value.delta.stop_reason:
            acc.stop_reason = value.delta.stop_reason
        if hasattr(value.delta, "stop_sequence") and value.delta.stop_sequence:
            acc.stop_sequence = value.delta.stop_sequence
        if hasattr(value, "usage") and value.usage.output_tokens:
            acc.usage.output_tokens = value.usage.output_tokens

    return acc


# Unlike other integrations, streaming is based on input flag
def should_use_accumulator(inputs: dict) -> bool:
    return isinstance(inputs, dict) and bool(inputs.get("stream"))


def create_wrapper_sync(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        "We need to do this so we can check if `stream` is used"
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return _add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: anthropic_accumulator,
            should_accumulate=should_use_accumulator,
        )

    return wrapper


# Surprisingly, the async `client.chat.completions.create` does not pass
# `inspect.iscoroutinefunction`, so we can't dispatch on it and must write
# it manually here...
def create_wrapper_async(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        def _fn_wrapper(fn: Callable) -> Callable:
            @wraps(fn)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await fn(*args, **kwargs)

            return _async_wrapper

        "We need to do this so we can check if `stream` is used"
        op_kwargs = settings.model_dump()
        op = weave.op(_fn_wrapper(fn), **op_kwargs)
        return _add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: anthropic_accumulator,
            should_accumulate=should_use_accumulator,
        )

    return wrapper


## This part of the code is for dealing with the other way
## of streaming, by calling Messages.stream
## this has 2 options: event based or text based.
## This code handles both cases by patching the _IteratorWrapper
## and adding a text_stream property to it.


def anthropic_stream_accumulator(
    acc: Message | None,
    value: MessageStream,
) -> Message:
    from anthropic.lib.streaming._types import MessageStopEvent

    if acc is None:
        acc = ""
    if isinstance(value, MessageStopEvent):
        acc = value.message
    return acc


class AnthropicIteratorWrapper(_IteratorWrapper):
    def __getattr__(self, name: str) -> Any:
        """Delegate all other attributes to the wrapped iterator."""
        if name in [
            "_iterator_or_ctx_manager",
            "_on_yield",
            "_on_error",
            "_on_close",
            "_on_finished_called",
            "_call_on_error_once",
            "text_stream",
        ]:
            return object.__getattribute__(self, name)
        return getattr(self._iterator_or_ctx_manager, name)

    def __stream_text__(self) -> Iterator[str] | AsyncIterator[str]:
        if isinstance(self._iterator_or_ctx_manager, AsyncIterator):
            return self.__async_stream_text__()
        else:
            return self.__sync_stream_text__()

    def __sync_stream_text__(self) -> Iterator[str]:  # type: ignore
        for chunk in self:  # type: ignore
            if chunk.type == "content_block_delta" and chunk.delta.type == "text_delta":  # type: ignore
                yield chunk.delta.text  # type: ignore

    async def __async_stream_text__(self) -> AsyncIterator[str]:  # type: ignore
        async for chunk in self:  # type: ignore
            if chunk.type == "content_block_delta" and chunk.delta.type == "text_delta":  # type: ignore
                yield chunk.delta.text  # type: ignore

    @property
    def text_stream(self) -> Iterator[str] | AsyncIterator[str]:
        return self.__stream_text__()


def create_stream_wrapper(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return _add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda _: anthropic_stream_accumulator,
            should_accumulate=lambda _: True,
            iterator_wrapper=AnthropicIteratorWrapper,  # type: ignore
        )

    return wrapper


def get_anthropic_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _anthropic_patcher
    if _anthropic_patcher is not None:
        return _anthropic_patcher

    base = settings.op_settings

    messages_create_settings = base.model_copy(
        update={"name": base.name or "anthropic.Messages.create"}
    )
    async_messages_create_settings = base.model_copy(
        update={"name": base.name or "anthropic.AsyncMessages.create"}
    )
    stream_settings = base.model_copy(
        update={"name": base.name or "anthropic.Messages.stream"}
    )
    async_stream_settings = base.model_copy(
        update={"name": base.name or "anthropic.AsyncMessages.stream"}
    )

    _anthropic_patcher = MultiPatcher(
        [
            # Patch the sync messages.create method for all messages.create methods
            SymbolPatcher(
                lambda: importlib.import_module("anthropic.resources.messages"),
                "Messages.create",
                create_wrapper_sync(messages_create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("anthropic.resources.messages"),
                "AsyncMessages.create",
                create_wrapper_async(async_messages_create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("anthropic.resources.messages"),
                "Messages.stream",
                create_stream_wrapper(stream_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("anthropic.resources.messages"),
                "AsyncMessages.stream",
                create_stream_wrapper(async_stream_settings),
            ),
        ]
    )

    return _anthropic_patcher
