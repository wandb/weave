"""Canonical location is ``weave.trace.builtin_object_classes.alert_spec``. This module is that module."""

import sys
import warnings

from weave.trace.builtin_object_classes import alert_spec as _canonical
from weave.trace.builtin_object_classes.alert_spec import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.trace_server.interface.builtin_object_classes.alert_spec is "
    "deprecated since weave 0.53.13 and will be removed in a future release; "
    "import weave.trace.builtin_object_classes.alert_spec instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
