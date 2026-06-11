"""Back-compat shim: implementation moved to weave.shared.builtin_object_classes.comparison_view."""

from typing import Any

from weave.shared.builtin_object_classes import comparison_view as _impl
from weave.shared.builtin_object_classes.comparison_view import *  # noqa: F403


def __getattr__(name: str) -> Any:
    # Forward names that star-import misses (e.g. excluded by __all__).
    return getattr(_impl, name)
