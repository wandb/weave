from __future__ import annotations

from typing import Any

from weave.trace.refs import ObjectRef, Ref


def get_ref(obj: Any) -> ObjectRef | None:
    return getattr(obj, "ref", None)


def remove_ref(obj: Any) -> None:
    if get_ref(obj) is not None:
        if "ref" in obj.__dict__:  # for methods
            obj.__dict__["ref"] = None
        else:
            obj.ref = None


def set_ref(obj: Any, ref: Ref | None) -> None:
    """Try to set the ref on "any" object.

    We use increasingly complex methods to try to set the ref
    to support different kinds of objects. This will still
    fail for python primitives, but those can't be traced anyway.
    """
    try:
        obj.ref = ref
    except:
        try:
            setattr(obj, "ref", ref)
        except:
            try:
                obj.__dict__["ref"] = ref
            except:
                raise ValueError(f"Failed to set ref on object of type {type(obj)}")
