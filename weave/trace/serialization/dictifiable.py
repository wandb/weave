from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Dictifiable(Protocol):
    """Protocol for objects that can be converted to a dictionary representation."""

    def to_dict(self) -> dict[str, Any]:
        """Convert the object to a dictionary representation."""
        ...


def try_to_dict(obj: Any) -> dict[str, Any] | None:
    """
    Attempt to convert an object to a dictionary using the Dictifiable protocol.

    Args:
        obj: Object to attempt to convert to dictionary

    Returns:
        Dictionary representation if object implements Dictifiable protocol, None otherwise
    """
    if isinstance(obj, Dictifiable):
        try:
            res = obj.to_dict()
            if isinstance(res, dict):
                return res
        except Exception:
            return None
    return None
