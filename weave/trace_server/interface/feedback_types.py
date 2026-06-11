"""Back-compat shim: implementation moved to weave.shared.feedback_types."""

from typing import Any

from weave.shared import feedback_types as _impl
from weave.shared.feedback_types import *  # noqa: F403


def __getattr__(name: str) -> Any:
    # Forward names that star-import misses (e.g. excluded by __all__).
    return getattr(_impl, name)
