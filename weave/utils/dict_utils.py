"""Utility functions for safely working with nested dictionaries.

This module provides functions for safely accessing and manipulating nested dictionary structures,
particularly useful when dealing with JSON-like data where keys might not exist at any level.
"""

import numbers
from collections import defaultdict
from typing import Any, Optional, TypeVar, Union

T = TypeVar("T")


def safe_get(
    obj: Optional[dict], path: list[str], default: Optional[T] = None
) -> Union[Any, Optional[T]]:
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


def convert_defaultdict_to_dict(d: Union[dict, defaultdict]) -> dict:
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

    return result
