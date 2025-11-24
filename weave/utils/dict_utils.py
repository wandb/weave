"""Utility functions for safely working with nested dictionaries.

This module provides functions for safely accessing and manipulating nested dictionary structures,
particularly useful when dealing with JSON-like data where keys might not exist at any level.
"""

import json
import numbers
from collections import defaultdict
from typing import Any, TypeVar

T = TypeVar("T")


def safe_get(
    obj: dict | None, path: list[str], default: T | None = None
) -> Any | T | None:
    """Safely get a value from a nested dictionary using a list of keys.

    This function traverses a nested dictionary structure using a list of keys,
    returning a default value if any part of the path doesn't exist.

    Args:
        obj: The dictionary to traverse. Can be None.
        path: List of keys representing the path to traverse.
        default: The default value to return if the path doesn't exist. Defaults to None.

    Returns:
        The value at the specified path if it exists, otherwise the default value.

    Example:
        ```python
        data = {
            "a": {
                "b": {
                    "c": 123
                }
            }
        }
        value = safe_get(data, ["a", "b", "c"])  # Returns 123
        value = safe_get(data, ["a", "x", "c"])  # Returns None
        value = safe_get(data, ["a", "x", "c"], default=0)  # Returns 0
        ```
    """
    if not path:
        return obj
    if not isinstance(obj, dict):
        return default
    return safe_get(obj.get(path[0]), path[1:], default)


def convert_defaultdict_to_dict(d: dict | defaultdict) -> dict:
    if isinstance(d, defaultdict):
        return {k: convert_defaultdict_to_dict(v) for k, v in d.items()}
    return d


def sum_dict_leaves(dicts: list[dict]) -> dict:
    """Recursively combines multiple dictionaries by summing their leaf values.

    This function takes a list of dictionaries and combines them by:
    1. For non-dict values: extending lists or summing numbers
    2. For nested dictionaries: recursively combining them

    Args:
        dicts: A list of dictionaries to combine

    Returns:
        A single dictionary with combined values

    Examples:
        >>> # Combining status counts from multiple runs
        >>> dicts = [
        ...     {"status_counts": {"SUCCESS": 5, "FAILED": 1}},
        ...     {"status_counts": {"SUCCESS": 3, "FAILED": 2, "PENDING": 1}}
        ... ]
        >>> sum_dict_leaves(dicts)
        {'status_counts': {'SUCCESS': 8, 'FAILED': 3, 'PENDING': 1}}

        >>> # Combining metrics with nested structure
        >>> dicts = [
        ...     {"metrics": {"accuracy": 0.95, "loss": 0.1, "details": {"precision": 0.9, "recall": 0.8}}},
        ...     {"metrics": {"accuracy": 0.97, "loss": 0.08, "details": {"precision": 0.92, "f1": 0.85}}}
        ... ]
        >>> sum_dict_leaves(dicts)
        {'metrics': {'accuracy': 1.92, 'loss': 0.18, 'details': {'precision': 1.82, 'recall': 0.8, 'f1': 0.85}}}
    """
    nested_dicts: dict[str, list[dict]] = defaultdict(list)
    result: dict[str, Any] = defaultdict(list)

    # First, collect all nested dictionaries by key
    for d in dicts:
        for k, v in d.items():
            if isinstance(v, dict):
                nested_dicts[k].append(v)
            elif v is not None:
                if isinstance(v, list):
                    result[k].extend(v)
                else:
                    result[k].append(v)

    # Sum those values that are numbers
    for k, values in result.items():
        # we only sum numbers if we are not going to combine nested dicts later
        if k not in nested_dicts and all(isinstance(v, numbers.Number) for v in values):
            result[k] = sum(values)

    # Then recursively sum each collection of nested dictionaries
    for k in nested_dicts.keys():
        result[k] = sum_dict_leaves(nested_dicts[k])

    return convert_defaultdict_to_dict(result)


def zip_dicts(base_dict: dict[str, Any], new_dict: dict[str, Any]) -> dict[str, Any]:
    final_dict = {}
    for key, value in base_dict.items():
        if key in new_dict:
            # Shared key (if both dicts, merge)
            new_value = new_dict[key]
            if isinstance(value, dict) and isinstance(new_value, dict):
                final_dict[key] = zip_dicts(value, new_value)
            else:
                # base-only key
                final_dict[key] = new_value
        else:
            final_dict[key] = value
    for key, value in new_dict.items():
        if key not in base_dict:
            # new-only key
            final_dict[key] = value

    return final_dict


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
