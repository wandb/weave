"""Canonical location is ``weave.shared.interface.builtin_object_classes.saved_view``. This module re-exports it."""

# Copy public names instead of import * so names omitted from __all__ still re-export.
from weave.shared.interface.builtin_object_classes import saved_view as _canonical

globals().update(
    {
        name: getattr(_canonical, name)
        for name in dir(_canonical)
        if not name.startswith("_")
    }
)
