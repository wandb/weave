"""Canonical location is ``weave.shared.errors``. This module re-exports it."""

# import * skips names starting with _, but core calls tse._get_error_registry().
from weave.shared import errors as _canonical

globals().update(
    {
        name: getattr(_canonical, name)
        for name in dir(_canonical)
        if not (name.startswith("__") and name.endswith("__"))
    }
)
del _canonical
