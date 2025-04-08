from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Callable

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.op import _add_accumulator

if TYPE_CHECKING:
    from mistralai.models import (
        ChatCompletionResponse,
        CompletionEvent,
    )

_mistral_patcher: MultiPatcher | None = None


def mistral_accumulator(
    acc: ChatCompletionResponse | None,
    value: CompletionEvent,
) -> ChatCompletionResponse:
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
    chat_complete_settings = base.model_copy(
        update={"name": base.name or "mistralai.chat.complete"}
    )
    chat_stream_settings = base.model_copy(
        update={"name": base.name or "mistralai.chat.stream"}
    )
    async_chat_complete_settings = base.model_copy(
        update={"name": base.name or "mistralai.async_client.chat.complete"}
    )
    async_chat_stream_settings = base.model_copy(
        update={"name": base.name or "mistralai.async_client.chat.stream"}
    )

    _mistral_patcher = MultiPatcher(
        [
            # Patch the sync, non-streaming chat method
            SymbolPatcher(
                lambda: importlib.import_module("mistralai.chat"),
                "Chat.complete",
                mistral_wrapper(chat_complete_settings),
            ),
            # Patch the sync, streaming chat method
            SymbolPatcher(
                lambda: importlib.import_module("mistralai.chat"),
                "Chat.stream",
                mistral_stream_wrapper(chat_stream_settings),
            ),
            # Patch the async, non-streaming chat method
            SymbolPatcher(
                lambda: importlib.import_module("mistralai.chat"),
                "Chat.complete_async",
                mistral_wrapper(async_chat_complete_settings),
            ),
            # Patch the async, streaming chat method
            SymbolPatcher(
                lambda: importlib.import_module("mistralai.chat"),
                "Chat.stream_async",
                mistral_stream_wrapper(async_chat_stream_settings),
            ),
        ]
    )

    return _mistral_patcher
