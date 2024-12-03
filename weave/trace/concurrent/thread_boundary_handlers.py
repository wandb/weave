from typing import Any, Callable

# Registry of handlers for making objects thread-safe
THREAD_BOUNDARY_HANDLERS: dict[type, Callable[[Any], Any]] = {}


def register_thread_boundary_handler(
    type_: type, handler: Callable[[Any], Any]
) -> None:
    THREAD_BOUNDARY_HANDLERS[type_] = handler


def prepare_for_thread_boundary(obj: Any) -> Any:
    """Ensure object is safe to cross thread boundaries."""
    for type_, handler in THREAD_BOUNDARY_HANDLERS.items():
        if isinstance(obj, type_):
            return handler(obj)
    return obj
