"""Serialization handlers for Python primitive types."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from weave.trace.serialization.registry import SerializationContext, register


def serialize_primitive(obj: Any, context: SerializationContext) -> Any:
    """Serialize primitive types (int, float, str, bool, None)."""
    return obj


def deserialize_primitive(data: Any, context: SerializationContext) -> Any:
    """Deserialize primitive types."""
    return data


def serialize_bytes(obj: bytes, context: SerializationContext) -> dict[str, Any]:
    """Serialize bytes objects."""
    try:
        # Try to decode as UTF-8 first
        decoded = obj.decode("utf-8")
        return {"_type": "bytes", "encoding": "utf-8", "value": decoded}
    except UnicodeDecodeError:
        # Fall back to base64 for binary data
        import base64
        encoded = base64.b64encode(obj).decode("ascii")
        return {"_type": "bytes", "encoding": "base64", "value": encoded}


def deserialize_bytes(data: dict[str, Any], context: SerializationContext) -> bytes:
    """Deserialize bytes objects."""
    encoding = data.get("encoding", "utf-8")
    value = data["value"]
    
    if encoding == "utf-8":
        return value.encode("utf-8")
    elif encoding == "base64":
        import base64
        return base64.b64decode(value)
    else:
        raise ValueError(f"Unknown bytes encoding: {encoding}")


def serialize_list(obj: list, context: SerializationContext) -> list[Any]:
    """Serialize list objects."""
    from weave.trace.serialization.registry import serialize
    
    new_context = context.increment_depth()
    return [serialize(item, new_context) for item in obj]


def deserialize_list(data: list[Any], context: SerializationContext) -> list[Any]:
    """Deserialize list objects."""
    from weave.trace.serialization.registry import deserialize
    
    new_context = context.increment_depth()
    return [deserialize(item, new_context) for item in data]


def serialize_tuple(obj: tuple, context: SerializationContext) -> dict[str, Any]:
    """Serialize tuple objects."""
    from weave.trace.serialization.registry import serialize
    
    new_context = context.increment_depth()
    return {
        "_type": "tuple",
        "values": [serialize(item, new_context) for item in obj]
    }


def deserialize_tuple(data: dict[str, Any], context: SerializationContext) -> tuple:
    """Deserialize tuple objects."""
    from weave.trace.serialization.registry import deserialize
    
    new_context = context.increment_depth()
    values = [deserialize(item, new_context) for item in data["values"]]
    return tuple(values)


def serialize_set(obj: set, context: SerializationContext) -> dict[str, Any]:
    """Serialize set objects."""
    from weave.trace.serialization.registry import serialize
    
    new_context = context.increment_depth()
    return {
        "_type": "set",
        "values": [serialize(item, new_context) for item in obj]
    }


def deserialize_set(data: dict[str, Any], context: SerializationContext) -> set:
    """Deserialize set objects."""
    from weave.trace.serialization.registry import deserialize
    
    new_context = context.increment_depth()
    values = [deserialize(item, new_context) for item in data["values"]]
    return set(values)


def serialize_dict(obj: dict, context: SerializationContext) -> dict[str, Any]:
    """Serialize dict objects."""
    from weave.trace.serialization.registry import serialize
    from weave.utils.sanitize import REDACTED_VALUE, should_redact
    
    new_context = context.increment_depth()
    result = {}
    
    for key, value in obj.items():
        # Handle PII redaction
        if isinstance(key, str) and should_redact(key) and context.redact_pii:
            result[key] = REDACTED_VALUE
        else:
            # Serialize both key and value (keys might not be strings)
            serialized_key = serialize(key, new_context) if not isinstance(key, str) else key
            serialized_value = serialize(value, new_context)
            result[serialized_key] = serialized_value
    
    return result


def deserialize_dict(data: dict[str, Any], context: SerializationContext) -> dict[Any, Any]:
    """Deserialize dict objects."""
    from weave.trace.serialization.registry import deserialize
    
    new_context = context.increment_depth()
    result = {}
    
    for key, value in data.items():
        # Deserialize both key and value
        deserialized_key = deserialize(key, new_context) if not isinstance(key, str) else key
        deserialized_value = deserialize(value, new_context)
        result[deserialized_key] = deserialized_value
    
    return result


def serialize_namedtuple(obj: Any, context: SerializationContext) -> dict[str, Any]:
    """Serialize namedtuple objects."""
    from weave.trace.serialization.registry import serialize
    
    new_context = context.increment_depth()
    return {
        "_type": "namedtuple",
        "_class": obj.__class__.__name__,
        "_module": obj.__class__.__module__,
        "values": {k: serialize(v, new_context) for k, v in obj._asdict().items()}
    }


def deserialize_namedtuple(data: dict[str, Any], context: SerializationContext) -> Any:
    """Deserialize namedtuple objects."""
    from weave.trace.serialization.registry import deserialize
    
    # This is simplified - real implementation would need to reconstruct the actual namedtuple class
    new_context = context.increment_depth()
    values = {k: deserialize(v, new_context) for k, v in data["values"].items()}
    
    # Try to import and reconstruct the namedtuple
    try:
        import importlib
        module = importlib.import_module(data["_module"])
        cls = getattr(module, data["_class"])
        return cls(**values)
    except (ImportError, AttributeError):
        # Fall back to a dict if we can't reconstruct the namedtuple
        return values


def is_namedtuple(obj: Any) -> bool:
    """Check if an object is a namedtuple."""
    return (
        isinstance(obj, tuple) and 
        hasattr(obj, "_asdict") and 
        hasattr(obj, "_fields")
    )


def register_primitive_handlers():
    """Register all primitive type handlers."""
    # Primitive types (highest priority)
    register(int, serialize_primitive, deserialize_primitive, priority=100)
    register(float, serialize_primitive, deserialize_primitive, priority=100)
    register(str, serialize_primitive, deserialize_primitive, priority=100)
    register(bool, serialize_primitive, deserialize_primitive, priority=100)
    register(type(None), serialize_primitive, deserialize_primitive, priority=100)
    
    # Bytes
    register(bytes, serialize_bytes, deserialize_bytes, priority=90)
    
    # Collections (lower priority to allow specialized handlers to override)
    register(list, serialize_list, deserialize_list, priority=50)
    register(tuple, serialize_tuple, deserialize_tuple, priority=50)
    register(set, serialize_set, deserialize_set, priority=50)
    register(dict, serialize_dict, deserialize_dict, priority=50)
    
    # Namedtuples (check function needed since they're tuple subclasses)
    register(
        tuple,  # Base type
        serialize_namedtuple,
        deserialize_namedtuple,
        priority=60,  # Higher than regular tuples
        check_func=is_namedtuple
    )