"""Handlers for making objects thread-safe."""

import logging
from typing import Any, Callable

THREAD_BOUNDARY_HANDLERS: dict[type, Callable[[Any], Any]] = {}

logger = logging.getLogger(__name__)


def register_thread_safety_handler(type_: type, handler: Callable[[Any], Any]) -> None:
    """Register a handler for making an object thread-safe (usually deepcopy)."""
    THREAD_BOUNDARY_HANDLERS[type_] = handler


def ensure_thread_safe(obj: Any) -> Any:
    """Ensure object is safe to cross thread boundaries."""
    for type_, handler in THREAD_BOUNDARY_HANDLERS.items():
        if isinstance(obj, type_):
            print(f"Ensuring thread safety for {type_} to {obj}")
            return handler(obj)
    print(f"No thread safety handler found for {type(obj)} to {obj}")
    return obj
