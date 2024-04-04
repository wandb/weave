import inspect
from math import ceil
from contextlib import contextmanager
from typing import Any, Callable, Dict, Generator, Iterator, Optional, TypeVar

import tiktoken
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk, Choice
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


def token_usage(
    input_messages: List[dict], response_choices: list[Choice]
) -> Optional[CompletionUsage]:
    try:
        prompt_tokens = num_tokens_from_messages(input_messages)
        completion_tokens = 0
        for choice in response_choices:
            message = choice.message
            completion_tokens += num_tokens_from_messages([message.model_dump()])

        total_tokens = prompt_tokens + completion_tokens
        return CompletionUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
    except Exception as e:
        print(f"Error: unable to calculate token usage {e}")
        return None


def calculate_image_tokens(width: int, height: int):
    if width > 2048 or height > 2048:
        aspect_ratio = width / height
        if aspect_ratio > 1:
            width, height = 2048, int(2048 / aspect_ratio)
        else:
            width, height = int(2048 * aspect_ratio), 2048

    if width >= height and height > 768:
        width, height = int((768 / height) * width), 768
    elif height > width and width > 768:
        width, height = 768, int((768 / width) * height)

    tiles_width = ceil(width / 512)
    tiles_height = ceil(height / 512)
    total_tokens = 85 + 170 * (tiles_width * tiles_height)

    return total_tokens

def num_tokens_from_messages(
    messages: List[dict], model: str = "gpt-3.5-turbo-0613"
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
        if message.get("content") is not None:
            if isinstance(message["content"], list):
                for content in message["content"]:
                    if content.get("type") == "text" and isinstance(content.get("text"), str):
                        num_tokens += len(encoding.encode(content["text"]))
                    elif content.get("type") == "image_url":
                        # TODO: actually extract the width and height of the image, just assuming 1024 now
                        num_tokens += calculate_image_tokens(1024, 1024)
                    else:
                        print(f"Warning: couldn't calculate tokens from content with type {type(content.get('type'))}")
            elif isinstance(message["content"], str):
                num_tokens += len(encoding.encode(message["content"]))
            else:
                print(f"Warning: couldn't calculate tokens from content with type {type(message['content'])}")            
        if message["role"] == "user":
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
