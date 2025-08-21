"""Serialization handlers for Python primitive types using the new registration system."""

from __future__ import annotations

import base64
from collections.abc import Mapping, Sequence
from typing import Any

from weave.trace.serialization.handlers.handler_registry import handler, register_handler
from weave.trace.serialization.registry import SerializationContext


# Primitive types - using functional registration for simplicity
def _register_primitives():
    """Register primitive type handlers."""
    from weave.trace.serialization.handlers.handler_registry import register_handler
    
    def serialize_primitive(obj: Any, context: SerializationContext) -> Any:
        """Pass through primitive types unchanged."""
        return obj
    
    def deserialize_primitive(data: Any, context: SerializationContext) -> Any:
        """Pass through primitive types unchanged."""
        return data
    
    # Register each primitive type with high priority
    for primitive_type in [int, float, str, bool, type(None)]:
        register_handler(
            primitive_type,
            serialize_primitive,
            deserialize_primitive,
            priority=100,
            name=f"Primitive_{primitive_type.__name__}"
        )


# Bytes handler
@handler(bytes, priority=90, name="Bytes")
class BytesHandler:
    @staticmethod
    def serialize(obj: bytes, context: SerializationContext) -> dict[str, Any]:
        """Serialize bytes objects."""
        try:
            # Try to decode as UTF-8 first
            decoded = obj.decode("utf-8")
            return {"_type": "bytes", "encoding": "utf-8", "value": decoded}
        except UnicodeDecodeError:
            # Fall back to base64 for binary data
            encoded = base64.b64encode(obj).decode("ascii")
            return {"_type": "bytes", "encoding": "base64", "value": encoded}
    
    @staticmethod
    def deserialize(data: dict[str, Any], context: SerializationContext) -> bytes:
        """Deserialize bytes objects."""
        encoding = data.get("encoding", "utf-8")
        value = data["value"]
        
        if encoding == "utf-8":
            return value.encode("utf-8")
        elif encoding == "base64":
            return base64.b64decode(value)
        else:
            raise ValueError(f"Unknown bytes encoding: {encoding}")


# List handler
@handler(list, priority=50, name="List")
class ListHandler:
    @staticmethod
    def serialize(obj: list, context: SerializationContext) -> list[Any]:
        """Serialize list objects."""
        from weave.trace.serialization.registry import serialize
        
        new_context = context.increment_depth()
        return [serialize(item, new_context) for item in obj]
    
    @staticmethod
    def deserialize(data: list[Any], context: SerializationContext) -> list[Any]:
        """Deserialize list objects."""
        from weave.trace.serialization.registry import deserialize
        
        new_context = context.increment_depth()
        return [deserialize(item, new_context) for item in data]


# Tuple handler
@handler(tuple, priority=50, name="Tuple")
class TupleHandler:
    @staticmethod
    def serialize(obj: tuple, context: SerializationContext) -> dict[str, Any]:
        """Serialize tuple objects."""
        from weave.trace.serialization.registry import serialize
        
        new_context = context.increment_depth()
        return {
            "_type": "tuple",
            "values": [serialize(item, new_context) for item in obj]
        }
    
    @staticmethod
    def deserialize(data: dict[str, Any], context: SerializationContext) -> tuple:
        """Deserialize tuple objects."""
        from weave.trace.serialization.registry import deserialize
        
        new_context = context.increment_depth()
        values = [deserialize(item, new_context) for item in data["values"]]
        return tuple(values)


# Set handler
@handler(set, priority=50, name="Set")
class SetHandler:
    @staticmethod
    def serialize(obj: set, context: SerializationContext) -> dict[str, Any]:
        """Serialize set objects."""
        from weave.trace.serialization.registry import serialize
        
        new_context = context.increment_depth()
        return {
            "_type": "set",
            "values": [serialize(item, new_context) for item in obj]
        }
    
    @staticmethod
    def deserialize(data: dict[str, Any], context: SerializationContext) -> set:
        """Deserialize set objects."""
        from weave.trace.serialization.registry import deserialize
        
        new_context = context.increment_depth()
        values = [deserialize(item, new_context) for item in data["values"]]
        return set(values)


# Dict handler
@handler(dict, priority=50, name="Dict")
class DictHandler:
    @staticmethod
    def serialize(obj: dict, context: SerializationContext) -> dict[str, Any]:
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
    
    @staticmethod
    def deserialize(data: dict[str, Any], context: SerializationContext) -> dict[Any, Any]:
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


# Namedtuple handler with check function
def is_namedtuple(obj: Any) -> bool:
    """Check if an object is a namedtuple."""
    return (
        isinstance(obj, tuple) and 
        hasattr(obj, "_asdict") and 
        hasattr(obj, "_fields")
    )


@handler(is_namedtuple, priority=60, name="NamedTuple")
class NamedTupleHandler:
    @staticmethod
    def serialize(obj: Any, context: SerializationContext) -> dict[str, Any]:
        """Serialize namedtuple objects."""
        from weave.trace.serialization.registry import serialize
        
        new_context = context.increment_depth()
        return {
            "_type": "namedtuple",
            "_class": obj.__class__.__name__,
            "_module": obj.__class__.__module__,
            "values": {k: serialize(v, new_context) for k, v in obj._asdict().items()}
        }
    
    @staticmethod
    def deserialize(data: dict[str, Any], context: SerializationContext) -> Any:
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


def register_primitive_handlers():
    """Register all primitive type handlers."""
    # Register basic primitives
    _register_primitives()
    
    # The decorator-based handlers auto-register via handler_registry
    from weave.trace.serialization.handlers.handler_registry import register_pending_handlers
    register_pending_handlers()