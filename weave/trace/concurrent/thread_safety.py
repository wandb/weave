"""Handlers for making objects thread-safe."""

from typing import Any, Callable

THREAD_BOUNDARY_HANDLERS: dict[type, Callable[[Any], Any]] = {}


def register_thread_safety_handler(type_: type, handler: Callable[[Any], Any]) -> None:
    """Register a handler for making an object thread-safe (usually deepcopy)."""
    THREAD_BOUNDARY_HANDLERS[type_] = handler


def ensure_thread_safe(obj: Any) -> Any:
    """Ensure object is safe to cross thread boundaries."""
    for type_, handler in THREAD_BOUNDARY_HANDLERS.items():
        if isinstance(obj, type_):
            return handler(obj)
    return obj
