import json
from collections.abc import Iterable
from datetime import datetime
from enum import Enum
from typing import Any, Union
from uuid import UUID

from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue

from weave.trace_server.opentelemetry.constants import (
    ATTRIBUTE_KEYS,
    INPUT_KEYS,
    OUTPUT_KEYS,
    USAGE_KEYS,
)


def to_json_serializable(value: Any) -> Any:
    """
    Transform common data types into JSON-serializable values.

    Args:
        value: Any value that needs to be converted to JSON-serializable format

    Returns:
        A JSON-serializable version of the input value

    Raises:
        ValueError: If the value type is not supported for JSON serialization
    """
    if value is None:
        return None
    elif isinstance(value, (str, int, float, bool)):
        return value
    elif isinstance(value, (list, tuple)):
        return [to_json_serializable(item) for item in value]
    elif isinstance(value, dict):
        return {str(k): to_json_serializable(v) for k, v in value.items()}
    elif isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, UUID):
        return str(value)
    elif isinstance(value, Enum):
        return value.value
    elif hasattr(value, "__dataclass_fields__"):  # Handle dataclasses
        return {
            k: to_json_serializable(getattr(value, k))
            for k in value.__dataclass_fields__
        }
    else:
        raise ValueError(f"Unsupported type for JSON serialization: {type(value)}")


def resolve_pb_any_value(value: AnyValue) -> Any:
    """
    Resolve the value field of an AnyValue protobuf message.

    Args:
        value: An AnyValue protobuf message

    Returns:
        The resolved value as a Python type

    Raises:
        ValueError: If the AnyValue has no value set or has an unsupported type
    """
    if value.HasField("string_value"):
        return value.string_value
    elif value.HasField("bool_value"):
        return value.bool_value
    elif value.HasField("int_value"):
        return value.int_value
    elif value.HasField("double_value"):
        return value.double_value
    elif value.HasField("array_value"):
        return [resolve_pb_any_value(v) for v in value.array_value.values]
    elif value.HasField("kvlist_value"):
        return dict(resolve_pb_key_value(kv) for kv in value.kvlist_value.values)
    elif value.HasField("bytes_value"):
        return value.bytes_value
    else:
        raise ValueError("AnyValue has no value set")


def resolve_pb_key_value(key_value: KeyValue) -> tuple[str, Any]:
    """
    Resolve a KeyValue protobuf message into a tuple of key and value.

    Args:
        key_value: A KeyValue protobuf message

    Returns:
        A tuple containing the key and resolved value

    Raises:
        ValueError: If the KeyValue has no value set or has an unsupported type
    """
    return (key_value.key, resolve_pb_any_value(key_value.value))


def _get_value_from_nested_dict(d: dict[str, Any], key: str) -> Any:
    """Get a value from a nested dictionary using a dot-separated key."""
    if "." not in key:
        return d.get(key)

    parts = key.split(".")
    current = d
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_value_in_nested_dict(d: dict[str, Any], key: str, value: Any) -> None:
    """Set a value in a nested dictionary using a dot-separated key."""
    if "." not in key:
        d[key] = value
        return

    parts = key.split(".")
    current = d
    for _, part in enumerate(parts[:-1]):
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def convert_numeric_keys_to_list(
    obj: dict[str, Any],
) -> Union[dict[str, Any], list[Any]]:
    """
    Convert dictionaries with numeric-only keys to lists.

    If all keys in a dictionary are numeric strings (0, 1, 2, ...),
    convert it to a list. Recursively processes nested dictionaries.
    """
    # Process all nested dictionaries first
    for key, value in obj.items():
        if isinstance(value, dict):
            obj[key] = convert_numeric_keys_to_list(value)

    # Check if all keys are numeric strings and contiguous starting from 0
    try:
        keys = sorted(int(k) for k in obj.keys())
        if keys == list(range(len(keys))) and all(
            isinstance(k, str) and k.isdigit() for k in obj.keys()
        ):
            # Convert to list, preserving order
            return [obj[str(i)] for i in range(len(keys))]
    except (ValueError, TypeError):
        # Not all keys are numeric
        pass

    return obj


def expand_attributes(kv: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    """
    Expand a flattened JSON attributes file into a nested Python dictionary.

    Args:
        file_path: Path to the JSON file with flattened attributes
        json_attributes: list of attributes to parse as JSON strings

    Returns:
        A nested Python dictionary
    """
    # Read the JSON file

    # Create the result dictionary
    result_dict: dict[str, Any] = {}

    # Process each key-value pair
    for flat_key, value in kv:
        # Weave expects JSON strings to be loaded to display properly, so just try and load every string as json
        if isinstance(value, str) and (value.startswith("[") or value.startswith("{")):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                # If JSON parsing fails, keep the original value
                pass

        # Add the nested key to the result
        _set_value_in_nested_dict(result_dict, flat_key, value)

    # Convert dictionaries with numeric keys to lists
    return result_dict


def flatten_attributes(
    data: dict[str, Any], json_attributes: list[str] = []
) -> dict[str, Any]:
    """
    Flatten a nested Python dictionary into a flat dictionary with dot-separated keys.

    Args:
        data: Nested Python dictionary to flatten
        json_attributes: list of attributes to stringify as JSON

    Returns:
        A flattened dictionary with dot-separated keys
    """
    result: dict[str, Any] = {}

    def _flatten(obj: Union[dict[str, Any], list[Any]], prefix: str = "") -> None:
        # Check if the entire object should be stringified as JSON
        should_stringify_entire_obj = any(
            prefix.rstrip(".") == attr for attr in json_attributes
        )

        if should_stringify_entire_obj:
            result[prefix.rstrip(".")] = json.dumps(obj)
            return

        if isinstance(obj, dict):
            for key, value in obj.items():
                new_key = f"{prefix}{key}" if prefix else key

                # Check if this exact key's value should be stringified as JSON
                should_stringify_as_json = any(
                    new_key == attr for attr in json_attributes
                )

                if (
                    isinstance(value, dict) or isinstance(value, list)
                ) and not should_stringify_as_json:
                    # Recursively flatten nested dictionaries or lists
                    _flatten(value, f"{new_key}.")
                else:
                    # If the value matches a JSON attribute, stringify it
                    if should_stringify_as_json and not isinstance(value, str):
                        value = json.dumps(value)
                    result[new_key] = value
        elif isinstance(obj, list):
            # Handle lists by using numeric indices as keys
            for i, item in enumerate(obj):
                new_key = f"{prefix}{i}"

                # Check if this exact key's value should be stringified as JSON
                should_stringify_as_json = any(
                    new_key == attr for attr in json_attributes
                )

                if (
                    isinstance(item, dict) or isinstance(item, list)
                ) and not should_stringify_as_json:
                    # Recursively flatten nested dictionaries or lists
                    _flatten(item, f"{new_key}.")
                else:
                    # If the item matches a JSON attribute, stringify it
                    if should_stringify_as_json and not isinstance(item, str):
                        item = json.dumps(item)
                    result[new_key] = item

    _flatten(data)
    return result


def get_attribute(data: dict[str, Any], key: str) -> Any:
    """
    Get the value of a nested attribute from either a nested or flattened dictionary.

    Args:
        data: dictionary to get value from
        key: Dot-separated key to get

    Returns:
        The value at the specified key or None if not found
    """
    # Check if it's a flat dictionary
    if key in data:
        return data[key]

    # Try to get from nested structure
    return _get_value_from_nested_dict(data, key)


def unflatten_key_values(
    key_values: Iterable[KeyValue],
) -> dict[str, Any]:
    """
    Transform a list of KeyValue pairs into a nested dictionary structure.

    Args:
        key_values: An iterable of KeyValue protobuf messages
        separator: The character used to separate nested keys (default: '.')

    Returns:
        A nested dictionary where keys are split by the separator

    Example:
        Input: [("llm.token_count.completion", 123)]
        Output: {"llm": {"token_count": {"completion": 123}}}

        Input: [
            ("retrieval.documents.0.document.content", 'A'),
            ("retrieval.documents.1.document.content", 'B')
        ]
        Output: {
            "retrieval": {
                "documents": {
                    "0": {"document": {"content": "A"}},
                    "1": {"document": {"content": "B"}}
                }
            }
        }
    """
    iterator = ((kv.key, resolve_pb_any_value(kv.value)) for kv in key_values)
    return expand_attributes(iterator)


def try_parse_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except:
            pass
    return value


def try_parse_int(value: Any) -> Any:
    try:
        value = int(value)
    except:
        pass
    return value


KEY_HANDLERS = {
    "gen_ai.prompt": convert_numeric_keys_to_list,
    "gen_ai.completion": convert_numeric_keys_to_list,
    "gen_ai.usage.prompt_tokens": try_parse_int,
}

for key in (
    USAGE_KEYS["prompt_tokens"]
    + USAGE_KEYS["completion_tokens"]
    + USAGE_KEYS["total_tokens"]
):
    KEY_HANDLERS[key] = try_parse_int


class SpanEvent(dict):
    name: str
    timestamp: datetime
    attributes: dict[str, Any]
    dropped_attributes_count: int


def parse_weave_values(
    attributes: dict[str, Any],
    key_mapping: Union[list[str], dict[str, list[str]]],
) -> dict[str, Any]:
    if isinstance(key_mapping, list):
        key_mapping = {key: [key] for key in key_mapping}
    result = {}
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
    ):
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
    if (
        "input_tokens" in usage
        and "output_tokens" in usage
        and "total_tokens" not in usage
    ):
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
    return usage


def get_weave_inputs(_: list[SpanEvent], attributes: dict[str, Any]) -> dict[str, Any]:
    return parse_weave_values(attributes, INPUT_KEYS)


def get_weave_outputs(_: list[SpanEvent], attributes: dict[str, Any]) -> dict[str, Any]:
    return parse_weave_values(attributes, OUTPUT_KEYS)
