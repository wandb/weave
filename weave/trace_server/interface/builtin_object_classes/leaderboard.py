"""Back-compat shim: implementation moved to weave.shared.builtin_object_classes.leaderboard."""

from typing import Any

from weave.shared.builtin_object_classes import leaderboard as _impl
from weave.shared.builtin_object_classes.leaderboard import *  # noqa: F403


def __getattr__(name: str) -> Any:
    # Forward names that star-import misses (e.g. excluded by __all__).
    return getattr(_impl, name)
