import importlib

import typing

import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import SymbolPatcher, MultiPatcher

if typing.TYPE_CHECKING:
    from anthropic.types import Message, MessageStreamEvent


def anthropic_accumulator(
    acc: typing.Optional["Message"],
    value: "MessageStreamEvent",
) -> "Message":
    from anthropic.types import (
        Message,
        Usage,
        ContentBlockDeltaEvent,
        MessageDeltaEvent,
        TextBlock,
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
        acc.usage.output_tokens += value.message.usage.output_tokens

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

    return acc


# TODO: Add accumulator for beta.messages for tool usage


def anthropic_stream_wrapper(fn: typing.Callable) -> typing.Callable:
    op = weave.op()(fn)
    acc_op = add_accumulator(op, anthropic_accumulator)  # type: ignore
    return acc_op


def anthropic_create_wrapper(fn: typing.Callable) -> typing.Callable:
    def wrapper(*args, **kwargs):
        if kwargs.get(
            "stream", False
        ):  # we check if the stream parameter is set to True
            return anthropic_stream_wrapper(fn)(*args, **kwargs)
        return weave.op()(fn)(*args, **kwargs)

    return wrapper


anthropic_patcher = MultiPatcher(
    [
        # Patch the sync messages.create method for all messages.create methods
        SymbolPatcher(
            lambda: importlib.import_module("anthropic.resources.messages"),
            "Messages.create",
            anthropic_create_wrapper,
        ),
        SymbolPatcher(
            lambda: importlib.import_module("anthropic.resources.messages"),
            "AsyncMessages.create",
            anthropic_create_wrapper,
        ),
    ]
)
