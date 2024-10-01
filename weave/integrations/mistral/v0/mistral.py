import importlib
from typing import TYPE_CHECKING, Callable, Optional

import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher

if TYPE_CHECKING:
    from mistralai.models.chat_completion import (
        ChatCompletionResponse,
        ChatCompletionStreamResponse,
    )


def mistral_accumulator(
    acc: Optional["ChatCompletionResponse"],
    value: "ChatCompletionStreamResponse",
) -> "ChatCompletionResponse":
    # This import should be safe at this point
    from mistralai.models.chat_completion import (
        ChatCompletionResponse,
        ChatCompletionResponseChoice,
        ChatMessage,
    )
    from mistralai.models.common import UsageInfo

    if acc is None:
        acc = ChatCompletionResponse(
            id=value.id,
            object=value.object,
            created=value.created,
            model=value.model,
            choices=[],
            usage=UsageInfo(prompt_tokens=0, total_tokens=0, completion_tokens=None),
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
                ChatCompletionResponseChoice(
                    index=len(acc.choices),
                    message=ChatMessage(role="", content=""),
                    finish_reason=None,
                )
            )
        acc.choices[delta_choice.index].message.role = (
            delta_choice.delta.role or acc.choices[delta_choice.index].message.role
        )
        acc.choices[delta_choice.index].message.content += (
            delta_choice.delta.content or ""
        )
        if delta_choice.delta.tool_calls:
            if acc.choices[delta_choice.index].message.tool_calls is None:
                acc.choices[delta_choice.index].message.tool_calls = []
            acc.choices[
                delta_choice.index
            ].message.tool_calls += delta_choice.delta.tool_calls
        acc.choices[delta_choice.index].finish_reason = (
            delta_choice.finish_reason or acc.choices[delta_choice.index].finish_reason
        )

    return acc


def mistral_stream_wrapper(fn: Callable) -> Callable:
    op = weave.op()(fn)
    acc_op = add_accumulator(op, lambda inputs: mistral_accumulator)  # type: ignore
    return acc_op


mistral_patcher = MultiPatcher(
    [
        # Patch the sync, non-streaming chat method
        SymbolPatcher(
            lambda: importlib.import_module("mistralai.client"),
            "MistralClient.chat",
            weave.op(),
        ),
        # Patch the sync, streaming chat method
        SymbolPatcher(
            lambda: importlib.import_module("mistralai.client"),
            "MistralClient.chat_stream",
            mistral_stream_wrapper,
        ),
        # Patch the async, non-streaming chat method
        SymbolPatcher(
            lambda: importlib.import_module("mistralai.async_client"),
            "MistralAsyncClient.chat",
            weave.op(),
        ),
        # Patch the async, streaming chat method
        SymbolPatcher(
            lambda: importlib.import_module("mistralai.async_client"),
            "MistralAsyncClient.chat_stream",
            mistral_stream_wrapper,
        ),
    ]
)
