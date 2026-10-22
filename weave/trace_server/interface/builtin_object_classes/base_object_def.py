"""Canonical location is ``weave.trace.builtin_object_classes.base_object_def``. This module is that module."""

import sys
import warnings

from weave.trace.builtin_object_classes import base_object_def as _canonical
from weave.trace.builtin_object_classes.base_object_def import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.trace_server.interface.builtin_object_classes.base_object_def is "
    "deprecated since weave 0.53.13 and will be removed in a future release; "
    "import weave.trace.builtin_object_classes.base_object_def instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
