from __future__ import annotations

from typing import Any

from weave.trace.context import context_state
from weave.trace.refs import ObjectRef, Ref


def get_ref(obj: Any) -> ObjectRef | None:
    # First check context-specific refs
    context_ref = context_state.get_ref(obj)
    if context_ref is not None:
        return context_ref

    # Check for backward compatibility ref stored in __dict__
    if hasattr(obj, "__dict__") and "_weave_ref" in obj.__dict__:
        return obj.__dict__["_weave_ref"]

    # Fall back to object attribute for legacy objects
    # This will work with both regular attributes and our RefProperty
    return getattr(obj, "ref", None)


def remove_ref(obj: Any) -> None:
    if get_ref(obj) is not None:
        if "ref" in obj.__dict__:  # for methods
            obj.__dict__["ref"] = None
        else:
            obj.ref = None


def set_ref(obj: Any, ref: Ref | None) -> None:
    """Try to set the ref on "any" object.

    Uses context-aware storage to ensure refs are isolated between contexts.
    Falls back to setting on the object for backward compatibility.
    """
    # Always store in context to ensure isolation
    context_state.set_ref(obj, ref)

    # For backward compatibility, also try to set on the object
    # If object has our RefProperty, this will be handled correctly
    try:
        # Try the normal attribute set first (works with RefProperty)
        obj.ref = ref
    except:
        # If that fails, try to set directly in __dict__
        try:
            if hasattr(obj, "__dict__"):
                obj.__dict__["_weave_ref"] = ref
        except:
            # It's OK if we can't set on the object
            # The context storage is the primary mechanism
            pass
