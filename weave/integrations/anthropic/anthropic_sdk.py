import importlib
import typing

import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher

if typing.TYPE_CHECKING:
    from anthropic.types import Message, MessageStreamEvent


def anthropic_accumulator(
    acc: typing.Optional["Message"],
    value: "MessageStreamEvent",
) -> "Message":
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
def should_use_accumulator(inputs: typing.Dict) -> bool:
    return isinstance(inputs, dict) and bool(inputs.get("stream"))


def create_wrapper(name: str) -> typing.Callable[[typing.Callable], typing.Callable]:
    def wrapper(fn: typing.Callable) -> typing.Callable:
        "We need to do this so we can check if `stream` is used"
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return add_accumulator(
            op,  # type: ignore
            anthropic_accumulator,
            should_accumulate=should_use_accumulator,
        )

    return wrapper


anthropic_patcher = MultiPatcher(
    [
        # Patch the sync messages.create method for all messages.create methods
        SymbolPatcher(
            lambda: importlib.import_module("anthropic.resources.messages"),
            "Messages.create",
            create_wrapper(name="anthropic.Messages.create"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("anthropic.resources.messages"),
            "AsyncMessages.create",
            create_wrapper(name="anthropic.AsyncMessages.create"),
        ),
    ]
)
