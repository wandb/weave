"""Serialization handlers for various types."""

from weave.trace.serialization.handlers.pydantic import register_pydantic_handlers
from weave.trace.serialization.handlers.primitives import register_primitive_handlers
from weave.trace.serialization.handlers.weave_types import register_weave_handlers
from weave.trace.serialization.handlers.ops import register_op_handler
from weave.trace.serialization.handlers.image import register_image_handlers
from weave.trace.serialization.handlers.audio import register_audio_handlers
from weave.trace.serialization.handlers.media import register_media_handlers


def register_all_handlers():
    """Register all built-in serialization handlers."""
    # Register in order of priority
    register_primitive_handlers()  # Highest priority for basic types
    register_pydantic_handlers()   # Pydantic models
    register_weave_handlers()      # Weave-specific types
    register_op_handler()          # Ops
    register_image_handlers()      # Images
    register_audio_handlers()      # Audio
    register_media_handlers()      # Other media and special types


__all__ = [
    "register_primitive_handlers",
    "register_pydantic_handlers",
    "register_weave_handlers",
    "register_op_handler",
    "register_image_handlers", 
    "register_audio_handlers",
    "register_media_handlers",
    "register_all_handlers",
]