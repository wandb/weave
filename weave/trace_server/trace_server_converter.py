"""Back-compat shim: implementation moved to weave.shared.trace_server_converter."""

from typing import Any

from weave.shared import trace_server_converter as _impl
from weave.shared.trace_server_converter import *  # noqa: F403


def __getattr__(name: str) -> Any:
    # Forward names that star-import misses (e.g. excluded by __all__).
    return getattr(_impl, name)
