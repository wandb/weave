import importlib
from typing import Callable, Dict, Optional

from groq.types.chat import ChatCompletion, ChatCompletionChunk, ChatCompletionMessage
from groq.types.chat.chat_completion import Choice
from groq.types.chat.chat_completion_chunk import Choice as ChoiceChunk
from rich import print as pprint

import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher


def groq_accumulator(
    acc: Optional[ChatCompletion], value: ChatCompletionChunk
) -> ChatCompletion:
    if acc is None:
        choices = []
        for choice in value.choices:
            if isinstance(value.choices[0], ChoiceChunk):
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
        pprint(f"{value.object=}")
        acc = ChatCompletion(
            id=value.id,
            choices=choices,
            created=value.created,
            model=value.model,
            object="chat.completion",
            system_fingerprint=value.system_fingerprint,
            usage=value.usage,
        )

    if value.usage:
        acc.usage.completion_tokens += value.usage.completion_tokens
        acc.usage.prompt_tokens += value.usage.prompt_tokens
        acc.usage.total_tokens += value.usage.total_tokens

    if value.choices:
        for idx, choice in enumerate(value.choices):
            acc.choices[idx].message += choice.message
            if acc.choices[idx].function_call:
                acc.choices[idx].function_call.append(choice.function_call)
            if acc.choices[idx].tool_call:
                acc.choices[idx].tool_call.append(choice.tool_call)

    return acc


def should_use_accumulator(inputs: Dict) -> bool:
    return isinstance(inputs, dict) and bool(inputs.get("stream"))


def groq_wrapper(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        # return op
        return add_accumulator(
            op,  # type: ignore
            make_accumulator=lambda inputs: groq_accumulator,
            should_accumulate=should_use_accumulator,
        )

    return wrapper


groq_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("groq.resources.chat.completions"),
            "Completions.create",
            groq_wrapper(name="groq.resources.chat.completions.Completions.create"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("groq.resources.chat.completions"),
            "AsyncCompletions.create",
            groq_wrapper(
                name="groq.resources.chat.completions.AsyncCompletions.create"
            ),
        ),
    ]
)
