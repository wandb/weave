"""Compatibility imports; definitions live in weave.shared.trace_server."""

from weave.shared.trace_server.interface.builtin_object_classes.base_object_def import (
    BaseObject,
    RefStr,
    pydantic,
)

__all__ = ["BaseObject", "RefStr", "pydantic"]
