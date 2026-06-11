"""Back-compat shim: implementation moved to weave.shared.url_safety."""

from typing import Any

from weave.shared import url_safety as _impl
from weave.shared.url_safety import *  # noqa: F403


def __getattr__(name: str) -> Any:
    # Forward names that star-import misses (e.g. excluded by __all__).
    return getattr(_impl, name)
