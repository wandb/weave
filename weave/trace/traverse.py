"""Utilities for traversing objects."""

from __future__ import annotations

from collections.abc import Collection, Iterator
from functools import cmp_to_key
from typing import Any, Union, overload

# String indicates object key access, number indicates array index access
# This structure allows us to handle corner cases like periods or brackets
# in object keys.

PathElement = Union[str, int]


def escape_key(key: str) -> str:
    """Escape special characters in a key for path string representation."""
    return key.replace(".", "\\.").replace("[", "\\[").replace("]", "\\]")


class ObjectPath:
    elements: list[PathElement]

    def __init__(self, elements: list[PathElement] | None = None):
        self.elements = elements if elements is not None else []

    @overload
    def __getitem__(self, index: int) -> PathElement: ...

    @overload
    def __getitem__(self, index: slice) -> list[PathElement]: ...

    def __getitem__(self, index: int | slice) -> PathElement | list[PathElement]:
        return self.elements[index]

    def __len__(self) -> int:
        return len(self.elements)

    def __add__(self, other: list[PathElement]) -> ObjectPath:
        return ObjectPath(self.elements + other)

    def __iter__(self) -> Iterator[PathElement]:
        return iter(self.elements)

    def __repr__(self) -> str:
        return f"ObjectPath({self.elements})"

    def __lt__(self, other: ObjectPath) -> bool:
        return compare_paths(self, other) < 0

    def __le__(self, other: ObjectPath) -> bool:
        return compare_paths(self, other) <= 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ObjectPath):
            return NotImplemented
        return compare_paths(self, other) == 0

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, ObjectPath):
            return NotImplemented
        return compare_paths(self, other) != 0

    def __gt__(self, other: ObjectPath) -> bool:
        return compare_paths(self, other) > 0

    def __ge__(self, other: ObjectPath) -> bool:
        return compare_paths(self, other) >= 0

    def __hash__(self) -> int:
        return hash(tuple(self.elements))

    def __str__(self) -> str:
        return self.to_str()

    def to_str(self) -> str:
        """Convert the path to a string representation.

        Returns a string with dot notation for string elements and
        square brackets for numeric indices.
        """
        result = ""
        for element in self.elements:
            if isinstance(element, str):
                # Escape special characters in string keys
                escaped = escape_key(element)
                if result:
                    result += "."
                result += escaped
            else:
                # Use bracket notation for numeric indices
                result += f"[{element}]"
        return result

    @classmethod
    def parse_str(cls, path_string: str) -> ObjectPath:
        """Parse a string representation of a path into a ObjectPath object.

        Handles dot notation for object access and square brackets for array indices.
        Supports escaping with backslash.

        Args:
            path_string: String representation of a path

        Returns:
            ObjectPath object

        Raises:
            ValueError: If the path string is invalid
        """
        path: list[PathElement] = []
        key = ""
        n = len(path_string)
        i = 0

        while i < n:
            char = path_string[i]
            if char == "\\":
                if i == n - 1:
                    raise ValueError("Invalid escape sequence")
                key += path_string[i + 1]
                i += 2
            elif char == ".":
                if i == 0 or i == n - 1:
                    raise ValueError("Invalid object access")
                prev = path_string[i - 1]
                next_char = path_string[i + 1]
                if not next_char.isalnum() or not (prev.isalnum() or prev == "]"):
                    raise ValueError("Invalid object access")
                if key:
                    path.append(key)
                    key = ""
                i += 1
            elif char == "[":
                if key:
                    path.append(key)
                    key = ""
                j = i + 1
                while j < n and path_string[j] != "]":
                    j += 1
                index_str = path_string[i + 1 : j]
                if j == n:
                    raise ValueError(f"Invalid array index: '{index_str}'")
                if not index_str.isdigit():
                    raise ValueError(f"Invalid array index: '{index_str}'")
                path.append(int(index_str))
                i = j + 1
            else:
                key += char
                i += 1

        if key:
            path.append(key)

        return cls(path)


ObjectPaths = list[ObjectPath]


def get_paths(obj: Any, path: ObjectPath | None = None) -> ObjectPaths:
    """Traverse an object and return all possible key paths."""
    if path is None:
        path = ObjectPath([])
    paths = [path] if path else []
    if isinstance(obj, dict):
        for key, value in obj.items():
            paths.extend(get_paths(value, path + [key]))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            to_add: list[PathElement] = [i]  # Making pyright happy
            paths.extend(get_paths(value, path + to_add))
    return paths


def compare_paths(path1: ObjectPath, path2: ObjectPath) -> int:
    """Compare two paths for sort ordering.

    Returns:
        -1 if path1 < path2
        0 if path1 == path2
        1 if path1 > path2
    """
    # Compare elements pairwise
    for e1, e2 in zip(path1, path2):
        # If elements are same type, compare directly
        if isinstance(e1, str) and isinstance(e2, str):
            if e1 < e2:
                return -1
            if e1 > e2:
                return 1
        elif isinstance(e1, int) and isinstance(e2, int):
            if e1 < e2:
                return -1
            if e1 > e2:
                return 1

        # If different types, strings come before integers
        if isinstance(e1, str) and isinstance(e2, int):
            return -1
        if isinstance(e1, int) and isinstance(e2, str):
            return 1

    # If we get here, all common elements were equal
    # Shorter paths come before longer paths
    if len(path1) < len(path2):
        return -1
    if len(path1) > len(path2):
        return 1

    return 0


def sort_paths(paths: Collection[ObjectPath]) -> ObjectPaths:
    return sorted(paths, key=cmp_to_key(compare_paths))
