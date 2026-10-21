"""Canonical location is ``weave.trace.builtin_object_classes.comparison_view``. This module is that module."""

import sys
import warnings

from weave.trace.builtin_object_classes import comparison_view as _canonical
from weave.trace.builtin_object_classes.comparison_view import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.trace_server.interface.builtin_object_classes.comparison_view is "
    "deprecated since weave 0.53.13 and will be removed in a future release; "
    "import weave.trace.builtin_object_classes.comparison_view instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
