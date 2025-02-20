"""Registry for Weave serializers."""

from __future__ import annotations

from typing import Any, Type, TypeVar

from weave.trace.serialization.protocol import WeaveSerializer

T = TypeVar('T')

class SerializerRegistry:
    """Registry for Weave serializers.
    
    The registry maintains a list of serializers and provides methods to find
    the appropriate serializer for a given object or type ID.
    """
    
    def __init__(self) -> None:
        self._serializers: list[Type[WeaveSerializer[Any]]] = []
        
    def register(self, serializer: Type[WeaveSerializer[Any]]) -> None:
        """Register a new serializer.
        
        Args:
            serializer: The serializer class to register
        """
        # Insert at start so newer serializers take precedence
        self._serializers.insert(0, serializer)
        
    def get_for_object(self, obj: Any) -> WeaveSerializer[Any]:
        """Get an appropriate serializer for the given object.
        
        Args:
            obj: The object to find a serializer for
            
        Returns:
            An instance of a serializer that can handle the object
            
        Raises:
            ValueError: If no serializer can handle the object
        """
        for serializer_cls in self._serializers:
            if serializer_cls.can_handle(obj):
                return serializer_cls()
        raise ValueError(f"No serializer found for object of type {type(obj)}")
        
    def get_by_type_id(self, type_id: str) -> WeaveSerializer[Any]:
        """Get a serializer by its type ID.
        
        Args:
            type_id: The type ID to find a serializer for
            
        Returns:
            An instance of the serializer for that type ID
            
        Raises:
            ValueError: If no serializer is found for the type ID
        """
        for serializer_cls in self._serializers:
            if serializer_cls.type_id() == type_id:
                return serializer_cls()
        raise ValueError(f"No serializer found for type ID {type_id}")

# Global registry instance
REGISTRY = SerializerRegistry() 