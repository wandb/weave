import copy
from collections.abc import Callable
from datetime import datetime
from typing import Any

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


def _insert_event(events_tree: dict[str, Any], name: str, attributes: dict[str, Any]) -> None:
    """Insert an OTEL span event into the nested events tree."""
    parts = name.split(".")
    current = events_tree
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    leaf = parts[-1]
    existing = current.get(leaf)
    if existing is None:
        current[leaf] = [copy.deepcopy(attributes)]
    elif isinstance(existing, list):
        existing.append(copy.deepcopy(attributes))
    elif isinstance(existing, dict):
        existing.setdefault("__events__", []).append(copy.deepcopy(attributes))
    else:
        current[leaf] = [copy.deepcopy(attributes)]


def _build_events_tree(events: list[SpanEvent] | None) -> dict[str, Any]:
    """Convert OTEL span events into a nested dict for attribute lookups."""
    if not events:
        return {}

    events_tree: dict[str, Any] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        name = event.get("name")
        event_attributes = event.get("attributes")
        if not name or not isinstance(event_attributes, dict):
            continue
        _insert_event(events_tree, name, event_attributes)

    if not events_tree:
        return {}

    return {"events": events_tree}


def parse_weave_values(
    attributes: dict[str, Any],
    key_mapping: list[str]
    | dict[str, list[str]]
    | list[tuple[str, Callable[..., Any]]]
    | dict[str, list[tuple[str, Callable[..., Any]]]],
    events: list[SpanEvent] | None = None,
) -> dict[str, Any]:
    result = {}
    events_tree = _build_events_tree(events) if events else None

    def _get_value(key: str) -> Any:
        value = get_attribute(attributes, key)
        if value is None and events_tree:
            value = get_attribute(events_tree, key)
        return value

    # If list use the attribute as the key - Prevents synthetic attributes under input and output

    if isinstance(key_mapping, list):
        for attribute_key_or_tuple in key_mapping:
            handler = None
            if isinstance(attribute_key_or_tuple, tuple):
                attribute_key, handler = attribute_key_or_tuple
            else:
                attribute_key = attribute_key_or_tuple
            value = _get_value(attribute_key)
            if value is not None:
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

            value = _get_value(attribute_key)
            if value is not None:
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
        usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
    return usage


# Some providers (e.g. Bedrock agents) encode inputs inside span events
def get_weave_inputs(events: list[SpanEvent], attributes: dict[str, Any]) -> dict[str, Any]:
    return parse_weave_values(attributes, INPUT_KEYS, events)


# Some providers (e.g. Bedrock agents) encode outputs inside span events
def get_weave_outputs(events: list[SpanEvent], attributes: dict[str, Any]) -> dict[str, Any]:
    return parse_weave_values(attributes, OUTPUT_KEYS, events)


# Custom attributes for weave to enable setting fields like wb_user_id otherwise unavailable in OTEL Traces
def get_wandb_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    return parse_weave_values(attributes, WB_KEYS)


# Pass events here even though they are unused because some libraries put input in event attributes
def get_span_overrides(attributes: dict[str, Any]) -> dict[str, Any]:
    return parse_weave_values(attributes, SPAN_OVERRIDES)
