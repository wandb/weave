import json
from collections.abc import Iterable
from datetime import datetime
from enum import Enum
from typing import Any, Union
from uuid import UUID

from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue

from weave.trace_server.opentelemetry.helpers import (
    get_attribute,
    to_json_serializable,
)

from weave.trace_server.opentelemetry.constants import (
    ATTRIBUTE_KEYS,
    INPUT_KEYS,
    OUTPUT_KEYS,
    USAGE_KEYS,
    WB_KEYS,
    KEY_HANDLERS
)

class SpanEvent(dict):
    name: str
    timestamp: datetime
    attributes: dict[str, Any]
    dropped_attributes_count: int


def parse_weave_values(
    attributes: dict[str, Any],
    key_mapping: Union[list[str], dict[str, list[str]]],
) -> dict[str, Any]:
    result = {}
    # If list use the attribute as the key - Prevents synthetic attributes under input and output
    if isinstance(key_mapping, list):
        for attribute_key in key_mapping:
            value = get_attribute(attributes, attribute_key)
            if value:
                if attribute_key in KEY_HANDLERS:
                    try:
                        value = KEY_HANDLERS[attribute_key](value)
                    except:
                        pass
                result[attribute_key] = value
                break
        return result

    # If dict, unpack to associate all nested keys with their parent
    for key, attribute_key_list in key_mapping.items():
        for attribute_key in attribute_key_list:
            value = get_attribute(attributes, attribute_key)
            if value:
                if attribute_key in KEY_HANDLERS:
                    try:
                        value = KEY_HANDLERS[attribute_key](value)
                    except:
                        pass
                result[key] = value
                break
    return to_json_serializable(result)


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
