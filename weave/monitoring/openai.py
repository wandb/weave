import typing
import openai

from . import monitor


def delta_update(value: dict, delta: dict) -> dict:
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
            delta_update(value[k], v)
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


def openai_create_preprocess(span: monitor.SpanWithInputs) -> None:
    span.inputs = span.inputs["kwargs"]
    if span.inputs.get("stream"):
        span.disable_autoclose()


def openai_create_postprocess(span: monitor.SpanWithInputsAndOutput) -> typing.Any:
    def wrapped_gen(gen: typing.Generator) -> typing.Generator:
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
            choices = record["choices"]
            for choice_update in item["choices"]:
                index = choice_update["index"]
                if index > len(choices) - 1:
                    for i in range(len(choices), index + 1):
                        choices.append(
                            {"index": i, "message": {}, "finish_reason": None}
                        )
                if "delta" in choice_update:
                    choices[index]["message"] = delta_update(
                        choices[index]["message"], choice_update["delta"]
                    )
                if "finish_reason" in choice_update:
                    choices[index]["finish_reason"] = choice_update["finish_reason"]
            yield item

        span.output = record
        span.close()

    if span.inputs.get("stream"):
        return wrapped_gen(span.output)
    return span.output


mon = monitor.default_monitor()

monitored_create = mon.trace(
    preprocess=openai_create_preprocess, postprocess=openai_create_postprocess
)(openai.ChatCompletion.create)


class ChatCompletion:
    @staticmethod
    def create(**kwargs: typing.Any) -> typing.Any:
        return monitored_create(**kwargs)
