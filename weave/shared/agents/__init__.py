from typing import Any

from weave.shared import _import_type_module

# The modules `import *` used to bind once `import weave` had loaded them.
__all__ = [
    "constants",  # noqa: F822  # resolved lazily by __getattr__ below
    "schema",  # noqa: F822
    "semconv",  # noqa: F822
    "types",  # noqa: F822
]


def __getattr__(name: str) -> Any:
    """Load a module on access, which `import weave` no longer does, so it warns."""
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return _import_type_module(f"{__name__}.{name}")
