"""Utility functions for safely working with nested dictionaries.

This module provides functions for safely accessing and manipulating nested dictionary structures,
particularly useful when dealing with JSON-like data where keys might not exist at any level.
"""

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
