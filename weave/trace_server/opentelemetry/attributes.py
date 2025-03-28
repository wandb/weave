import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Iterator, Iterable
from uuid import UUID
from openinference.semconv import trace
from openinference.semconv.trace import DocumentAttributes, SpanAttributes
from opentelemetry.proto.common.v1.common_pb2 import (AnyValue, KeyValue)

DOCUMENT_METADATA = DocumentAttributes.DOCUMENT_METADATA
LLM_PROMPT_TEMPLATE_VARIABLES = SpanAttributes.LLM_PROMPT_TEMPLATE_VARIABLES
METADATA = SpanAttributes.METADATA
TOOL_PARAMETERS = SpanAttributes.TOOL_PARAMETERS
OUTPUT_MESSAGES = SpanAttributes.LLM_OUTPUT_MESSAGES
INPUT_MESSAGES = SpanAttributes.LLM_INPUT_MESSAGES

# Attributes interpreted as JSON strings during ingestion
# Currently only maps openinference attributes
# JSON_ATTRIBUTES = (
#     DOCUMENT_METADATA,
#     LLM_PROMPT_TEMPLATE_VARIABLES,
#     METADATA,
#     TOOL_PARAMETERS,
#     OUTPUT_MESSAGES,
#     INPUT_MESSAGES,
# )

JSON_ATTRIBUTES = [
    "input.value",
    "output.value",
]

def load_json_strings(key_values: Iterable[tuple[str, Any]]) -> Iterator[tuple[str, Any]]:
    for key, value in key_values:
        if key.endswith(JSON_ATTRIBUTES):
            try:
                dict_value = json.loads(value)
            except Exception:
                yield key, value
            else:
                if dict_value:
                    yield key, dict_value
        else:
            yield key, value
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
    elif hasattr(value, '__dataclass_fields__'):  # Handle dataclasses
        return {k: to_json_serializable(getattr(value, k)) for k in value.__dataclass_fields__}
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
    if value.HasField('string_value'):
        return value.string_value
    elif value.HasField('bool_value'):
        return value.bool_value
    elif value.HasField('int_value'):
        return value.int_value
    elif value.HasField('double_value'):
        return value.double_value
    elif value.HasField('array_value'):
        return [resolve_pb_any_value(v) for v in value.array_value.values]
    elif value.HasField('kvlist_value'):
        return dict(resolve_pb_key_value(kv) for kv in value.kvlist_value.values)
    elif value.HasField('bytes_value'):
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


def _get_value_from_nested_dict(d: Dict[str, Any], key: str) -> Any:
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


def _set_value_in_nested_dict(d: Dict[str, Any], key: str, value: Any) -> None:
    """Set a value in a nested dictionary using a dot-separated key."""
    if "." not in key:
        d[key] = value
        return

    parts = key.split(".")
    current = d
    for i, part in enumerate(parts[:-1]):
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value

def _convert_numeric_keys_to_list(obj: Dict[str, Any]) -> Union[Dict[str, Any], List[Any]]:
    """
    Convert dictionaries with numeric-only keys to lists.

    If all keys in a dictionary are numeric strings (0, 1, 2, ...), 
    convert it to a list. Recursively processes nested dictionaries.
    """
    if not isinstance(obj, dict):
        return obj

    # Process all nested dictionaries first
    for key, value in obj.items():
        if isinstance(value, dict):
            obj[key] = _convert_numeric_keys_to_list(value)

    # Check if all keys are numeric strings and contiguous starting from 0
    try:
        keys = sorted(int(k) for k in obj.keys())
        if keys == list(range(len(keys))) and all(isinstance(k, str) and k.isdigit() for k in obj.keys()):
            # Convert to list, preserving order
            return [obj[str(i)] for i in range(len(keys))]
    except (ValueError, TypeError):
        # Not all keys are numeric
        pass

    return obj

def expand_attributes(kv: Iterable[tuple[str, str]], json_attributes: List[str] = []) -> Union[Dict[str, Any], List[Any]]:
    """
    Expand a flattened JSON attributes file into a nested Python dictionary.

    Args:
        file_path: Path to the JSON file with flattened attributes
        json_attributes: List of attributes to parse as JSON strings

    Returns:
        A nested Python dictionary
    """

    # Read the JSON file

    # Create the result dictionary
    result: Union[Dict[str, Any], List[Any]] = {}

    # Process each key-value pair
    for flat_key, value in kv:
        # Check if the value should be parsed as JSON
        should_parse_as_json = any(
            flat_key.endswith(attr) or flat_key == attr 
            for attr in json_attributes
        )

        if should_parse_as_json and isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                # If JSON parsing fails, keep the original value
                pass

        # Add the nested key to the result
        _set_value_in_nested_dict(result, flat_key, value)

    # Convert dictionaries with numeric keys to lists
    result = _convert_numeric_keys_to_list(result)

    return result

def flatten_attributes(data: Dict[str, Any], json_attributes: List[str] = []) -> Dict[str, Any]:
    """
    Flatten a nested Python dictionary into a flat dictionary with dot-separated keys.

    Args:
        data: Nested Python dictionary to flatten
        json_attributes: List of attributes to stringify as JSON

    Returns:
        A flattened dictionary with dot-separated keys
    """
    result: Dict[str, Any] = {}

    def _flatten(obj: Union[Dict[str, Any], List[Any]], prefix: str = "") -> None:
        # Check if the entire object should be stringified as JSON
        should_stringify_entire_obj = any(
            prefix.rstrip('.') == attr for attr in json_attributes
        )

        if should_stringify_entire_obj:
            result[prefix.rstrip('.')] = json.dumps(obj)
            return

        if isinstance(obj, dict):
            for key, value in obj.items():
                new_key = f"{prefix}{key}" if prefix else key

                # Check if this exact key's value should be stringified as JSON
                should_stringify_as_json = any(
                    new_key == attr for attr in json_attributes
                )

                if (isinstance(value, dict) or isinstance(value, list)) and not should_stringify_as_json:
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

                if (isinstance(item, dict) or isinstance(item, list)) and not should_stringify_as_json:
                    # Recursively flatten nested dictionaries or lists
                    _flatten(item, f"{new_key}.")
                else:
                    # If the item matches a JSON attribute, stringify it
                    if should_stringify_as_json and not isinstance(item, str):
                        item = json.dumps(item)
                    result[new_key] = item

    _flatten(data)
    return result


def get_attribute(data: Dict[str, Any], key: str) -> Any:
    """
    Get the value of a nested attribute from either a nested or flattened dictionary.

    Args:
        data: Dictionary to get value from
        key: Dot-separated key to get

    Returns:
        The value at the specified key or None if not found
    """
    # Check if it's a flat dictionary
    if key in data:
        return data[key]

    # Try to get from nested structure
    return _get_value_from_nested_dict(data, key)


def unflatten_key_values(key_values: Iterable[KeyValue]) -> Union[Dict[str, Any], List[Any]]:
    """
    Transform a list of KeyValue pairs into a nested dictionary structure.

    Args:
        key_values: An iterable of KeyValue protobuf messages
        separator: The character used to separate nested keys (default: '.')

    Returns:
        A nested dictionary where keys are split by the separator and digit keys
        are treated as array indices.

    Example:
        Input: [("llm.token_count.completion", 123)]
        Output: {"llm": {"token_count": {"completion": 123}}}

        Input: [
            ("retrieval.documents.0.document.content", 'A'),
            ("retrieval.documents.1.document.content", 'B')
        ]
        Output: {
            "retrieval": {
                "documents": [
                    {"document": {"content": "A"}},
                    {"document": {"content": "B"}}
                ]
            }
        }
    """
    iterator = map(lambda kv: (kv.key, resolve_pb_any_value(kv.value)), key_values)
    return expand_attributes(iterator, json_attributes=JSON_ATTRIBUTES)

# # Example usage
# if __name__ == "__main__":
#     # Example of expanding a flattened JSON file
#     expanded = expand_attributes("example.json")
#     print("Expanded attributes:")
#     print(json.dumps(expanded, indent=2))
#
#     # Example of flattening a nested dictionary
#     flattened = flatten_attributes(expanded)
#     print("\nFlattened attributes:")
#     print(json.dumps(flattened, indent=2))
#
#     # Example of getting values
#     print("\nGetting values:")
#     print(f"LLM provider: {get_attribute(expanded, 'llm.provider')}")
#     print(f"Input value model: {get_attribute(expanded, 'input.value.model')}")
