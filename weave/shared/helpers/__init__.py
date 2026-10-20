"""Its only module moved to weave.utils.url_safety; the path here is an alias that warns."""

import importlib
import sys
import warnings
from typing import Any

__all__ = ["url_safety"]  # noqa: F822  # resolved lazily by __getattr__ below


def __getattr__(name: str) -> Any:
    """Resolve url_safety, which moved out of this package, on access, so it warns."""
    if name != "url_safety":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = importlib.import_module("weave.utils.url_safety")
    warnings.warn(
        "weave.shared.helpers.url_safety is deprecated and will be removed in a "
        "future release; import weave.utils.url_safety instead.",
        FutureWarning,
        stacklevel=2,
    )
    # A later import of the old path then finds the module and does not warn again.
    sys.modules[f"{__name__}.url_safety"] = value
    globals()[name] = value
    return value
