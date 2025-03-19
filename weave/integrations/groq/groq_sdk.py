from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Callable

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.op import _add_accumulator

if TYPE_CHECKING:
    from groq.types.chat import ChatCompletion, ChatCompletionChunk


_groq_patcher: MultiPatcher | None = None


def groq_accumulator(
    acc: ChatCompletion | None, value: ChatCompletionChunk
) -> ChatCompletion:
    from groq.types.chat import ChatCompletion, ChatCompletionMessage
    from groq.types.chat.chat_completion import Choice
    from groq.types.chat.chat_completion_chunk import Choice as ChoiceChunk
    from groq.types.completion_usage import CompletionUsage

    if acc is None:
        choices = []
        for choice in value.choices:
            if isinstance(choice, ChoiceChunk):
                choices.append(
                    Choice(
                        message=ChatCompletionMessage(
                            content=choice.delta.content,
                            role=choice.delta.role,
                            function_call=choice.delta.function_call,
                            tool_call=choice.delta.tool_calls,
                        ),
                        finish_reason="stop",
                        index=choice.index,
                        logprobs=choice.logprobs,
                    )
                )
            else:
                choices.append(choice)
        acc = ChatCompletion(
            id=value.id,
            choices=choices,
            created=value.created,
            model=value.model,
            object="chat.completion",
            system_fingerprint=value.system_fingerprint,
            usage=CompletionUsage(
                completion_tokens=0,
                prompt_tokens=0,
                total_tokens=0,
                completion_time=0,
                prompt_time=0,
                queue_time=0,
                total_time=0,
            ),
        )

    if value.x_groq is not None and value.x_groq.usage is not None:
        acc.usage.completion_tokens += value.x_groq.usage.completion_tokens
        acc.usage.prompt_tokens += value.x_groq.usage.prompt_tokens
        acc.usage.total_tokens += value.x_groq.usage.total_tokens
        acc.usage.completion_time += value.x_groq.usage.completion_time
        acc.usage.prompt_time += value.x_groq.usage.prompt_time
        acc.usage.queue_time += value.x_groq.usage.queue_time
        acc.usage.total_time += value.x_groq.usage.total_time

    if value.choices:
        for idx, choice in enumerate(value.choices):
            if isinstance(acc.choices[idx].message.content, str) and isinstance(
                choice.delta.content, str
            ):
                acc.choices[idx].message.content += choice.delta.content
            if acc.choices[idx].message.function_call:
                acc.choices[idx].message.function_call.append(
                    choice.delta.function_call
                )
            if acc.choices[idx].message.tool_call:
                acc.choices[idx].message.tool_call.append(choice.delta.tool_call)

    return acc


def should_use_accumulator(inputs: dict) -> bool:
    return isinstance(inputs, dict) and bool(inputs.get("stream"))


def groq_wrapper(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return _add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: groq_accumulator,
            should_accumulate=should_use_accumulator,
        )

    return wrapper


def get_groq_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _groq_patcher
    if _groq_patcher is not None:
        return _groq_patcher

    base = settings.op_settings

    chat_completions_settings = base.model_copy(
        update={"name": base.name or "groq.chat.completions.create"}
    )
    async_chat_completions_settings = base.model_copy(
        update={"name": base.name or "groq.async.chat.completions.create"}
    )

    _groq_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("groq.resources.chat.completions"),
                "Completions.create",
                groq_wrapper(chat_completions_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("groq.resources.chat.completions"),
                "AsyncCompletions.create",
                groq_wrapper(async_chat_completions_settings),
            ),
        ]
    )

    return _groq_patcher
