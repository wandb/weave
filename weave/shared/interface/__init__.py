import importlib
from typing import Any

from weave.shared import _import_type_module

# The subpackage and modules `import *` used to bind once `import weave` had loaded them.
__all__ = [
    "builtin_object_classes",  # noqa: F822  # resolved lazily by __getattr__ below
    "feedback_types",  # noqa: F822
    "query",  # noqa: F822
]


def __getattr__(name: str) -> Any:
    """Load a submodule on access: `import weave` no longer loads any of them."""
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    if name == "builtin_object_classes":
        # It warns itself when a moved module is read from it.
        return importlib.import_module(f"{__name__}.{name}")
    return _import_type_module(f"{__name__}.{name}")
