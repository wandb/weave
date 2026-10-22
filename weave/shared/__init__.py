"""Utilities shared between the Weave client and trace server implementations."""

import importlib
import sys
import warnings
from types import ModuleType
from typing import Any

# The digest helpers this package re-exported; they moved to weave.trace.serialization.digest.
__all__ = [
    "ObjectDigestResult",  # noqa: F822  # resolved lazily by __getattr__ below
    "bytes_digest",  # noqa: F822
    "compute_file_digest",  # noqa: F822
    "compute_object_digest",  # noqa: F822
    "compute_object_digest_result",  # noqa: F822
    "compute_row_digest",  # noqa: F822
    "compute_table_digest",  # noqa: F822
    "str_digest",  # noqa: F822
]

# Submodules that moved into the client, by new path. Their weave.shared paths are aliases that warn.
_MOVED_MODULES = {
    "constants": "weave.trace.constants",
    "digest": "weave.trace.serialization.digest",
    "ids": "weave.utils.ids",
    "object_class_util": "weave.trace.serialization.object_class_util",
    "otel_context_keys": "weave.trace.otel_context_keys",
    "otel_span_attrs": "weave.trace.otel_span_attrs",
    "pydantic_util": "weave.utils.pydantic_util",
    "refs": "weave.trace.refs_base",
    "refs_internal": "weave.trace.refs_internal",
    "serialization_metadata": "weave.trace.serialization.serialization_metadata",
    "trace_server_converter": "weave.trace.trace_server_converter",
    "tracing": "weave.trace.server_tracing",
}


# The API type modules, and the packages holding more, that `import weave` loaded
# before the client stopped using them.
_TYPE_MODULES = frozenset(
    {
        "common_interface",
        "http_service_interface",
        "service_interface",
        "trace_server_interface",
        "validation",
        "validation_util",
    }
)
_TYPE_PACKAGES = frozenset({"agents", "interface", "sensitive_data"})


def _import_type_module(name: str) -> ModuleType:
    """Import a deprecated API type module on attribute access, warning at the caller.

    The module warns when it is imported, but that warning would point at importlib,
    so its own message is emitted again from the caller's line.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", FutureWarning)
        module = importlib.import_module(name)
    for caught_warning in caught:
        if issubclass(caught_warning.category, FutureWarning) and str(
            caught_warning.message
        ).startswith(f"{name} "):
            warnings.warn(caught_warning.message, stacklevel=3)
        else:
            warnings.warn_explicit(
                caught_warning.message,
                caught_warning.category,
                caught_warning.filename,
                caught_warning.lineno,
            )
    return module


def __getattr__(name: str) -> Any:
    """Resolve the names that moved out of this package on access, so each one warns."""
    if name in _TYPE_MODULES:
        return _import_type_module(f"{__name__}.{name}")
    if name in _TYPE_PACKAGES:
        # Their modules warn on access.
        return importlib.import_module(f"{__name__}.{name}")
    if name == "helpers":
        # Its only module moved, so nothing imports it; its own __getattr__ warns.
        return importlib.import_module(f"{__name__}.helpers")
    if name == "errors":
        # Nothing imports it any more. It warns when imported; warn here instead, so
        # the warning points at the caller and not at importlib.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            value = importlib.import_module(f"{__name__}.errors")
        warnings.warn(
            "weave.shared.errors is deprecated and will be removed in a future "
            "release; import the error classes from weave.trace.errors instead.",
            FutureWarning,
            stacklevel=2,
        )
        return value
    if name in _MOVED_MODULES:
        new_path = _MOVED_MODULES[name]
        value = importlib.import_module(new_path)
        advice = f"import {new_path} instead."
    elif name in __all__:
        # Imported here, not at the top: digest imports the builtin object registry, which loads this package.
        from weave.trace.serialization import digest

        value = getattr(digest, name)
        advice = "import it from weave.trace.serialization.digest instead."
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    warnings.warn(
        f"weave.shared.{name} is deprecated and will be removed in a future release; "
        + advice,
        FutureWarning,
        stacklevel=2,
    )
    if name in _MOVED_MODULES:
        # A later `import weave.shared.<name>` then finds the module and does not warn again.
        sys.modules[f"{__name__}.{name}"] = value
    # `from weave.shared import name` looks the name up twice; the second lookup finds it here.
    globals()[name] = value
    return value
