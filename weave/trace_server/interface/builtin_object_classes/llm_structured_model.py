"""Back-compat shim: implementation moved to weave.shared.builtin_object_classes.llm_structured_model."""

from typing import Any

from weave.shared.builtin_object_classes import llm_structured_model as _impl
from weave.shared.builtin_object_classes.llm_structured_model import *  # noqa: F403


def __getattr__(name: str) -> Any:
    # Forward names that star-import misses (e.g. excluded by __all__).
    return getattr(_impl, name)
