"""
Property-based ref handling to intercept direct .ref access.

This module provides a base class and descriptor that automatically
routes .ref access through get_ref/set_ref for proper context isolation.
"""

from typing import Any, Optional, Type
from weakref import WeakKeyDictionary

from weave.trace.refs import Ref


class RefProperty:
    """
    Descriptor that intercepts .ref access and routes through ref_util functions.

    This ensures that even legacy code using obj.ref directly will benefit
    from context isolation.
    """

    def __init__(self):
        # Store refs that were set directly on objects before this descriptor
        # was installed (for backward compatibility during migration)
        self._legacy_refs: WeakKeyDictionary[Any, Optional[Ref]] = WeakKeyDictionary()

    def __get__(self, instance: Any, owner: Type[Any] = None) -> Optional[Ref]:
        if instance is None:
            return self

        # Import here to avoid circular imports
        from weave.trace.context import context_state

        # Check context-specific refs first
        context_ref = context_state.get_ref(instance)
        if context_ref is not None:
            return context_ref

        # Check legacy refs (only for hashable objects)
        try:
            if instance in self._legacy_refs:
                return self._legacy_refs[instance]
        except TypeError:
            # Object is not hashable, skip legacy refs
            pass

        # Check if object has ref stored directly in __dict__ (backward compatibility)
        if hasattr(instance, "__dict__") and "_weave_ref" in instance.__dict__:
            return instance.__dict__["_weave_ref"]

        return None

    def __set__(self, instance: Any, value: Optional[Ref]) -> None:
        if instance is None:
            return

        # Import here to avoid circular imports
        from weave.trace.context import context_state

        # Set in context
        context_state.set_ref(instance, value)

        # Also store in instance for backward compatibility
        if hasattr(instance, "__dict__"):
            instance.__dict__["_weave_ref"] = value

    def __delete__(self, instance: Any) -> None:
        if instance is None:
            return

        # Import here to avoid circular imports
        from weave.trace.context import context_state

        # Clear from context
        context_state.set_ref(instance, None)

        # Clear from instance
        if hasattr(instance, "__dict__") and "_weave_ref" in instance.__dict__:
            del instance.__dict__["_weave_ref"]

        # Also clear any legacy ref (only for hashable objects)
        try:
            if instance in self._legacy_refs:
                del self._legacy_refs[instance]
        except TypeError:
            # Object is not hashable, skip legacy refs
            pass


class RefPropertyMixin:
    """
    Mixin class that adds the ref property descriptor.

    Classes can inherit from this to automatically get context-aware ref handling.
    """

    ref = RefProperty()


def add_ref_property(cls: Type[Any]) -> Type[Any]:
    """
    Class decorator that adds the ref property descriptor to a class.

    This can be used to retrofit existing classes without changing their inheritance.

    Example:
        @add_ref_property
        class MyClass:
            def __init__(self):
                # No need to set self.ref = None
                pass
    """
    # Check if the class already has a ref attribute
    if hasattr(cls, "ref"):
        # Save any existing refs before replacing the attribute
        ref_prop = RefProperty()
        for instance in cls.__dict__.get("__instances__", []):
            if hasattr(instance, "ref"):
                ref_prop._legacy_refs[instance] = getattr(instance, "ref", None)
    else:
        ref_prop = RefProperty()

    # Install the property
    setattr(cls, "ref", ref_prop)
    return cls


def monkey_patch_ref_property(cls: Type[Any]) -> None:
    """
    Monkey patch an existing class to use the ref property descriptor.

    This is useful for third-party classes or when you can't modify the class definition.

    Args:
        cls: The class to patch
    """
    # Get all existing instances if we can find them
    existing_refs = {}

    # Try to preserve existing refs if possible
    if hasattr(cls, "__instances__"):
        for instance in cls.__instances__:
            if hasattr(instance, "ref"):
                existing_refs[id(instance)] = getattr(instance, "ref", None)

    # Create and install the property
    ref_prop = RefProperty()

    # Store the original ref attribute if it exists
    original_ref = getattr(cls, "ref", None)

    # Install our descriptor
    setattr(cls, "ref", ref_prop)

    # If we found existing refs, store them in the legacy dict
    for inst_id, ref in existing_refs.items():
        # This is a bit hacky, but we need to find the instance by id
        import gc

        for obj in gc.get_objects():
            if id(obj) == inst_id and isinstance(obj, cls):
                ref_prop._legacy_refs[obj] = ref
                break
