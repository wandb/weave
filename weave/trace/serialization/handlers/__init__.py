"""Serialization handlers for various types.

This module provides a unified registration system for all serialization handlers.
Handlers can be registered using either:
1. The @handler decorator for automatic registration
2. Direct registration through register_handler() function
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def register_all_handlers():
    """Register all built-in serialization handlers.
    
    This function imports all handler modules and triggers their registration.
    Handlers using the @handler decorator are automatically registered on import.
    """
    try:
        # Import v2 handlers that use the decorator-based registration
        # These modules contain @handler decorated classes that auto-register
        from weave.trace.serialization.handlers import (
            primitives_v2,
            pydantic_v2,
            media_v2,
        )
        
        # Import original handlers (will be migrated later)
        from weave.trace.serialization.handlers import (
            weave_types,
            ops,
            image,
            audio,
        )
        
        # Trigger registration of any pending decorator-based handlers
        from weave.trace.serialization.handlers.handler_registry import register_pending_handlers
        register_pending_handlers()
        
        # Register handlers using v2 system
        from weave.trace.serialization.handlers.primitives_v2 import register_primitive_handlers
        from weave.trace.serialization.handlers.pydantic_v2 import register_pydantic_handlers
        from weave.trace.serialization.handlers.media_v2 import register_media_handlers
        
        # Register original handlers (temporary until fully migrated)
        from weave.trace.serialization.handlers.weave_types import register_weave_handlers
        from weave.trace.serialization.handlers.ops import register_op_handler
        from weave.trace.serialization.handlers.image import register_image_handlers
        from weave.trace.serialization.handlers.audio import register_audio_handlers
        
        # Register in order of priority
        register_primitive_handlers()  # Highest priority for basic types
        register_pydantic_handlers()   # Pydantic models
        register_media_handlers()      # DateTime and other media types
        register_weave_handlers()      # Weave-specific types
        register_op_handler()          # Ops
        register_image_handlers()      # Images
        register_audio_handlers()      # Audio
        
        logger.debug("All serialization handlers registered successfully")
        
    except ImportError as e:
        logger.warning(f"Some handlers could not be registered due to missing dependencies: {e}")
    except Exception as e:
        logger.error(f"Error registering serialization handlers: {e}")
        raise


# Convenience re-exports for handler registration
from weave.trace.serialization.handlers.handler_registry import (
    handler,
    register_handler,
    HandlerRegistration,
)

__all__ = [
    "register_all_handlers",
    "handler",
    "register_handler",
    "HandlerRegistration",
]