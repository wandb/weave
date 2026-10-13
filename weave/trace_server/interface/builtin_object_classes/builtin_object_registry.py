"""Canonical location is ``weave.shared.interface.builtin_object_classes.builtin_object_registry``. This module is that module."""

import sys
import warnings

from weave.shared.interface.builtin_object_classes import (
    builtin_object_registry as _canonical,
)
from weave.shared.interface.builtin_object_classes.builtin_object_registry import *  # noqa: F403

# TODO: delete this alias after weave 0.53.13.
warnings.warn(
    "weave.trace_server.interface.builtin_object_classes.builtin_object_registry "
    "is deprecated since weave 0.53.13 and will be removed after weave 0.53.13; "
    "import weave.shared.interface.builtin_object_classes.builtin_object_registry "
    "instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
