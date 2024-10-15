import importlib
from typing import TYPE_CHECKING, Callable, Optional

import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher

if TYPE_CHECKING:
    from mistralai.models import (
        ChatCompletionResponse,
        CompletionEvent,
    )


def mistral_accumulator(
    acc: Optional["ChatCompletionResponse"],
    value: "CompletionEvent",
) -> "ChatCompletionResponse":
    # This import should be safe at this point
    from mistralai.models import (
        AssistantMessage,
        ChatCompletionChoice,
        ChatCompletionResponse,
        UsageInfo,
    )

    value = value.data
    if acc is None:
        acc = ChatCompletionResponse(
            id=value.id,
            object=value.object,
            created=value.created,
            model=value.model,
            choices=[],
            usage=UsageInfo(prompt_tokens=0, total_tokens=0, completion_tokens=0),
        )

    # Merge in the usage info
    if value.usage is not None:
        acc.usage.prompt_tokens += value.usage.prompt_tokens
        acc.usage.total_tokens += value.usage.total_tokens
        if acc.usage.completion_tokens is None:
            acc.usage.completion_tokens = value.usage.completion_tokens
        else:
            acc.usage.completion_tokens += value.usage.completion_tokens

    # Loop through the choices and add their deltas
    for delta_choice in value.choices:
        while delta_choice.index >= len(acc.choices):
            acc.choices.append(
                ChatCompletionChoice(
                    index=len(acc.choices),
                    message=AssistantMessage(content=""),
                    finish_reason="stop",
                )
            )

        if acc.choices is None:
            return acc

        target_choice: ChatCompletionChoice = acc.choices[delta_choice.index]

        if target_choice is None:
            return acc

        target_choice.finish_reason = (
            delta_choice.finish_reason or target_choice.finish_reason
        )

        target_choice.message.role = (
            delta_choice.delta.role or target_choice.message.role
        )
        target_choice.message.content += delta_choice.delta.content or ""
        if delta_choice.delta.tool_calls:
            if target_choice.message.tool_calls is None:
                target_choice.message.tool_calls = []
            target_choice.message.tool_calls += delta_choice.delta.tool_calls

    return acc


def mistral_stream_wrapper(name: str) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        acc_op = add_accumulator(op, lambda inputs: mistral_accumulator)  # type: ignore
        acc_op.name = name  # type: ignore
        return acc_op

    return wrapper


def mistral_wrapper(name: str) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return op

    return wrapper


mistral_patcher = MultiPatcher(
    [
        # Patch the sync, non-streaming chat method
        SymbolPatcher(
            lambda: importlib.import_module("mistralai.chat"),
            "Chat.complete",
            mistral_wrapper(name="Mistral.chat.complete"),
        ),
        # Patch the sync, streaming chat method
        SymbolPatcher(
            lambda: importlib.import_module("mistralai.chat"),
            "Chat.stream",
            mistral_stream_wrapper(name="Mistral.chat.stream"),
        ),
        # Patch the async, non-streaming chat method
        SymbolPatcher(
            lambda: importlib.import_module("mistralai.chat"),
            "Chat.complete_async",
            mistral_wrapper(name="Mistral.chat.complete_async"),
        ),
        # Patch the async, streaming chat method
        SymbolPatcher(
            lambda: importlib.import_module("mistralai.chat"),
            "Chat.stream_async",
            mistral_stream_wrapper(name="Mistral.chat.stream_async"),
        ),
    ]
)
