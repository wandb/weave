from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class WeaveSerializable(Protocol):
    """Protocol for objects with custom serialization support.

    Objects implementing this protocol can define custom serialization
    and deserialization behavior through dunder methods.
    """

    def __weave_serialize__(self) -> dict[str, Any]:
        """Serialize the object to a dictionary representation.

        Returns:
            A dictionary representation of the object that can be used
            for serialization to JSON or other formats.
        """
        ...

    @classmethod
    def __weave_deserialize__(cls, data: dict[str, Any]) -> Any:
        """Deserialize a dictionary representation back to an object.

        Args:
            data: Dictionary representation of the object

        Returns:
            A new instance of the class reconstructed from the data
        """
        ...


@runtime_checkable
class Dictifiable(Protocol):
    """Protocol for objects that can be converted to a dictionary representation.

    DEPRECATED: Use WeaveSerializable with __weave_serialize__ instead.
    This protocol is maintained for backwards compatibility.
    """

    def to_dict(self) -> dict[str, Any]:
        """Convert the object to a dictionary representation."""
        ...


def try_weave_serialize(obj: Any) -> dict[str, Any] | None:
    """Attempt to serialize an object using the WeaveSerializable protocol.

    Args:
        obj: Object to attempt to serialize

    Returns:
        Dictionary representation if object implements WeaveSerializable protocol, None otherwise
    """
    if isinstance(obj, WeaveSerializable):
        try:
            res = obj.__weave_serialize__()
            if isinstance(res, dict):
                return res
        except Exception:
            return None
    return None


def try_weave_deserialize(cls: type, data: dict[str, Any]) -> Any | None:
    """Attempt to deserialize data using the WeaveSerializable protocol.

    Args:
        cls: Class that may implement WeaveSerializable protocol
        data: Dictionary representation to deserialize

    Returns:
        Deserialized object if class implements WeaveSerializable protocol, None otherwise
    """
    if hasattr(cls, "__weave_deserialize__") and callable(cls.__weave_deserialize__):
        try:
            return cls.__weave_deserialize__(data)
        except Exception:
            return None
    return None


def try_to_dict(obj: Any) -> dict[str, Any] | None:
    """Attempt to convert an object to a dictionary.

    This function first tries the new WeaveSerializable protocol (__weave_serialize__),
    then falls back to the legacy Dictifiable protocol (to_dict) for backwards compatibility.

    Args:
        obj: Object to attempt to convert to dictionary

    Returns:
        Dictionary representation if object implements either protocol, None otherwise
    """
    # Try new WeaveSerializable protocol first
    if (result := try_weave_serialize(obj)) is not None:
        return result

    # Fall back to legacy Dictifiable protocol
    if isinstance(obj, Dictifiable):
        try:
            res = obj.to_dict()
            if isinstance(res, dict):
                return res
        except Exception:
            return None
    return None
