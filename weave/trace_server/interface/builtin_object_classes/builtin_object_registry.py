"""Canonical location is ``weave.trace.builtin_object_classes.builtin_object_registry``. This module is that module."""

import sys
import warnings

from weave.trace.builtin_object_classes import builtin_object_registry as _canonical
from weave.trace.builtin_object_classes.builtin_object_registry import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.trace_server.interface.builtin_object_classes.builtin_object_registry"
    " is deprecated since weave 0.53.13 and will be removed in a future "
    "release; import weave.trace.builtin_object_classes.builtin_object_registry"
    " instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
