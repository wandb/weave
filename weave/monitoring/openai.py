import typing
import openai
from openai import util as openai_util
import functools
import tiktoken

from . import monitor


def _delta_update(value: dict, delta: dict) -> dict:
    """
    Update the 'value' dictionary with the 'delta' dictionary.

    :param value: The original dictionary to be updated.
    :param delta: The dictionary containing changes to be applied.
    :return: The updated dictionary.
    """
    for k, v in delta.items():
        if k not in value:
            value[k] = v
        elif isinstance(v, dict):
            _delta_update(value[k], v)
        elif v is None:
            value[k] = None
        elif isinstance(v, str):
            if value[k] is not None:
                value[k] += v
            else:
                value[k] = v
        else:
            raise ValueError("Unsupported type in delta")
    return value


def elide_api_key(api_key: str) -> str:
    return api_key[:3] + "..." + api_key[-4:]


def openai_create_preprocess(span: monitor.SpanWithInputs) -> None:
    # The openai signature's are always args/kwargs, but the actual
    # parameters for e.g. ChatCompletion.create can only be passed in kwargs.
    # Generic parameters like api_key can be passed as args.
    # TODO: handle api_key in args
    span.inputs = span.inputs["kwargs"]

    api_key = None
    try:
        api_key = span.inputs.pop("api_key")
    except KeyError:
        api_key = openai_util.default_api_key()
    span.attributes["api_key"] = elide_api_key(api_key)

    if span.inputs.get("stream"):
        span.disable_autoclose()


def process_chat_completion_choice(
    existing_choices: list[typing.Any], update_choices: list[typing.Any]
) -> list[typing.Any]:
    for choice_update in update_choices:
        index = choice_update["index"]
        if index > len(existing_choices) - 1:
            for i in range(len(existing_choices), index + 1):
                existing_choices.append(
                    {"index": i, "message": {}, "finish_reason": None}
                )
        if "delta" in choice_update:
            existing_choices[index]["message"] = _delta_update(
                existing_choices[index]["message"], choice_update["delta"]
            )
        if "finish_reason" in choice_update:
            existing_choices[index]["finish_reason"] = choice_update["finish_reason"]
    return existing_choices


def process_completion_choice(
    existing_choices: list[typing.Any], update_choices: list[typing.Any]
) -> list[typing.Any]:
    for choice_update in update_choices:
        index = choice_update["index"]
        if index > len(existing_choices) - 1:
            for i in range(len(existing_choices), index + 1):
                existing_choices.append({"index": i, "text": "", "finish_reason": None})
        existing_choices[index]["text"] = (
            existing_choices[index]["text"] + choice_update["text"]
        )
        if "finish_reason" in choice_update:
            existing_choices[index]["finish_reason"] = choice_update["finish_reason"]
    return existing_choices


def count_chat_completion_tokens(
    span: monitor.SpanWithInputsAndOutput, record: dict
) -> dict:
    summary = {}
    encoding = tiktoken.encoding_for_model(record["model"])

    prompt_tokens = (encoding.encode(m["content"]) for m in span.inputs["messages"])
    summary["prompt_tokens"] = sum(len(c) for c in prompt_tokens)

    completion_tokens = (
        encoding.encode(c["message"]["content"]) for c in record["choices"]
    )
    summary["completion_tokens"] = sum(len(c) for c in completion_tokens)
    summary["total_tokens"] = summary["prompt_tokens"] + summary["completion_tokens"]
    return summary


def count_completion_tokens(
    span: monitor.SpanWithInputsAndOutput, record: dict
) -> dict:
    summary = {}
    encoding = tiktoken.encoding_for_model(record["model"])

    prompt_tokens = encoding.encode(span.inputs["prompt"])
    summary["prompt_tokens"] = len(prompt_tokens)

    completion_tokens = 0
    for c in record["choices"]:
        completion_tokens += len(encoding.encode(c["text"]))
    summary["completion_tokens"] = completion_tokens
    summary["total_tokens"] = summary["prompt_tokens"] + summary["completion_tokens"]
    return summary


def openai_create_postprocess(
    process_choice_fn: typing.Callable, count_token_fn: typing.Callable
) -> typing.Callable:
    def post_process(span: monitor.SpanWithInputsAndOutput) -> typing.Generator:
        def wrapped_gen(gen: typing.Generator) -> typing.Generator:
            # TODO: this needs to compute token usage.
            record = None
            for item in gen:
                if record is None:
                    record = {
                        "id": item["id"],
                        "object": item["object"],
                        "created": item["created"],
                        "model": item["model"],
                        "choices": [],
                    }
                record["choices"] = process_choice_fn(
                    record["choices"], item["choices"]
                )
                yield item
            if record is not None:
                span.summary.update(count_token_fn(span, record))

            span.output = record
            span.close()

        if span.inputs.get("stream"):
            return wrapped_gen(span.output)

        # move usage to summary
        usage = span.output.pop("usage")
        for k, v in usage.items():
            span.summary[k] = v

        return span.output

    return post_process


mon = monitor.default_monitor()


def monitored_create(
    openai_func: typing.Callable,
    process_choice_fn: typing.Callable,
    count_token_fn: typing.Callable,
) -> typing.Callable:
    return mon.trace(
        preprocess=openai_create_preprocess,
        postprocess=openai_create_postprocess(process_choice_fn, count_token_fn),
    )(openai_func)


def message_from_stream(stream: typing.Generator) -> typing.Any:
    """Helper to extract a printable streaming message from an OpenAI stream response."""
    # TODO: print role.
    # TODO: print function call responses
    cur_index = 0
    for record in stream:
        if "choices" in record:
            for choice_update in record["choices"]:
                if choice_update["index"] == cur_index:
                    delta = choice_update["delta"]
                    if "content" in delta:
                        yield delta["content"]
                else:
                    yield "\n\nNEXT RESPONSE:\n\n"


class ChatCompletion:
    @staticmethod
    def create(**kwargs: typing.Any) -> typing.Any:
        return monitored_create(
            openai.ChatCompletion.create,
            process_chat_completion_choice,
            count_chat_completion_tokens,
        )(**kwargs)


class Completion:
    @staticmethod
    def create(**kwargs: typing.Any) -> typing.Any:
        return monitored_create(
            openai.Completion.create, process_completion_choice, count_completion_tokens
        )(**kwargs)
