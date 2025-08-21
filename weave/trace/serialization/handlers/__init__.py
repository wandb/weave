"""Serialization handlers for various types."""

from weave.trace.serialization.handlers.pydantic import register_pydantic_handlers
from weave.trace.serialization.handlers.primitives import register_primitive_handlers


def register_all_handlers():
    """Register all built-in serialization handlers."""
    register_primitive_handlers()
    register_pydantic_handlers()


__all__ = [
    "register_primitive_handlers",
    "register_pydantic_handlers", 
    "register_all_handlers",
]