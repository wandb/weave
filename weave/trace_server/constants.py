"""Back-compat shim: implementation moved to weave.shared.constants."""

from typing import Any

from weave.shared import constants as _impl
from weave.shared.constants import *  # noqa: F403


def __getattr__(name: str) -> Any:
    # Forward names that star-import misses (e.g. excluded by __all__).
    return getattr(_impl, name)
