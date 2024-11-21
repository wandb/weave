from __future__ import annotations

import importlib
from functools import wraps
from typing import Any, Callable

from anthropic import MessageStopEvent

import weave
from weave.trace.op import Callback
from weave.trace.patcher import MultiPatcher, SymbolPatcher
from weave.trace.weave_client import Call


def should_accumulate(call: Call) -> bool:
    return bool(call.inputs.get("stream"))


class AnthropicCallback(Callback):
    def __init__(self):
        self.acc = None

    def after_yield(self, call: Call, value: Any) -> None:
        from anthropic.types import (
            ContentBlockDeltaEvent,
            Message,
            MessageDeltaEvent,
            TextBlock,
            Usage,
        )

        print(f"{value=}, {self.acc=}")

        if self.acc is None:
            if not hasattr(value, "message"):
                raise ValueError("Initial event must contain a message")
            self.acc = Message(
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
            self.acc.usage.input_tokens += value.message.usage.input_tokens

        # Accumulate the content if it's a ContentBlockDeltaEvent
        if isinstance(value, ContentBlockDeltaEvent) and hasattr(value.delta, "text"):
            if self.acc.content and isinstance(self.acc.content[-1], TextBlock):
                self.acc.content[-1].text += value.delta.text
            else:
                self.acc.content.append(TextBlock(type="text", text=value.delta.text))

        # Handle MessageDeltaEvent for stop_reason and stop_sequence
        if isinstance(value, MessageDeltaEvent):
            if hasattr(value.delta, "stop_reason") and value.delta.stop_reason:
                self.acc.stop_reason = value.delta.stop_reason
            if hasattr(value.delta, "stop_sequence") and value.delta.stop_sequence:
                self.acc.stop_sequence = value.delta.stop_sequence
            if hasattr(value, "usage") and value.usage.output_tokens:
                self.acc.usage.output_tokens = value.usage.output_tokens

    def after_yield_all(self, call: Call) -> None:
        call.output = self.acc


class AnthropicStreamingCallback:
    def __init__(self):
        self.acc = None

    def after_yield(self, call: Call, value: Any) -> None:
        print(f"{value=}, {self.acc=}")

        if self.acc is None:
            self.acc = ""
        if isinstance(value, MessageStopEvent):
            self.acc = value.message

    def after_yield_all(self, call: Call) -> None:
        call.output = self.acc


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

        "We need to do this so we can check if `stream` is used"
        return weave.op(
            _fn_wrapper(fn),
            name=name,
            callbacks=[AnthropicCallback()],
            __should_accumulate=should_accumulate,
        )

    return wrapper


def create_wrapper_stream(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        return weave.op(
            fn,
            name=name,
            callbacks=[AnthropicStreamingCallback()],
            __should_accumulate=lambda call: True,
            __should_use_contextmanager=lambda f: True,
        )

    return wrapper


def create_wrapper_async_stream(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        return weave.op(
            fn,
            name=name,
            callbacks=[AnthropicStreamingCallback()],
            __should_accumulate=lambda call: True,
            __should_use_contextmanager=lambda f: True,
        )

    return wrapper


anthropic_patcher = MultiPatcher(
    [
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
            create_wrapper_stream(name="anthropic.Messages.stream"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("anthropic.resources.messages"),
            "AsyncMessages.stream",
            create_wrapper_async_stream(name="anthropic.AsyncMessages.stream"),
        ),
    ]
)
