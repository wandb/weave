"""Centralized serialization registry for Weave.

This module provides a unified registry for all serialization handlers,
managing type-specific and protocol-based serialization strategies.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, Type, Union

from weave.trace.serialization.protocols import FileSerializable, Serializable

logger = logging.getLogger(__name__)

SerializeFunc = Callable[[Any, "SerializationContext"], Any]
DeserializeFunc = Callable[[Any, "SerializationContext"], Any]


@dataclass
class SerializationContext:
    """Context passed to serialization handlers."""
    
    project_id: str | None = None
    client: Any = None  # Avoid circular import with WeaveClient
    depth: int = 0
    max_depth: int = 10
    seen: set[int] = field(default_factory=set)
    redact_pii: bool = False
    use_refs: bool = True
    file_storage: bool = True
    
    def increment_depth(self) -> SerializationContext:
        """Create a new context with incremented depth."""
        return SerializationContext(
            project_id=self.project_id,
            client=self.client,
            depth=self.depth + 1,
            max_depth=self.max_depth,
            seen=self.seen,
            redact_pii=self.redact_pii,
            use_refs=self.use_refs,
            file_storage=self.file_storage,
        )
    
    def has_seen(self, obj_id: int) -> bool:
        """Check if an object has been seen (for circular reference detection)."""
        return obj_id in self.seen
    
    def mark_seen(self, obj_id: int) -> None:
        """Mark an object as seen."""
        self.seen.add(obj_id)


@dataclass
class SerializationHandler:
    """A handler for serializing and deserializing a specific type."""
    
    type_or_protocol: Type | Protocol
    serialize: SerializeFunc
    deserialize: DeserializeFunc
    priority: int = 0  # Higher priority handlers are checked first
    check_func: Callable[[Any], bool] | None = None  # Optional instance check
    
    def can_handle(self, obj: Any) -> bool:
        """Check if this handler can handle the given object."""
        if self.check_func:
            return self.check_func(obj)
        
        # For protocols, use isinstance check
        if hasattr(self.type_or_protocol, "__runtime_checkable__"):
            return isinstance(obj, self.type_or_protocol)
        
        # For regular types
        return isinstance(obj, self.type_or_protocol)


class SerializationRegistry:
    """Central registry for all serialization handlers."""
    
    def __init__(self):
        self._handlers: list[SerializationHandler] = []
        self._type_cache: dict[type, SerializationHandler | None] = {}
        
    def register(
        self,
        type_or_protocol: Type | Protocol,
        serialize: SerializeFunc | None = None,
        deserialize: DeserializeFunc | None = None,
        priority: int = 0,
        check_func: Callable[[Any], bool] | None = None,
    ) -> None:
        """Register a serialization handler.
        
        Args:
            type_or_protocol: The type or protocol to handle.
            serialize: Function to serialize objects of this type.
            deserialize: Function to deserialize objects of this type.
            priority: Handler priority (higher = checked first).
            check_func: Optional function to check if an object can be handled.
        """
        # If no explicit handlers provided, check for protocol methods
        if serialize is None and hasattr(type_or_protocol, "__weave_serialize__"):
            serialize = self._protocol_serialize
        if deserialize is None and hasattr(type_or_protocol, "__weave_deserialize__"):
            deserialize = self._protocol_deserialize
            
        if serialize is None or deserialize is None:
            raise ValueError(
                f"Must provide both serialize and deserialize functions for {type_or_protocol}"
            )
        
        handler = SerializationHandler(
            type_or_protocol=type_or_protocol,
            serialize=serialize,
            deserialize=deserialize,
            priority=priority,
            check_func=check_func,
        )
        
        # Insert handler in priority order
        insert_idx = 0
        for i, existing in enumerate(self._handlers):
            if existing.priority < priority:
                insert_idx = i
                break
            insert_idx = i + 1
        
        self._handlers.insert(insert_idx, handler)
        # Clear cache when adding new handler
        self._type_cache.clear()
        
    def _protocol_serialize(self, obj: Any, context: SerializationContext) -> Any:
        """Serialize using the Serializable protocol."""
        return obj.__weave_serialize__()
    
    def _protocol_deserialize(self, data: Any, context: SerializationContext) -> Any:
        """Deserialize using the Serializable protocol."""
        # This is a placeholder - actual implementation would need type info
        raise NotImplementedError("Protocol deserialization requires type information")
    
    def get_handler(self, obj: Any) -> SerializationHandler | None:
        """Get the handler for a given object."""
        obj_type = type(obj)
        
        # Check cache first
        if obj_type in self._type_cache:
            return self._type_cache[obj_type]
        
        # Find handler
        for handler in self._handlers:
            if handler.can_handle(obj):
                self._type_cache[obj_type] = handler
                return handler
        
        # Check if object implements Serializable protocol
        if isinstance(obj, Serializable):
            handler = SerializationHandler(
                type_or_protocol=Serializable,
                serialize=self._protocol_serialize,
                deserialize=self._protocol_deserialize,
                priority=-1,  # Lower priority than registered handlers
            )
            self._type_cache[obj_type] = handler
            return handler
        
        self._type_cache[obj_type] = None
        return None
    
    def serialize(self, obj: Any, context: SerializationContext | None = None) -> Any:
        """Serialize an object using the appropriate handler.
        
        Args:
            obj: The object to serialize.
            context: Optional serialization context.
            
        Returns:
            The serialized representation of the object.
        """
        if context is None:
            context = SerializationContext()
        
        # Check for circular references
        if not isinstance(obj, (int, float, str, bool, type(None))):
            obj_id = id(obj)
            if context.has_seen(obj_id):
                return {"_type": "CircularRef", "_id": obj_id}
            context.mark_seen(obj_id)
        
        # Check depth limit
        if context.depth > context.max_depth:
            return {"_type": "DepthLimitExceeded", "_repr": repr(obj)[:100]}
        
        handler = self.get_handler(obj)
        if handler:
            return handler.serialize(obj, context)
        
        # Fallback for unknown types
        return self._fallback_serialize(obj, context)
    
    def deserialize(self, data: Any, context: SerializationContext | None = None) -> Any:
        """Deserialize data using the appropriate handler.
        
        Args:
            data: The data to deserialize.
            context: Optional serialization context.
            
        Returns:
            The deserialized object.
        """
        if context is None:
            context = SerializationContext()
        
        # Handle special types
        if isinstance(data, dict):
            if data.get("_type") == "CircularRef":
                return f"<CircularRef {data.get('_id')}>"
            elif data.get("_type") == "DepthLimitExceeded":
                return f"<DepthLimitExceeded {data.get('_repr')}>"
        
        # Find handler based on type hint in data
        # This is simplified - real implementation would need type tracking
        return data
    
    def _fallback_serialize(self, obj: Any, context: SerializationContext) -> Any:
        """Fallback serialization for unknown types."""
        # Import here to avoid circular dependency
        from weave.trace.serialization.dictifiable import try_to_dict
        
        # Try to_dict if available (using the protocol)
        if as_dict := try_to_dict(obj):
            # Recursively serialize the dictionary
            new_context = context.increment_depth()
            return {k: self.serialize(v, new_context) for k, v in as_dict.items()}
        
        # Try __dict__ if available
        if hasattr(obj, "__dict__"):
            try:
                obj_dict = obj.__dict__.copy()
                new_context = context.increment_depth()
                return {
                    "_type": "Object",
                    "_class": obj.__class__.__name__,
                    "_module": obj.__class__.__module__,
                    "data": {k: self.serialize(v, new_context) for k, v in obj_dict.items()}
                }
            except Exception:
                pass
        
        # Final fallback to string representation
        return {"_type": "FallbackString", "_value": repr(obj)[:1000]}
    
    def clear(self) -> None:
        """Clear all registered handlers."""
        self._handlers.clear()
        self._type_cache.clear()


# Global registry instance
_registry = SerializationRegistry()

# Public API functions
def register(
    type_or_protocol: Type | Protocol,
    serialize: SerializeFunc | None = None,
    deserialize: DeserializeFunc | None = None,
    priority: int = 0,
    check_func: Callable[[Any], bool] | None = None,
) -> None:
    """Register a serialization handler with the global registry."""
    _registry.register(type_or_protocol, serialize, deserialize, priority, check_func)


def serialize(obj: Any, context: SerializationContext | None = None) -> Any:
    """Serialize an object using the global registry."""
    return _registry.serialize(obj, context)


def deserialize(data: Any, context: SerializationContext | None = None) -> Any:
    """Deserialize data using the global registry."""
    return _registry.deserialize(data, context)


def get_registry() -> SerializationRegistry:
    """Get the global registry instance."""
    return _registry