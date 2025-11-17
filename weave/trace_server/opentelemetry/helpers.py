import base64
import json
import math
import re
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue


class AttributePathConflictError(TypeError):
    def __init__(
        self,
        *,
        parent_key: str,
        attempted_subkey: str,
        existing_type: type,
        message: str | None = None,
    ) -> None:
        if message is None:
            message = (
                "Invalid attribute structure: cannot set subkey '"
                f"{attempted_subkey}' under parent key '{parent_key}' because it "
                f"is already a {existing_type.__name__}. "
                "Attributes must form a valid tree structure."
            )
        super().__init__(message)
        self.parent_key = parent_key
        self.attempted_subkey = attempted_subkey
        self.existing_type = existing_type


def to_json_serializable(value: Any) -> Any:
    # Transform common data types into JSON-serializable values.
    if value is None:
        return None
    elif isinstance(value, (str, bool)):
        return value
    elif isinstance(value, int):
        return value
    elif isinstance(value, float):
        # Handle special floats: NaN, inf, -inf
        if math.isnan(value) or math.isinf(value):
            return str(value)
        return value
    elif isinstance(value, (list, tuple)):
        return [to_json_serializable(item) for item in value]
    elif isinstance(value, dict):
        return {str(k): to_json_serializable(v) for k, v in value.items()}
    elif isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, date):  # date without time
        return value.isoformat()
    elif isinstance(value, time):  # time without date
        return value.isoformat()
    elif isinstance(value, timedelta):
        return value.total_seconds()
    elif isinstance(value, UUID):
        return str(value)
    elif isinstance(value, Enum):
        return value.value
    elif isinstance(value, Decimal):
        # Convert Decimal to float or str, depending on requirements.
        return float(value)
    elif isinstance(value, (set, frozenset)):
        return [to_json_serializable(item) for item in value]
    elif isinstance(value, complex):
        return {"real": value.real, "imag": value.imag}
    elif isinstance(value, (bytes, bytearray)):
        return base64.b64encode(value).decode("ascii")
    elif hasattr(value, "__dataclass_fields__"):
        return {
            k: to_json_serializable(getattr(value, k))
            for k in value.__dataclass_fields__
        }
    else:
        raise ValueError(f"Unsupported type for JSON serialization: {type(value)}")


def resolve_pb_any_value(value: AnyValue) -> Any:
    """Resolve the value field of an AnyValue protobuf message.

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
    """Resolve a KeyValue protobuf message into a tuple of key and value.

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
            if isinstance(current, list) and part.isdigit():
                part = int(part)
                current = current[part] if part < len(current) else None
                continue
            else:
                return None
        current = current[part]
    return current


def _validate_structure(d: dict[str, Any], key: str, value: Any) -> None:
    """Ensure setting `value` at dot-path `key` won't corrupt structure.

    Validation rules:
    - Disallow placing a primitive at a path that already contains a mapping
      (dict or list).
    - Disallow descending into a non-dict value for any parent segment.
    - Disallow overwriting an existing mapping at the leaf with a primitive
      when subkeys already exist for that path.
    """
    # Simple key (no nesting): prevent clobbering an existing mapping with a primitive
    if "." not in key:
        existing = d.get(key)
        if isinstance(existing, (dict, list)) and not isinstance(value, (dict, list)):
            raise AttributePathConflictError(
                parent_key=key,
                attempted_subkey="<root>",
                existing_type=type(existing),
                message=(
                    f"Invalid attribute structure: key '{key}' already has nested values, "
                    "but a non-object value was also provided. Do not send both '"
                    f"{key}' and '{key}.*' keys. Either: (1) remove the primitive '"
                    f"{key}', (2) move it under a different name (e.g. '{key}_value'), or "
                    f"(3) represent it as a field, e.g. '{key}.value'."
                ),
            )
        return

    # Nested key: validate traversal and leaf overwrite rules
    parts = key.split(".")
    current: Any = d
    for i, part in enumerate(parts[:-1]):
        # Build the dotted path for the current parent segment.
        # Example: key='a.b.c'
        #  - i=0 -> parts[:1] = ['a']   -> parent_path='a'
        #  - i=1 -> parts[:2] = ['a','b'] -> parent_path='a.b'
        # This is used to reference the parent key in conflict messages when
        # we detect that we must descend into a non-dict (primitive) value.
        parent_path = ".".join(parts[: i + 1])
        if part in current and not isinstance(current[part], dict):
            # We must descend, but parent is a primitive -> conflict
            raise AttributePathConflictError(
                parent_key=parent_path,
                attempted_subkey=parts[i + 1],
                existing_type=type(current[part]),
            )
        # Safe to continue (either missing or a dict); creation happens in setter
        if part in current:
            current = current[part]
        else:
            current = {}  # placeholder to advance logic without mutating

    # Leaf rule: prevent overwriting an existing mapping with a primitive
    parent = _get_value_from_nested_dict(d, ".".join(parts[:-1])) or {}
    if isinstance(parent, dict):
        last = parts[-1]
        existing_leaf = parent.get(last)
        if isinstance(existing_leaf, (dict, list)) and not isinstance(
            value, (dict, list)
        ):
            raise AttributePathConflictError(
                parent_key=".".join(parts),
                attempted_subkey="<root>",
                existing_type=type(existing_leaf),
                message=(
                    f"Invalid attribute structure: received both nested subkeys for '{'.'.join(parts)}' "
                    "and a non-object value for the same key. Do not send both '"
                    f"{'.'.join(parts)}' and '{'.'.join(parts)}.*'. Either keep only nested keys or "
                    f"use a different key for the primitive (e.g. '{'.'.join(parts)}_value')."
                ),
            )


def _set_value_in_nested_dict(d: dict[str, Any], key: str, value: Any) -> None:
    """Set a value in a nested dictionary using a dot-separated key."""
    _validate_structure(d, key, value)
    if "." not in key:
        d[key] = value
        return

    parts = key.split(".")
    current = d
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def convert_numeric_keys_to_list(
    obj: dict[str, Any],
) -> dict[str, Any] | list[Any]:
    """Convert dictionaries with numeric-only keys to lists.

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
    """Expand a flattened JSON attributes file into a nested Python dictionary.

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
    data: dict[str, Any], json_attributes: list[str] | None = None
) -> dict[str, Any]:
    """Flatten a nested Python dictionary into a flat dictionary with dot-separated keys.

    Args:
        data: Nested Python dictionary to flatten
        json_attributes: list of attributes to stringify as JSON

    Returns:
        A flattened dictionary with dot-separated keys
    """
    if json_attributes is None:
        json_attributes = []

    result: dict[str, Any] = {}

    def _flatten(obj: dict[str, Any] | list[Any], prefix: str = "") -> None:
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
    """Get the value of a nested attribute from either a nested or flattened dictionary.

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
    """Transform a list of KeyValue pairs into a nested dictionary structure.

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


def try_parse_int(value: Any) -> Any:
    try:
        value = int(value)
    except:
        pass
    return value


def try_convert_numeric_keys_to_list(value: Any) -> Any:
    if isinstance(value, dict):
        try:
            value = convert_numeric_keys_to_list(value)
        except:
            pass
    return value


def capture_parts(s: str, delimiters: list[str] | None = None) -> list[str]:
    """Split a string on multiple delimiters while preserving the delimiters in the result.

    This function splits a string using the specified delimiters and includes those
    delimiters in the resulting list. Empty strings are filtered out from the result.

    Args:
        s: The input string to split.
        delimiters: A list of delimiter strings to split on. Defaults to common delimiters.

    Returns:
        A list containing the parts of the split string, including the delimiters.
        If no splits occurred, returns the original string in a list.

    Example:
        >>> capture_parts("hello/world.txt")
        ['hello', '/', 'world', '.', 'txt']
    """
    if delimiters is None:
        delimiters = [",", ";", "|", " ", "/", "?", "."]

    # Escape special regex characters and join with | for regex alternation
    capture = "|".join(map(re.escape, delimiters))
    pattern = f"({(capture)})"

    # Use re.split with capturing groups to include the delimiters
    parts = re.split(pattern, s)

    # Filter out empty strings that might result from the split
    result = [part for part in parts if part != ""]

    result = list(filter(lambda x: len(x) > 0, parts))
    # If no split occurred, return the original string in a list
    if len(result) == 0:
        return [s]

    return result


def shorten_name(
    name: str, max_len: int, abbrv: str = "...", use_delimiter_in_abbr: bool = True
) -> str:
    """Shorten a string to a maximum length by intelligently abbreviating at delimiters.

    This function shortens a string to fit within a specified maximum length.
    It tries to shorten at natural break points (delimiters) rather than
    arbitrarily truncating in the middle of words.

    Args:
        name: The input string to shorten.
        max_len: The maximum allowed length of the output string.
        abbrv: The abbreviation string to append when shortening (default "...").
        use_delimiter_in_abbr: If True, includes the delimiter before the abbreviation
                              when shortening at a delimiter (default True).

    Returns:
        A shortened version of the input string that doesn't exceed max_len characters.

    Examples:
        >>> shorten_name("hello/world.txt", 10)
        'hello/...'
        >>> shorten_name("hello/world.txt", 10, use_delimiter_in_abbr=False)
        'hello...'
        >>> shorten_name("hello/world.txt", 20)
        'hello/world.txt'
        >>> shorten_name("verylongword", 8)
        'verylo...'
        >>> shorten_name("hello/world.txt", 10, ":1234" use_delimiter_in_abbr=False)
        'hello:1234'
    """
    if len(name) <= max_len:
        return name
    # Split the string based on all of the listed delimiters
    delimiters = [",", ";", "|", " ", "/", "?", "."]
    parts = capture_parts(name, delimiters)
    abbrv_len = len(abbrv)
    if len(parts) <= 1:
        # No delimiters found, just truncate
        return name[: max_len - abbrv_len] + abbrv

    shortened_name = parts[0]

    # If the first part is already longer than max_len, truncate it
    if len(shortened_name) > max_len - abbrv_len:
        return shortened_name[: max_len - abbrv_len] + abbrv

    i = 1
    while i < len(parts):
        # Concatenate the delimiter with the next part
        next_delimiter = ""
        while parts[i] in delimiters:
            next_delimiter = next_delimiter + parts[i]
            i += 1

        next_part = f"{next_delimiter}{parts[i]}"
        # If there is no abbreviation, do not end on a delimiter (ex. no trailing periods)
        if not abbrv_len:
            delimiter_with_abbrv = ""
        elif abbrv.startswith(next_delimiter) or not use_delimiter_in_abbr:
            delimiter_with_abbrv = abbrv
        else:
            delimiter_with_abbrv = f"{next_delimiter}{abbrv}"

        if len(shortened_name) + len(next_part) >= max_len - (
            len(delimiter_with_abbrv)
        ):
            shortened_name += delimiter_with_abbrv
            break
        else:
            shortened_name += next_part
        i += 1
    return shortened_name


def try_parse_timestamp(x: Any) -> Any:
    """Try to parse a timestamp from various formats.

    Args:
        x: The input value to parse as a timestamp.

    Returns:
        A datetime object if parsing is successful, otherwise returns None.
    """
    try:
        if isinstance(x, str):
            # Try to parse as ISO 8601 format
            return datetime.fromisoformat(x)
        elif isinstance(x, int):
            # Try to parse from unix_ns
            return datetime.fromtimestamp(x / 1_000_000_000)
        elif isinstance(x, float):
            return datetime.fromtimestamp(x)
    except (ValueError, TypeError):
        return None
