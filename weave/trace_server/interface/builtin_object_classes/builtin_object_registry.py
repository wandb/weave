"""Back-compat shim: implementation moved to weave.shared.builtin_object_classes.builtin_object_registry."""

from typing import Any

from weave.shared.builtin_object_classes import builtin_object_registry as _impl
from weave.shared.builtin_object_classes.builtin_object_registry import *  # noqa: F403


def __getattr__(name: str) -> Any:
    # Forward names that star-import misses (e.g. excluded by __all__).
    return getattr(_impl, name)
