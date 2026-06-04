from __future__ import annotations

from groq.types.chat import ChatCompletion, ChatCompletionChunk, ChatCompletionMessage
from groq.types.chat.chat_completion import Choice
from groq.types.chat.chat_completion_chunk import Choice as ChoiceChunk
from groq.types.completion_usage import CompletionUsage

from weave.integrations._llm_provider import Endpoint, LLMProviderPatcher
from weave.integrations.patcher import MultiPatcher, NoOpPatcher
from weave.trace.autopatch import IntegrationSettings


def groq_accumulator(
    acc: ChatCompletion | None, value: ChatCompletionChunk
) -> ChatCompletion:
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


# NOTE: groq's async endpoint historically did NOT use the async passthrough
# wrapper (unlike cerebras), so async_passthrough is left at its default (False).
_GROQ_ENDPOINTS = [
    Endpoint(
        module="groq.resources.chat.completions",
        symbol="Completions.create",
        op_name="groq.chat.completions.create",
        accumulator=lambda inputs: groq_accumulator,
    ),
    Endpoint(
        module="groq.resources.chat.completions",
        symbol="AsyncCompletions.create",
        op_name="groq.async.chat.completions.create",
        accumulator=lambda inputs: groq_accumulator,
    ),
]

_groq_provider = LLMProviderPatcher(_GROQ_ENDPOINTS)


def get_groq_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    return _groq_provider.get(settings)
