import inspect
from contextlib import contextmanager
from typing import Any, Callable, Dict, Generator, Iterator, Optional, TypeVar

import tiktoken
from openai.types.chat.chat_completion import ChatCompletion, Choice
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from openai.types.completion_usage import CompletionUsage

import wandb

from .models import *

T = TypeVar("T")


def update_combined_choice(
    combined_choice: CombinedChoice, choice: Choice
) -> CombinedChoice:
    combined_choice.content += choice.delta.content or ""
    combined_choice.role = combined_choice.role or choice.delta.role
    combined_choice.function_call = (
        combined_choice.function_call or choice.delta.function_call
    )
    combined_choice.tool_calls = combined_choice.tool_calls or choice.delta.tool_calls
    if choice.finish_reason:
        combined_choice.finish_reason = choice.finish_reason
    return combined_choice


def reconstruct_completion(
    input_messages: List[ChatCompletionMessage],
    output_chunks: List[ChatCompletionChunk],
) -> ChatCompletion:
    combined_results: Dict[int, CombinedChoice] = {}

    if not output_chunks:
        raise Exception

    for chunk in output_chunks:
        for choice in chunk.choices:
            index = choice.index
            if index not in combined_results:
                combined_results[index] = CombinedChoice()
            combined_results[index] = update_combined_choice(
                combined_results[index], choice
            )

    # Construct ChatCompletionChoice objects
    combined_choices = [
        Choice(
            # logprobs included here because latest versions of pydantic require
            # optional fields without default values to be included in the
            # constructor
            logprobs=None,
            finish_reason=result.finish_reason,
            index=index,
            message=ChatCompletionMessage(
                content=result.content,
                role=result.role,
                function_call=result.function_call,
                tool_calls=result.tool_calls,
            ),
        )
        for index, result in sorted(combined_results.items())
    ]

    # Assume all chunks belong to the same completion
    first_chunk = output_chunks[0]

    prompt_tokens = num_tokens_from_messages(input_messages)
    completion_tokens = 0
    for choice in combined_choices:
        message = choice.message
        completion_tokens += num_tokens_from_messages([message])

    total_tokens = prompt_tokens + completion_tokens
    usage = CompletionUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )

    return ChatCompletion(
        id=first_chunk.id,
        choices=combined_choices,
        created=first_chunk.created,
        model=first_chunk.model,
        object="chat.completion",
        usage=usage,
    )


def num_tokens_from_messages(
    messages: List[ChatCompletionMessage], model: str = "gpt-3.5-turbo-0613"
) -> int:
    model_defaults = {
        "gpt-3.5-turbo-0613": ModelTokensConfig(per_message=3, per_name=1),
        "gpt-3.5-turbo-16k-0613": ModelTokensConfig(per_message=3, per_name=1),
        "gpt-4-0314": ModelTokensConfig(per_message=3, per_name=1),
        "gpt-4-32k-0314": ModelTokensConfig(per_message=3, per_name=1),
        "gpt-4-0613": ModelTokensConfig(per_message=3, per_name=1),
        "gpt-4-32k-0613": ModelTokensConfig(per_message=3, per_name=1),
        "gpt-3.5-turbo-0301": ModelTokensConfig(per_message=4, per_name=-1),
    }

    config = model_defaults.get(model)
    if config is None:
        if "gpt-3.5-turbo" in model:
            print(
                "Warning: gpt-3.5-turbo may update over time. Assuming gpt-3.5-turbo-0613."
            )
            return num_tokens_from_messages(messages, "gpt-3.5-turbo-0613")
        elif "gpt-4" in model:
            print("Warning: gpt-4 may update over time. Assuming gpt-4-0613.")
            return num_tokens_from_messages(messages, "gpt-4-0613")
        else:
            raise NotImplementedError(
                f"num_tokens_from_messages() is not implemented for model {model}. "
                "See https://github.com/openai/openai-python/blob/main/chatml.md "
                "for information on how messages are converted to tokens."
            )

    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")

    num_tokens = 3  # Prime with assistant
    for message in messages:
        num_tokens += config.per_message
        if message.content is not None:
            num_tokens += len(encoding.encode(message.content))
        if message.role == "user":
            num_tokens += config.per_name

    return num_tokens


def info(msg: str) -> None:
    wandb.termlog(msg)


def error(msg: str) -> None:
    wandb.termerror(msg)


def warn(msg: str) -> None:
    wandb.termwarn(msg)


@contextmanager
def error_handler() -> Generator[None, None, None]:
    try:
        yield
    except Exception as e:
        print(f"problem with callback: {e}")


def bind_params(func: Callable, *args: Any, **kwargs: Any) -> Dict[str, Any]:
    sig = inspect.signature(func)
    return sig.bind_partial(*args, **kwargs).arguments
