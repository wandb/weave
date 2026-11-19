from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import TYPE_CHECKING

from groq.types.chat import ChatCompletion, ChatCompletionChunk, ChatCompletionMessage
from groq.types.chat.chat_completion import Choice
from groq.types.chat.chat_completion_chunk import Choice as ChoiceChunk
from groq.types.chat.chat_completion_chunk import ChoiceDelta
from groq.types.chat.chat_completion_message import FunctionCall
from groq.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)
from groq.types.completion_usage import CompletionUsage

import weave
from weave.integrations.integration_metadata import (
    library_integration,
    with_integration_metadata,
)
from weave.integrations.integration_utilities import should_use_accumulator
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.op import _add_accumulator

if TYPE_CHECKING:
    pass


_groq_patcher: MultiPatcher | None = None

GROQ_INTEGRATION = library_integration("groq")


def groq_accumulator(
    acc: ChatCompletion | None, value: ChatCompletionChunk
) -> ChatCompletion:
    if acc is None:
        choices = []
        for choice in value.choices:
            if isinstance(choice, ChoiceChunk):
                choices.append(
                    Choice(
                        message=ChatCompletionMessage(role="assistant"),
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

    for idx, choice in enumerate(value.choices):
        _merge_delta(acc.choices[idx].message, choice.delta)
        if choice.finish_reason:
            acc.choices[idx].finish_reason = choice.finish_reason  # type: ignore[assignment]

    return acc


def _merge_delta(message: ChatCompletionMessage, delta: ChoiceDelta) -> None:
    if delta.content is not None:
        message.content = (message.content or "") + delta.content
    if delta.reasoning is not None:
        message.reasoning = (message.reasoning or "") + delta.reasoning
    if delta.function_call is not None:
        if message.function_call is None:
            message.function_call = FunctionCall(name="", arguments="")
        message.function_call.name += delta.function_call.name or ""
        message.function_call.arguments += delta.function_call.arguments or ""
    for tool_call in delta.tool_calls or []:
        if message.tool_calls is None:
            message.tool_calls = []
        while tool_call.index >= len(message.tool_calls):
            message.tool_calls.append(
                ChatCompletionMessageToolCall(
                    id="", type="function", function=Function(name="", arguments="")
                )
            )
        merged = message.tool_calls[tool_call.index]
        if tool_call.id:
            merged.id = tool_call.id
        if tool_call.function is not None:
            merged.function.name += tool_call.function.name or ""
            merged.function.arguments += tool_call.function.arguments or ""


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

    global _groq_patcher  # noqa: PLW0603
    if _groq_patcher is not None:
        return _groq_patcher

    base = with_integration_metadata(settings.op_settings, GROQ_INTEGRATION)

    chat_completions_settings = base.model_copy(
        update={
            "name": base.name or "groq.chat.completions.create",
            "kind": base.kind or "llm",
        }
    )
    async_chat_completions_settings = base.model_copy(
        update={
            "name": base.name or "groq.async.chat.completions.create",
            "kind": base.kind or "llm",
        }
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
