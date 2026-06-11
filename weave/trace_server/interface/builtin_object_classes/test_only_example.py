"""Back-compat shim: implementation moved to weave.shared.builtin_object_classes.test_only_example."""

from typing import Any

from weave.shared.builtin_object_classes import test_only_example as _impl
from weave.shared.builtin_object_classes.test_only_example import *  # noqa: F403


def __getattr__(name: str) -> Any:
    # Forward names that star-import misses (e.g. excluded by __all__).
    return getattr(_impl, name)
