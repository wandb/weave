"""Back-compat shim: implementation moved to weave.shared.ids."""

from typing import Any

from weave.shared import ids as _impl
from weave.shared.ids import *  # noqa: F403


def __getattr__(name: str) -> Any:
    # Forward names that star-import misses (e.g. excluded by __all__).
    return getattr(_impl, name)
