"""Canonical location is ``weave.shared.interface.builtin_object_classes.base_object_def``. This module is that module."""

import sys
import warnings

from weave.shared.interface.builtin_object_classes import base_object_def as _canonical
from weave.shared.interface.builtin_object_classes.base_object_def import *  # noqa: F403

# TODO: delete this alias after weave 0.53.13.
warnings.warn(
    "weave.trace_server.interface.builtin_object_classes.base_object_def is "
    "deprecated since weave 0.53.13 and will be removed after weave 0.53.13; "
    "import weave.shared.interface.builtin_object_classes.base_object_def "
    "instead.",
    FutureWarning,
    stacklevel=2,
)

sys.modules[__name__] = _canonical
