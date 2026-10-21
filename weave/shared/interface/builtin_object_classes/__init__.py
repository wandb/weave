"""Moved to weave.trace.builtin_object_classes. Its modules here are aliases that warn."""

import importlib
import sys
import warnings
from typing import Any

# The modules that moved; `import *` used to bind them once `import weave` had loaded them.
__all__ = [
    "agent_dashboard",  # noqa: F822  # resolved lazily by __getattr__ below
    "alert_spec",  # noqa: F822
    "annotation_spec",  # noqa: F822
    "base_object_def",  # noqa: F822
    "builtin_object_registry",  # noqa: F822
    "comparison_view",  # noqa: F822
    "leaderboard",  # noqa: F822
    "llm_structured_model",  # noqa: F822
    "provider",  # noqa: F822
    "saved_view",  # noqa: F822
    "test_only_example",  # noqa: F822
]


def __getattr__(name: str) -> Any:
    """Resolve the modules that moved out of this package on access, so each one warns."""
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    new_path = f"weave.trace.builtin_object_classes.{name}"
    value = importlib.import_module(new_path)
    warnings.warn(
        f"{__name__}.{name} is deprecated and will be removed in a future release; "
        f"import {new_path} instead.",
        FutureWarning,
        stacklevel=2,
    )
    # A later import of the old path then finds the module and does not warn again.
    sys.modules[f"{__name__}.{name}"] = value
    globals()[name] = value
    return value
