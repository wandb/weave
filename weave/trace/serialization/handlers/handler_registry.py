"""Handler registration utilities for the serialization system."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Type

logger = logging.getLogger(__name__)

# Global list to track handlers that need to be registered
_PENDING_HANDLERS: list[HandlerRegistration] = []


@dataclass
class HandlerRegistration:
    """Registration information for a handler."""
    type_or_check: Type | Callable[[Any], bool]
    serialize: Callable
    deserialize: Callable
    priority: int = 50
    name: str = ""
    
    def register(self) -> None:
        """Register this handler with the global registry."""
        from weave.trace.serialization.registry import register
        
        if callable(self.type_or_check) and not isinstance(self.type_or_check, type):
            # It's a check function
            register(
                object,  # Base type
                self.serialize,
                self.deserialize,
                priority=self.priority,
                check_func=self.type_or_check
            )
        else:
            # It's a type
            register(
                self.type_or_check,
                self.serialize,
                self.deserialize,
                priority=self.priority
            )
        
        if self.name:
            logger.debug(f"Registered handler for {self.name}")


def handler(
    type_or_check: Type | Callable[[Any], bool],
    priority: int = 50,
    name: str = ""
) -> Callable:
    """Decorator to register a serialization handler.
    
    Usage:
        @handler(MyType, priority=75)
        class MyTypeHandler:
            @staticmethod
            def serialize(obj, context):
                ...
            
            @staticmethod
            def deserialize(data, context):
                ...
    
    Or with a check function:
        @handler(lambda obj: isinstance(obj, MyType), priority=75)
        class MyTypeHandler:
            ...
    """
    def decorator(cls: type) -> type:
        # Extract serialize and deserialize methods
        serialize_fn = getattr(cls, 'serialize', None)
        deserialize_fn = getattr(cls, 'deserialize', None)
        
        if not serialize_fn or not deserialize_fn:
            raise ValueError(
                f"Handler class {cls.__name__} must have both "
                "'serialize' and 'deserialize' methods"
            )
        
        # Create registration entry
        registration = HandlerRegistration(
            type_or_check=type_or_check,
            serialize=serialize_fn,
            deserialize=deserialize_fn,
            priority=priority,
            name=name or cls.__name__
        )
        
        # Add to pending registrations
        _PENDING_HANDLERS.append(registration)
        
        # Add registration method to the class
        cls._registration = registration
        
        return cls
    
    return decorator


def register_pending_handlers() -> None:
    """Register all pending handlers with the global registry."""
    for registration in _PENDING_HANDLERS:
        try:
            registration.register()
        except Exception as e:
            logger.error(f"Failed to register handler {registration.name}: {e}")
    
    # Clear the list after registration
    _PENDING_HANDLERS.clear()


# Alternative functional registration approach
def register_handler(
    type_or_check: Type | Callable[[Any], bool],
    serialize: Callable,
    deserialize: Callable,
    priority: int = 50,
    name: str = ""
) -> None:
    """Register a handler using functions instead of a class.
    
    Args:
        type_or_check: The type to handle or a check function
        serialize: Function to serialize objects
        deserialize: Function to deserialize data
        priority: Handler priority (higher = checked first)
        name: Optional name for debugging
    """
    registration = HandlerRegistration(
        type_or_check=type_or_check,
        serialize=serialize,
        deserialize=deserialize,
        priority=priority,
        name=name
    )
    
    # Register immediately
    registration.register()