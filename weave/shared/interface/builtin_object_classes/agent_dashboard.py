"""Canonical location is ``weave.trace.builtin_object_classes.agent_dashboard``. This module is that module."""

import sys
import warnings

from weave.trace.builtin_object_classes import agent_dashboard as _canonical
from weave.trace.builtin_object_classes.agent_dashboard import *  # noqa: F403

# TODO: delete this alias together with weave.shared.
warnings.warn(
    "weave.shared.interface.builtin_object_classes.agent_dashboard is "
    "deprecated and will be removed in a future release; import "
    "weave.trace.builtin_object_classes.agent_dashboard instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
