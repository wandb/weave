from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Callable

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.op import _add_accumulator

if TYPE_CHECKING:
    from mistralai.models.chat_completion import (
        ChatCompletionResponse,
        ChatCompletionStreamResponse,
    )

_mistral_patcher: MultiPatcher | None = None


def mistral_accumulator(
    acc: ChatCompletionResponse | None,
    value: ChatCompletionStreamResponse,
) -> ChatCompletionResponse:
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


def mistral_stream_wrapper(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        acc_op = _add_accumulator(op, lambda inputs: mistral_accumulator)  # type: ignore
        return acc_op

    return wrapper


def mistral_wrapper(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def get_mistral_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _mistral_patcher
    if _mistral_patcher is not None:
        return _mistral_patcher

    base = settings.op_settings

    chat_settings = base.model_copy(update={"name": base.name or "mistralai.chat"})
    chat_stream_settings = base.model_copy(
        update={"name": base.name or "mistralai.chat_stream"}
    )
    async_chat_settings = base.model_copy(
        update={"name": base.name or "mistralai.async_client.chat"}
    )
    async_chat_stream_settings = base.model_copy(
        update={"name": base.name or "mistralai.async_client.chat_stream"}
    )

    _mistral_patcher = MultiPatcher(
        [
            # Patch the sync, non-streaming chat method
            SymbolPatcher(
                lambda: importlib.import_module("mistralai.client"),
                "MistralClient.chat",
                mistral_wrapper(chat_settings),
            ),
            # Patch the sync, streaming chat method
            SymbolPatcher(
                lambda: importlib.import_module("mistralai.client"),
                "MistralClient.chat_stream",
                mistral_stream_wrapper(chat_stream_settings),
            ),
            # Patch the async, non-streaming chat method
            SymbolPatcher(
                lambda: importlib.import_module("mistralai.async_client"),
                "MistralAsyncClient.chat",
                mistral_wrapper(async_chat_settings),
            ),
            # Patch the async, streaming chat method
            SymbolPatcher(
                lambda: importlib.import_module("mistralai.async_client"),
                "MistralAsyncClient.chat_stream",
                mistral_stream_wrapper(async_chat_stream_settings),
            ),
        ]
    )

    return _mistral_patcher
