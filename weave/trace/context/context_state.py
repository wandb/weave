"""
Context-aware state management for WeaveClient and refs.

This module provides isolation between concurrent executions using Python's
contextvars. This ensures that each async task or thread has its own isolated
client and ref registry, preventing data leakage between users.
"""

import contextvars
import threading
import weakref
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from weave.trace.refs import Ref
    from weave.trace.weave_client import WeaveClient

# Context variable for isolated client storage
_client_context: contextvars.ContextVar[Optional["WeaveClient"]] = (
    contextvars.ContextVar("_client_context", default=None)
)

# Context-specific ref registries using weak references
# Key: context_id, Value: WeakValueDictionary mapping object_id -> ref
_ref_registries: dict[int, weakref.WeakValueDictionary] = {}
_ref_registry_lock = threading.Lock()

# For objects that don't support weakref (like some built-ins)
# Key: (context_id, object_id), Value: ref
_strong_refs: dict[tuple[int, int], "Ref"] = {}
_strong_refs_lock = threading.Lock()


def get_context_id() -> int:
    """Get a unique identifier for the current context."""
    # Use the id of the context's copy of the client
    return id(_client_context.get())


def get_client() -> Optional["WeaveClient"]:
    """Get the client from the current context."""
    return _client_context.get()


def set_client(client: Optional["WeaveClient"]) -> contextvars.Token:
    """Set the client in the current context."""
    return _client_context.set(client)


def reset_client(token: contextvars.Token) -> None:
    """Reset the client to the previous value."""
    _client_context.reset(token)


def _get_ref_registry() -> weakref.WeakValueDictionary:
    """Get or create the ref registry for the current context."""
    context_id = get_context_id()

    with _ref_registry_lock:
        if context_id not in _ref_registries:
            _ref_registries[context_id] = weakref.WeakValueDictionary()
        return _ref_registries[context_id]


def set_ref(obj: Any, ref: Optional["Ref"]) -> None:
    """
    Set a ref for an object in the current context.

    Uses weak references where possible to allow automatic cleanup.
    Falls back to strong references for objects that don't support weakref.
    """
    obj_id = id(obj)
    context_id = get_context_id()

    if ref is None:
        # Remove ref
        registry = _get_ref_registry()
        if obj_id in registry:
            del registry[obj_id]

        # Also check strong refs
        with _strong_refs_lock:
            key = (context_id, obj_id)
            if key in _strong_refs:
                del _strong_refs[key]
    else:
        # Try to store as weak ref first
        try:
            registry = _get_ref_registry()

            # Create a wrapper that holds the ref
            # The wrapper will be garbage collected when obj is collected
            class RefWrapper:
                def __init__(self, ref: Ref) -> None:
                    self.ref = ref

            wrapper = RefWrapper(ref)
            registry[obj_id] = wrapper
        except TypeError:
            # Object doesn't support weakref, use strong ref
            with _strong_refs_lock:
                _strong_refs[context_id, obj_id] = ref


def get_ref(obj: Any) -> Optional["Ref"]:
    """Get the ref for an object in the current context."""
    obj_id = id(obj)
    context_id = get_context_id()

    # Check weak refs first
    registry = _get_ref_registry()
    wrapper = registry.get(obj_id)
    if wrapper is not None:
        return wrapper.ref

    # Check strong refs
    with _strong_refs_lock:
        return _strong_refs.get((context_id, obj_id))


def clear_context() -> None:
    """Clear all refs for the current context."""
    context_id = get_context_id()

    # Clear weak refs
    with _ref_registry_lock:
        if context_id in _ref_registries:
            del _ref_registries[context_id]

    # Clear strong refs
    with _strong_refs_lock:
        keys_to_delete = [k for k in _strong_refs if k[0] == context_id]
        for key in keys_to_delete:
            del _strong_refs[key]
