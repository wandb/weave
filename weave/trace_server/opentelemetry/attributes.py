from datetime import datetime
from typing import Any, Callable, Union

from weave.trace_server.opentelemetry.constants import (
    ATTRIBUTE_KEYS,
    INPUT_KEYS,
    OUTPUT_KEYS,
    SPAN_OVERRIDES,
    USAGE_KEYS,
    WB_KEYS,
)
from weave.trace_server.opentelemetry.helpers import (
    get_attribute,
    to_json_serializable,
    try_convert_numeric_keys_to_list,
)


class SpanEvent(dict):
    name: str
    timestamp: datetime
    attributes: dict[str, Any]
    dropped_attributes_count: int


def parse_weave_values(
    attributes: dict[str, Any],
    key_mapping: Union[
        list[str],
        dict[str, list[str]],
        list[tuple[str, Callable[..., Any]]],
        dict[str, list[tuple[str, Callable[..., Any]]]],
    ],
) -> dict[str, Any]:
    result = {}
    # If list use the attribute as the key - Prevents synthetic attributes under input and output

    if isinstance(key_mapping, list):
        for attribute_key_or_tuple in key_mapping:
            handler = None
            if isinstance(attribute_key_or_tuple, tuple):
                attribute_key, handler = attribute_key_or_tuple
            else:
                attribute_key = attribute_key_or_tuple
            value = get_attribute(attributes, attribute_key)
            if value:
                # Handler should never raise - Always use a try in handler and default to passed in value
                if handler:
                    value = handler(value)
                result[attribute_key] = value
                break
        if result != {}:
            to_json_serializable(try_convert_numeric_keys_to_list(result))
        return result

    # If dict, unpack to associate all nested keys with their parent
    for key, attribute_key_list in key_mapping.items():
        for attribute_key_or_tuple in attribute_key_list:
            handler = None
            if isinstance(attribute_key_or_tuple, tuple):
                attribute_key, handler = attribute_key_or_tuple
            else:
                attribute_key = attribute_key_or_tuple

            value = get_attribute(attributes, attribute_key)
            if value:
                if handler:
                    # Handler should never raise - Always use a try in handler and default to passed in value
                    value = handler(value)
                result[key] = value
                break

    # Prevent empty dict from becoming empty list
    if result != {}:
        to_json_serializable(try_convert_numeric_keys_to_list(result))
    return result


def get_weave_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    value = parse_weave_values(attributes, ATTRIBUTE_KEYS)
    return value


def get_weave_usage(attributes: dict[str, Any]) -> dict[str, Any]:
    usage = parse_weave_values(attributes, USAGE_KEYS)
    if (
        "prompt_tokens" in usage
        and "completion_tokens" in usage
        and "total_tokens" not in usage
        and isinstance(usage["prompt_tokens"], int)
        and isinstance(usage["completion_tokens"], int)
    ):
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
    if (
        "input_tokens" in usage
        and "output_tokens" in usage
        and "total_tokens" not in usage
        and isinstance(usage["input_tokens"], int)
        and isinstance(usage["output_tokens"], int)
    ):
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
    return usage


# Pass events here even though they are unused because some libraries put input in event attribtes
def get_weave_inputs(_: list[SpanEvent], attributes: dict[str, Any]) -> dict[str, Any]:
    return parse_weave_values(attributes, INPUT_KEYS)


# Pass events here even though they are unused because some libraries put output in event attribtes
def get_weave_outputs(_: list[SpanEvent], attributes: dict[str, Any]) -> dict[str, Any]:
    return parse_weave_values(attributes, OUTPUT_KEYS)


# Custom attributes for weave to enable setting fields like wb_user_id otherwise unavailable in OTEL Traces
def get_wandb_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    return parse_weave_values(attributes, WB_KEYS)


# Pass events here even though they are unused because some libraries put input in event attribtes
def get_span_overrides(attributes: dict[str, Any]) -> dict[str, Any]:
    return parse_weave_values(attributes, SPAN_OVERRIDES)
